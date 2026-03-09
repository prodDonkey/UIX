from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import threading
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.run import Run
from app.models.script import Script


def create_run(db: Session, script_id: int) -> Run:
    if not db.get(Script, script_id):
        raise ValueError("Script not found")

    run = Run(script_id=script_id, status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def list_runs(db: Session, script_id: int | None = None, limit: int = 200) -> list[Run]:
    stmt = (
        select(Run)
        .options(
            load_only(
                Run.id,
                Run.script_id,
                Run.status,
                Run.started_at,
                Run.ended_at,
                Run.duration_ms,
                Run.request_id,
                Run.error_message,
                Run.remark,
                Run.is_starred,
            )
        )
        .order_by(Run.id.desc())
        .limit(limit)
    )
    if script_id is not None:
        stmt = stmt.where(Run.script_id == script_id)
    return list(db.scalars(stmt).all())


def start_run_async(run_id: int) -> None:
    thread = threading.Thread(target=_execute_run, args=(run_id,), daemon=True)
    thread.start()


def cancel_run(db: Session, run_id: int) -> Run | None:
    run = db.get(Run, run_id)
    if not run:
        return None

    if run.status not in ("queued", "running"):
        _append_log_line(run.log_path, f"[{_now_str()}] cancel ignored for run {run_id} status={run.status}")
        return run

    if run.request_id:
        _append_log_line(
            run.log_path,
            f"[{_now_str()}] midsce cancel start run={run_id} requestId={run.request_id}",
        )
        cancel_result = _midscene_cancel_task(run.request_id)
        cancel_status = str(cancel_result.get("status") or "").strip().lower()
        if cancel_status not in ("cancelled", "completed"):
            message = (
                f"midsce cancel failed for requestId={run.request_id}: "
                f"{cancel_result.get('message') or cancel_result.get('error') or cancel_status or 'unknown'}"
            )
            _append_log_line(run.log_path, f"[{_now_str()}] {message}")
            raise RuntimeError(message)

        run.status = "cancelled"
        run.ended_at = datetime.utcnow()
        if run.started_at:
            run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
        report_path = _extract_report_path(cancel_result)
        if report_path:
            run.report_path = report_path
        db.commit()
        db.refresh(run)
        _append_log_line(
            run.log_path,
            f"[{_now_str()}] midsce cancel done run={run_id} requestId={run.request_id}",
        )
        return run

    run.status = "cancelled"
    run.ended_at = datetime.utcnow()
    if run.started_at:
        run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
    db.commit()
    db.refresh(run)

    _append_log_line(run.log_path, f"[{_now_str()}] cancel requested for run {run_id} before midsce accept")
    return run


def _execute_run(run_id: int) -> None:
    log_path: str | None = None
    started_at: datetime | None = None
    request_id: str | None = None
    last_progress: dict | None = None
    try:
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if not run or run.status == "cancelled":
                return

            script = db.get(Script, run.script_id)
            if not script:
                run.status = "failed"
                run.error_message = "Script not found"
                db.commit()
                return

            logs_dir = Path(settings.run_logs_dir)
            logs_dir.mkdir(parents=True, exist_ok=True)
            current_log_path = logs_dir / f"run-{run.id}.log"

            run.status = "running"
            run.started_at = datetime.utcnow()
            run.log_path = str(current_log_path.resolve())
            run.current_task = None
            run.current_action = None
            run.progress_json = None
            run.error_message = None
            run.request_id = None
            db.commit()

            log_path = run.log_path
            started_at = run.started_at
            script_content = script.content

        _append_log_line(log_path, f"[{_now_str()}] midsce start run={run_id}")
        run_yaml_result = _midscene_run_yaml(script_content)
        request_id = str(run_yaml_result.get("requestId") or "").strip()
        if not request_id:
            raise ValueError(f"Invalid midsce run-yaml response: {run_yaml_result}")

        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if not run or run.status == "cancelled":
                if run and run.status == "cancelled":
                    _append_log_line(log_path, f"[{_now_str()}] cancelled locally before requestId persisted")
                return
            run.request_id = request_id
            db.commit()

        _append_log_line(log_path, f"[{_now_str()}] midsce accepted requestId={request_id}")

        poll_interval_sec = max(settings.midscene_status_poll_interval_ms, 500) / 1000
        while True:
            with SessionLocal() as db:
                run = db.get(Run, run_id)
                if not run:
                    return
                if run.status == "cancelled":
                    _append_log_line(log_path, f"[{_now_str()}] cancelled by user")
                    return

            try:
                progress = _midscene_task_progress(request_id)
                last_progress = progress
            except Exception as exc:  # noqa: BLE001
                _append_log_line(log_path, f"[{_now_str()}] task-progress fetch error={exc}")
                progress = {}

            compact_progress = _compact_midscene_progress(progress, run_id)
            with SessionLocal() as db:
                run = db.get(Run, run_id)
                if not run:
                    return
                if run.status == "cancelled":
                    _append_log_line(log_path, f"[{_now_str()}] cancelled by user")
                    return
                run.current_task = compact_progress.get("currentTask")
                run.current_action = compact_progress.get("currentAction")
                run.progress_json = json.dumps(compact_progress, ensure_ascii=False)
                db.commit()

            result = _midscene_task_result(request_id)
            midscene_status = str(result.get("status") or "").strip().lower()
            run_status = _map_midscene_status_to_run(midscene_status)
            if run_status in ("success", "failed", "cancelled"):
                error_message = _extract_error_message(result, midscene_status)
                with SessionLocal() as db:
                    run = db.get(Run, run_id)
                    if not run:
                        return
                    if run.status == "cancelled":
                        return
                    run.status = run_status
                    run.ended_at = datetime.utcnow()
                    start_for_duration = run.started_at or started_at
                    if start_for_duration:
                        run.duration_ms = int((run.ended_at - start_for_duration).total_seconds() * 1000)
                    run.error_message = error_message
                    run.report_path = _extract_report_path(result)
                    run.summary_path = None
                    if last_progress is not None:
                        final_progress = _compact_midscene_progress(last_progress, run_id)
                        run.current_task = final_progress.get("currentTask")
                        run.current_action = final_progress.get("currentAction")
                        run.progress_json = json.dumps(final_progress, ensure_ascii=False)
                    db.commit()
                _append_log_line(
                    log_path,
                    f"[{_now_str()}] midsce finished status={midscene_status} mapped={run_status}",
                )
                return

            _append_log_line(
                log_path,
                (
                    f"[{_now_str()}] midsce polling status={midscene_status or '-'} "
                    f"task={compact_progress.get('currentTask') or '-'} "
                    f"action={compact_progress.get('currentAction') or '-'} "
                    f"progress={compact_progress.get('completed') or 0}/{compact_progress.get('total') or 0}"
                ),
            )
            time.sleep(poll_interval_sec)
    except Exception as exc:  # noqa: BLE001
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run:
                run.status = "failed"
                run.ended_at = datetime.utcnow()
                start_for_duration = run.started_at or started_at
                if start_for_duration:
                    run.duration_ms = int((run.ended_at - start_for_duration).total_seconds() * 1000)
                run.error_message = str(exc)
                if request_id and not run.request_id:
                    run.request_id = request_id
                db.commit()
                _append_log_line(run.log_path or log_path, f"[{_now_str()}] failed error={exc}")


def read_run_logs(run: Run, tail_bytes: int = 50_000) -> str:
    if not run.log_path:
        return ""
    path = Path(run.log_path)
    if not path.exists() or not path.is_file():
        return ""
    with path.open("rb") as file:
        file.seek(0, 2)
        size = file.tell()
        if size <= tail_bytes:
            file.seek(0)
        else:
            file.seek(size - tail_bytes)
        data = file.read()
    return data.decode("utf-8", errors="ignore")


def get_report_path(run: Run) -> str | None:
    if not run.report_path:
        return None
    report_path = Path(run.report_path)
    if report_path.exists() and report_path.is_file():
        return str(report_path.resolve())
    return run.report_path


def get_runtime_report_path(run: Run) -> str | None:
    if not run.request_id:
        return None
    try:
        result = _midscene_task_result(run.request_id)
    except Exception:
        return None
    value = _extract_report_path(result)
    if not value:
        return None
    report_path = Path(value)
    if report_path.exists() and report_path.is_file():
        return str(report_path.resolve())
    return value


def get_report_html(run: Run) -> str | None:
    if not run.request_id:
        return None
    try:
        result = _midscene_task_result(run.request_id)
    except Exception:
        return None
    report_html = result.get("reportHTML") or result.get("report_html")
    if isinstance(report_html, str) and report_html.strip():
        # Midscene 某些环境会返回带占位符的模板 HTML，直接预览会是空白页。
        # 这种内容不能作为最终报告返回，优先让上层继续寻找真实 reportPath。
        if "REPLACE_ME_WITH_REPORT_HTML" in report_html:
            return None
        return report_html
    return None


def _midscene_run_yaml(yaml_content: str) -> dict:
    return _midscene_request("POST", "/run-yaml", json_body={"yaml": yaml_content})


def _midscene_task_progress(request_id: str) -> dict:
    return _midscene_request("GET", f"/task-progress/{request_id}")


def _midscene_task_result(request_id: str) -> dict:
    return _midscene_request("GET", f"/task-result/{request_id}")


def _midscene_cancel_task(request_id: str) -> dict:
    return _midscene_request("POST", f"/cancel/{request_id}")


def _midscene_request(method: str, path: str, json_body: dict | None = None) -> dict:
    url = f"{settings.midscene_base_url.rstrip('/')}{path}"
    timeout = httpx.Timeout(settings.midscene_timeout_sec)
    with httpx.Client(timeout=timeout) as client:
        response = client.request(method, url, json=json_body)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"Invalid midsce response from {url}: {data}")
        return data


