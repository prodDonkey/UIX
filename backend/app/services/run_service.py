from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import threading
import time
from urllib.parse import urlparse, urlunparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.run import Run
from app.models.scene import Scene
from app.models.scene_task_item import SceneTaskItem
from app.models.script import Script
from app.services.scene_compiler import SceneCompileError, compile_scene_script, extract_script_env

logger = logging.getLogger("uvicorn.error")
MIDSCENE_PORT_FALLBACK_SPAN = 5


def create_run(db: Session, script_id: int) -> Run:
    script = db.get(Script, script_id)
    if not script:
        raise ValueError("Script not found")

    run = Run(
        script_id=script_id,
        status="queued",
        script_name_snapshot=script.name,
        script_content_snapshot=script.content,
        script_updated_at_snapshot=script.updated_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def create_scene_run(db: Session, scene_id: int) -> Run:
    scene = db.get(Scene, scene_id)
    if not scene:
        raise ValueError("Scene not found")

    task_items = list(
        db.scalars(
            select(SceneTaskItem)
            .where(SceneTaskItem.scene_id == scene_id)
            .order_by(SceneTaskItem.sort_order.asc(), SceneTaskItem.id.asc())
        ).all()
    )
    if not task_items:
        raise ValueError("Scene has no task items")

    first_script = db.get(Script, task_items[0].script_id)
    if not first_script:
        raise ValueError("Scene task source script not found")

    try:
        compiled_yaml = compile_scene_script(
            extract_script_env(first_script.content),
            [item.task_content_snapshot for item in task_items],
        )
    except SceneCompileError as exc:
        raise ValueError(str(exc)) from exc

    run = Run(
        script_id=first_script.id,
        scene_id=scene.id,
        status="queued",
        scene_name_snapshot=scene.name,
        script_name_snapshot=scene.name,
        script_content_snapshot=compiled_yaml,
        script_updated_at_snapshot=scene.updated_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def list_runs(
    db: Session,
    script_id: int | None = None,
    scene_id: int | None = None,
    limit: int = 200,
) -> list[Run]:
    stmt = (
        select(Run)
        .options(
            load_only(
                Run.id,
                Run.script_id,
                Run.scene_id,
                Run.status,
                Run.started_at,
                Run.ended_at,
                Run.duration_ms,
                Run.request_id,
                Run.error_message,
                Run.total_tokens,
                Run.scene_name_snapshot,
                Run.remark,
                Run.is_starred,
            )
        )
        .order_by(Run.id.desc())
        .limit(limit)
    )
    if script_id is not None:
        stmt = stmt.where(Run.script_id == script_id)
    if scene_id is not None:
        stmt = stmt.where(Run.scene_id == scene_id)
    return list(db.scalars(stmt).all())


def start_run_async(run_id: int) -> None:
    thread = threading.Thread(target=_execute_run, args=(run_id,), daemon=True)
    thread.start()


def cancel_run(db: Session, run_id: int) -> Run | None:
    run = db.get(Run, run_id)
    if not run:
        return None

    if run.status not in ("queued", "running"):
        return run

    if run.request_id:
        cancel_result = _midscene_cancel_task(run.request_id)
        cancel_status = str(cancel_result.get("status") or "").strip().lower()
        if cancel_status not in ("cancelled", "completed"):
            message = (
                f"midsce cancel failed for requestId={run.request_id}: "
                f"{cancel_result.get('message') or cancel_result.get('error') or cancel_status or 'unknown'}"
            )
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
        return run

    run.status = "cancelled"
    run.ended_at = datetime.utcnow()
    if run.started_at:
        run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
    db.commit()
    db.refresh(run)
    return run


def _execute_run(run_id: int) -> None:
    started_at: datetime | None = None
    request_id: str | None = None
    last_progress: dict | None = None
    try:
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if not run or run.status == "cancelled":
                return

            script = db.get(Script, run.script_id)
            script_content = (run.script_content_snapshot or "").strip()
            if not script_content and not script:
                run.status = "failed"
                run.error_message = "Script not found"
                db.commit()
                return

            run.status = "running"
            run.started_at = datetime.utcnow()
            run.current_task = None
            run.current_action = None
            run.progress_json = None
            run.error_message = None
            run.request_id = None
            db.commit()

            started_at = run.started_at
            if not script_content and script:
                script_content = script.content

        run_yaml_result = _midscene_run_yaml(script_content)
        request_id = str(run_yaml_result.get("requestId") or "").strip()
        if not request_id:
            raise ValueError(f"Invalid midsce run-yaml response: {run_yaml_result}")

        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if not run or run.status == "cancelled":
                return
            run.request_id = request_id
            db.commit()

        poll_interval_sec = max(settings.midscene_status_poll_interval_ms, 500) / 1000
        while True:
            with SessionLocal() as db:
                run = db.get(Run, run_id)
                if not run:
                    return
                if run.status == "cancelled":
                    return

            try:
                progress = _midscene_task_progress(request_id)
                last_progress = progress
            except httpx.TimeoutException as exc:
                # 轮询超时不立即判失败，保留 run 为 running，等待下一轮继续收敛。
                logger.warning(
                    "Midscene task-progress轮询超时，继续重试 runId=%s requestId=%s error=%s",
                    run_id,
                    request_id,
                    exc,
                )
                progress = {}
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Midscene task-progress轮询失败，继续重试 runId=%s requestId=%s error=%s",
                    run_id,
                    request_id,
                    exc,
                )
                progress = {}

            compact_progress = _compact_midscene_progress(progress, run_id)
            with SessionLocal() as db:
                run = db.get(Run, run_id)
                if not run:
                    return
                if run.status == "cancelled":
                    return
                run.current_task = compact_progress.get("currentTask")
                run.current_action = compact_progress.get("currentAction")
                run.progress_json = json.dumps(compact_progress, ensure_ascii=False)
                db.commit()

            try:
                result = _midscene_task_result(request_id)
            except httpx.TimeoutException as exc:
                logger.warning(
                    "Midscene task-result轮询超时，继续重试 runId=%s requestId=%s error=%s",
                    run_id,
                    request_id,
                    exc,
                )
                time.sleep(poll_interval_sec)
                continue
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
                    run.total_tokens = _extract_total_tokens_from_progress(last_progress)
                    if last_progress is not None:
                        final_progress = _compact_midscene_progress(last_progress, run_id)
                        run.current_task = final_progress.get("currentTask")
                        run.current_action = final_progress.get("currentAction")
                        run.progress_json = json.dumps(final_progress, ensure_ascii=False)
                    db.commit()
                return
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
                if run.total_tokens is None and request_id:
                    try:
                        progress = _midscene_task_progress(request_id)
                    except Exception:  # noqa: BLE001
                        progress = last_progress
                    else:
                        last_progress = progress
                    run.total_tokens = _extract_total_tokens_from_progress(progress)
                    if isinstance(progress, dict):
                        final_progress = _compact_midscene_progress(progress, run_id)
                        run.current_task = final_progress.get("currentTask")
                        run.current_action = final_progress.get("currentAction")
                        run.progress_json = json.dumps(final_progress, ensure_ascii=False)
                db.commit()


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


def sync_run_terminal_status(db: Session, run: Run) -> Run:
    if run.status != "running" or not run.request_id:
        return run

    try:
        result = _midscene_task_result(run.request_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Midscene task-result补偿同步失败，保持原状态 runId=%s requestId=%s error=%s",
            run.id,
            run.request_id,
            exc,
        )
        return run

    midscene_status = str(result.get("status") or "").strip().lower()
    run_status = _map_midscene_status_to_run(midscene_status)
    if run_status not in ("success", "failed", "cancelled"):
        return run

    error_message = _extract_error_message(result, midscene_status)
    run.status = run_status
    run.ended_at = datetime.utcnow()
    if run.started_at:
        run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
    run.error_message = error_message

    report_path = _extract_report_path(result)
    if report_path:
        run.report_path = report_path

    if run.total_tokens is None:
        try:
            progress = _midscene_task_progress(run.request_id)
        except Exception:  # noqa: BLE001
            progress = None
        run.total_tokens = _extract_total_tokens_from_progress(progress)
        if isinstance(progress, dict):
            final_progress = _compact_midscene_progress(progress, run.id)
            run.current_task = final_progress.get("currentTask")
            run.current_action = final_progress.get("currentAction")
            run.progress_json = json.dumps(final_progress, ensure_ascii=False)

    db.commit()
    db.refresh(run)
    logger.info(
        "Midscene task-result补偿同步成功 runId=%s requestId=%s midsceneStatus=%s runStatus=%s",
        run.id,
        run.request_id,
        midscene_status,
        run.status,
    )
    return run


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


def get_run_task_progress(run: Run) -> dict:
    if not run.request_id:
        return {"executionDump": None}
    raw_progress = _midscene_task_progress(run.request_id)
    return _summarize_midscene_task_progress(raw_progress, run.id)


def _midscene_task_result(request_id: str) -> dict:
    return _midscene_request("GET", f"/task-result/{request_id}")


def _midscene_cancel_task(request_id: str) -> dict:
    return _midscene_request("POST", f"/cancel/{request_id}")


def _midscene_request(method: str, path: str, json_body: dict | None = None) -> dict:
    timeout = httpx.Timeout(settings.midscene_timeout_sec)
    candidate_urls = _build_midscene_candidate_urls(path)
    last_error: Exception | None = None

    for index, url in enumerate(candidate_urls):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(method, url, json=json_body)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError(f"Invalid midsce response from {url}: {data}")
                if index > 0:
                    logger.warning("Midscene 请求已自动切换到备用地址 %s", url)
                return data
        except httpx.TimeoutException:
            raise
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if index < len(candidate_urls) - 1 and _should_retry_midscene_on_fallback(exc):
                logger.warning("Midscene 地址 %s 返回 %s，尝试备用地址", url, exc.response.status_code)
                continue
            raise RuntimeError(_format_midscene_request_error(method, url, exc)) from exc
        except httpx.RequestError as exc:
            last_error = exc
            if index < len(candidate_urls) - 1 and _should_retry_midscene_on_fallback(exc):
                logger.warning("Midscene 地址 %s 不可达，尝试备用地址: %s", url, exc)
                continue
            raise RuntimeError(_format_midscene_request_error(method, url, exc)) from exc

    if last_error is not None:
        raise RuntimeError(_format_midscene_request_error(method, candidate_urls[-1], last_error)) from last_error
    raise RuntimeError("Midscene 请求失败：未找到可用请求地址")


def _build_midscene_candidate_urls(path: str) -> list[str]:
    base_url = settings.midscene_base_url.rstrip("/")
    candidates = [f"{base_url}{path}"]
    parsed = urlparse(base_url)
    hostname = (parsed.hostname or "").strip().lower()
    port = parsed.port
    if hostname not in {"localhost", "127.0.0.1"} or port is None:
        return candidates

    for offset in range(1, MIDSCENE_PORT_FALLBACK_SPAN + 1):
        alt_port = port + offset
        netloc = _build_netloc_with_port(parsed, alt_port)
        alt_url = urlunparse(parsed._replace(netloc=netloc)).rstrip("/")
        candidates.append(f"{alt_url}{path}")
    return candidates


def _build_netloc_with_port(parsed, port: int) -> str:
    host = parsed.hostname or "localhost"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.username is not None:
        credentials = parsed.username
        if parsed.password is not None:
            credentials = f"{credentials}:{parsed.password}"
        return f"{credentials}@{host}:{port}"
    return f"{host}:{port}"


def _should_retry_midscene_on_fallback(exc: Exception) -> bool:
    if isinstance(exc, httpx.ConnectError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {502, 503, 504}
    return False


def _format_midscene_request_error(method: str, url: str, exc: Exception) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        reason = exc.response.reason_phrase or "HTTP error"
        return (
            f"Midscene 服务调用失败：{method} {url} 返回 {status_code} {reason}。"
            f"请确认 Android Playground 服务已启动，并检查 backend/.env 中 MIDSCENE_BASE_URL 是否与实际地址一致。"
            f"若 5800 端口被占用，服务可能自动切换到 5801 及后续端口。"
        )
    if isinstance(exc, httpx.ConnectError):
        return (
            f"无法连接 Midscene 服务：{host}。请先启动 Android Playground 服务，"
            f"或检查 backend/.env 中 MIDSCENE_BASE_URL 是否指向正确端口。"
            f"若 5800 端口被占用，服务可能自动切换到 5801 及后续端口。"
        )
    return f"Midscene 服务调用失败：{method} {url}，错误：{exc}"


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


def _extract_total_tokens_from_progress(progress: dict | None) -> int | None:
    if not isinstance(progress, dict):
        return None

    tasks = progress.get("tasks")
    if not isinstance(tasks, list):
        return None

    task_token_map: dict[str, int] = {}
    fallback_total = 0

    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        usage = task.get("usage")
        if not isinstance(usage, dict):
            continue

        total_value = usage.get("total_tokens")
        if total_value is None:
            total_value = usage.get("totalTokens")
        if total_value is None:
            prompt_tokens = usage.get("prompt_tokens") or usage.get("promptTokens") or 0
            completion_tokens = usage.get("completion_tokens") or usage.get("completionTokens") or 0
            total_value = prompt_tokens + completion_tokens

        try:
            total_tokens = int(total_value or 0)
        except (TypeError, ValueError):
            continue

        task_id = str(task.get("taskId") or task.get("id") or f"fallback-{index}")
        task_token_map[task_id] = total_tokens
        fallback_total += total_tokens

    if task_token_map:
        return sum(task_token_map.values())
    if fallback_total > 0:
        return fallback_total
    return None


def _summarize_midscene_task_progress(progress: dict, run_id: int) -> dict:
    if not isinstance(progress, dict):
        return {
            "runId": run_id,
            "executionDump": {"name": None, "logTime": None, "tasks": []},
        }

    execution_dump = progress.get("executionDump")
    source = execution_dump if isinstance(execution_dump, dict) else progress
    tasks = source.get("tasks")
    compact_tasks: list[dict] = []
    if isinstance(tasks, list):
        for task in tasks:
            if not isinstance(task, dict):
                continue
            compact_tasks.append(_summarize_midscene_task(task))

    return {
        "runId": run_id,
        "status": _map_midscene_status_to_run(str(progress.get("status") or "").lower()),
        "currentTask": progress.get("currentTask") or progress.get("current_task"),
        "currentAction": progress.get("currentAction") or progress.get("current_action"),
        "executionDump": {
            "name": source.get("name"),
            "logTime": source.get("logTime") or source.get("log_time"),
            "tasks": compact_tasks,
        },
    }


def _summarize_midscene_task(task: dict) -> dict:
    return {
        "taskId": task.get("taskId") or task.get("id"),
        "status": task.get("status"),
        "type": task.get("type"),
        "subType": task.get("subType"),
        "thought": _compact_midscene_value(task.get("thought")),
        "param": _compact_midscene_value(task.get("param")),
        "output": _compact_midscene_output(task.get("output")),
        "timing": _compact_midscene_value(task.get("timing")),
        "error": _compact_midscene_value(task.get("error")),
    }


def _compact_midscene_output(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None

    output: dict[str, object] = {}
    for key in ("log", "thought", "message", "error"):
        compact_value = _compact_midscene_value(value.get(key))
        if compact_value is not None:
            output[key] = compact_value

    actions = value.get("actions")
    if isinstance(actions, list):
        compact_actions = []
        for action in actions[:10]:
            if not isinstance(action, dict):
                continue
            compact_actions.append(
                {
                    "type": action.get("type"),
                    "thought": _compact_midscene_value(action.get("thought")),
                    "param": _compact_midscene_value(action.get("param")),
                }
            )
        if compact_actions:
            output["actions"] = compact_actions
        if len(actions) > len(compact_actions):
            output["actionCount"] = len(actions)

    return output or None


def _compact_midscene_value(value: object, *, depth: int = 0) -> object:
    if value is None:
        return None
    if depth >= 4:
        return _compact_midscene_scalar(value)
    if isinstance(value, str):
        return _compact_midscene_string(value)
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        compact_items = [
            compact_item
            for compact_item in (
                _compact_midscene_value(item, depth=depth + 1) for item in value[:10]
            )
            if compact_item is not None
        ]
        if len(value) > len(compact_items):
            compact_items.append(f"... truncated {len(value) - len(compact_items)} items")
        return compact_items
    if isinstance(value, dict):
        compact: dict[str, object] = {}
        for key, item in value.items():
            if _is_heavy_midscene_key(key):
                continue
            compact_item = _compact_midscene_value(item, depth=depth + 1)
            if compact_item is None:
                continue
            compact[str(key)] = compact_item
        return compact or None
    return _compact_midscene_scalar(value)


def _compact_midscene_scalar(value: object) -> object:
    if isinstance(value, str):
        return _compact_midscene_string(value)
    return str(value)


def _compact_midscene_string(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if text.startswith("data:image/"):
        return "[omitted image data]"
    max_length = 4000
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}... [truncated {len(text) - max_length} chars]"


def _is_heavy_midscene_key(key: object) -> bool:
    normalized = str(key).strip().lower()
    if not normalized:
        return False
    heavy_keys = {
        "base64",
        "screenshot",
        "screenshots",
        "uicontext",
        "recorder",
        "cache",
        "dom",
        "html",
        "snapshot",
        "snapshots",
        "before",
        "after",
        "image",
        "images",
        "video",
    }
    return normalized in heavy_keys


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
