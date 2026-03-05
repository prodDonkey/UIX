from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import threading
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

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


def list_runs(db: Session, script_id: int | None = None) -> list[Run]:
    stmt = select(Run).order_by(Run.id.desc())
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

    # 幂等取消：仅 queued/running 允许切换为 cancelled
    if run.status in ("queued", "running"):
        run.status = "cancelled"
        run.ended_at = datetime.utcnow()
        if run.started_at:
            run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
        db.commit()
        db.refresh(run)

    # 最佳努力通知 Runner 取消，不影响接口返回
    _runner_cancel(run_id)
    _append_log_line(run.log_path, f"[{_now_str()}] cancel requested for run {run_id}")
    return run


def _execute_run(run_id: int) -> None:
    log_path: str | None = None
    started_at: datetime | None = None
    try:
        # 使用短会话初始化 run，避免后台线程长时间占用连接池。
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if not run:
                return
            if run.status == "cancelled":
                return

            script = db.get(Script, run.script_id)
            if not script:
                run.status = "failed"
                run.error_message = "Script not found"
                db.commit()
                return

            scripts_dir = Path(settings.run_scripts_dir)
            logs_dir = Path(settings.run_logs_dir)
            scripts_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)

            yaml_path = scripts_dir / f"run-{run.id}-script-{run.script_id}.yaml"
            current_log_path = logs_dir / f"run-{run.id}.log"
            yaml_path.write_text(script.content, encoding="utf-8")

            run.status = "running"
            run.started_at = datetime.utcnow()
            run.log_path = str(current_log_path.resolve())
            run.current_task = None
            run.current_action = None
            run.progress_json = None
            run.error_message = None
            db.commit()

            script_content = script.content
            log_path = run.log_path
            started_at = run.started_at

        _append_log_line(log_path, f"[{_now_str()}] runner start run={run_id}")
        _runner_start(run_id, script_content)

        terminal_status: str | None = None
        previous_progress_signature: tuple[str | None, str | None, int, int] | None = None
        poll_interval_sec = max(settings.runner_progress_poll_interval_ms, 200) / 1000

        while True:
            # 先从 runner 拉进度，再落库，避免数据库连接在网络请求期间被占用。
            progress = _runner_progress(run_id)
            progress_status = progress.get("status")

            with SessionLocal() as db:
                run = db.get(Run, run_id)
                if not run:
                    return
                if run.status == "cancelled":
                    _runner_cancel(run_id)
                    _append_log_line(log_path, f"[{_now_str()}] cancelled by user")
                    return

                run.current_task = progress.get("currentTask")
                run.current_action = progress.get("currentAction")
                run.progress_json = json.dumps(progress, ensure_ascii=False)
                db.commit()

                completed = _safe_int(progress.get("completed"))
                total = _safe_int(progress.get("total"))
                signature = (run.current_task, run.current_action, completed, total)
            if signature != previous_progress_signature:
                _append_log_line(
                    log_path,
                    (
                        f"[{_now_str()}] progress status={progress_status} "
                        f"task={signature[0] or '-'} action={signature[1] or '-'} "
                        f"completed={completed}/{total}"
                    ),
                )
                previous_progress_signature = signature

            if progress_status in ("success", "failed", "cancelled"):
                terminal_status = progress_status
                break

            time.sleep(poll_interval_sec)

        result = _runner_result(run_id)
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if not run:
                return
            if run.status == "cancelled":
                return

            run.ended_at = datetime.utcnow()
            start_for_duration = run.started_at or started_at
            if start_for_duration:
                run.duration_ms = int((run.ended_at - start_for_duration).total_seconds() * 1000)

            run.report_path = result.get("reportPath")
            run.summary_path = result.get("summaryPath")
            run.error_message = result.get("errorMessage")

            result_status = result.get("status") or terminal_status
            if result_status not in ("success", "failed", "cancelled"):
                result_status = "failed"
                run.error_message = run.error_message or f"Unexpected runner status: {result.get('status')}"

            run.status = result_status
            db.commit()
            final_status = run.status
            final_report_path = run.report_path

        _append_log_line(
            log_path,
            f"[{_now_str()}] runner finished status={final_status} report={final_report_path or '-'}",
        )
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
                db.commit()
                _append_log_line(run.log_path or log_path, f"[{_now_str()}] failed error={exc}")


def read_run_logs(run: Run) -> str:
    if not run.log_path:
        return ""
    path = Path(run.log_path)
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def get_report_path(run: Run) -> str | None:
    if not run.report_path:
        return None
    report_path = Path(run.report_path)
    if report_path.exists() and report_path.is_file():
        return str(report_path.resolve())
    return run.report_path


def _runner_start(run_id: int, yaml_content: str) -> None:
    _runner_request(
        "POST",
        "/runs/start",
        json_body={
            "runId": run_id,
            "yamlContent": yaml_content,
        },
    )


def _runner_progress(run_id: int) -> dict:
    return _runner_request("GET", f"/runs/{run_id}/progress")


def _runner_result(run_id: int) -> dict:
    return _runner_request("GET", f"/runs/{run_id}/result")


def _runner_cancel(run_id: int) -> None:
    try:
        _runner_request("POST", f"/runs/{run_id}/cancel")
    except Exception:
        # 取消是 best-effort，避免影响主流程
        return


def _runner_request(method: str, path: str, json_body: dict | None = None) -> dict:
    url = f"{settings.runner_base_url.rstrip('/')}{path}"
    timeout = httpx.Timeout(settings.runner_timeout_sec)
    with httpx.Client(timeout=timeout) as client:
        response = client.request(method, url, json=json_body)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"Invalid runner response from {url}: {data}")
        return data


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


def _safe_int(value: object) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0