def _map_midscene_status_to_run(status: str) -> str:
    if status == "completed":
        return "success"
    if status == "failed":
        return "failed"
    if status == "cancelled":
        return "cancelled"
    if status == "not_found":
        return "failed"
    return "running"


def _extract_error_message(result: dict, status: str) -> str | None:
    raw_error = result.get("errorMessage") or result.get("error") or result.get("message")
    if isinstance(raw_error, str) and raw_error.strip():
        return raw_error.strip()
    if status == "not_found":
        return "midsce task not found for requestId"
    return None


def _extract_report_path(result: dict) -> str | None:
    value = result.get("reportPath") or result.get("report_path")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _append_log_line(log_path: str | None, content: str) -> None:
    if not log_path:
        return
    try:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(content)
            file.write("\n")
    except Exception:
        return


def _now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _compact_midscene_progress(progress: dict, run_id: int) -> dict:
    tasks = progress.get("tasks")
    compact_tasks: list[dict] = []
    if isinstance(tasks, list):
        for task in tasks[-20:]:
            if not isinstance(task, dict):
                continue
            compact_tasks.append(
                {
                    "taskId": task.get("taskId") or task.get("id"),
                    "status": task.get("status"),
                    "type": task.get("type"),
                    "subType": task.get("subType"),
                    "thought": task.get("thought"),
                    "param": task.get("param"),
                    "timing": task.get("timing"),
                    "error": task.get("error"),
                }
            )

    return {
        "runId": run_id,
        "status": _map_midscene_status_to_run(str(progress.get("status") or "").lower()),
        "currentTask": progress.get("currentTask") or progress.get("current_task"),
        "currentAction": progress.get("currentAction") or progress.get("current_action"),
        "completed": progress.get("completed"),
        "total": progress.get("total"),
        "updatedAt": progress.get("updatedAt") or progress.get("updated_at"),
        "executionDump": {
            "name": progress.get("name"),
            "tasks": compact_tasks,
        },
    }
