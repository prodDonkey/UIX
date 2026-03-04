from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import threading
import time
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.run import Run
from app.models.script import Script

_ACTIVE_PROCESSES: dict[int, subprocess.Popen[str]] = {}
_ACTIVE_LOCK: Final = threading.Lock()


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

    # Idempotent cancel for queued/running tasks.
    if run.status in ("queued", "running"):
        run.status = "cancelled"
        run.ended_at = datetime.utcnow()
        if run.started_at:
            run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
        db.commit()
        db.refresh(run)

    with _ACTIVE_LOCK:
        proc = _ACTIVE_PROCESSES.get(run_id)
    if proc and proc.poll() is None:
        _terminate_process_tree(proc)
    return run


def _execute_run(run_id: int) -> None:
    db = SessionLocal()
    try:
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
        log_path = logs_dir / f"run-{run.id}.log"
        yaml_path.write_text(script.content)

        run.status = "running"
        run.started_at = datetime.utcnow()
        run.log_path = str(log_path.resolve())
        db.commit()
        db.refresh(run)
        if run.status == "cancelled":
            return

        command = shlex.split(settings.run_command_prefix) + [str(yaml_path.resolve())]
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(Path.cwd()),
            start_new_session=True,
        )
        with _ACTIVE_LOCK:
            _ACTIVE_PROCESSES[run.id] = proc

        report_path: str | None = None
        summary_path: str | None = None
        recent_lines: list[str] = []

        with log_path.open("w", encoding="utf-8") as log_file:
            if proc.stdout:
                for line in proc.stdout:
                    log_file.write(line)
                    log_file.flush()
                    stripped = line.strip()
                    if stripped:
                        recent_lines.append(stripped)
                        if len(recent_lines) > 200:
                            recent_lines = recent_lines[-200:]
                    if "report:" in stripped and ".html" in stripped:
                        report_path = stripped.split("report:", 1)[1].strip()
                    if stripped.startswith("Summary:") and ".json" in stripped:
                        summary_path = stripped.split("Summary:", 1)[1].strip()

        exit_code = proc.wait()
        with _ACTIVE_LOCK:
            _ACTIVE_PROCESSES.pop(run.id, None)

        db.refresh(run)
        if run.status == "cancelled":
            return

        run.ended_at = datetime.utcnow()
        if run.started_at:
            run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
        run.report_path = report_path
        run.summary_path = summary_path

        if exit_code == 0:
            run.status = "success"
            run.error_message = None
        else:
            run.status = "failed"
            extracted_error = _extract_midscene_error_message(recent_lines)
            run.error_message = extracted_error or f"Command exited with code {exit_code}"

        db.commit()
    except Exception as exc:  # noqa: BLE001
        run = db.get(Run, run_id)
        if run:
            run.status = "failed"
            run.ended_at = datetime.utcnow()
            if run.started_at:
                run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
            run.error_message = str(exc)
            db.commit()
    finally:
        db.close()


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


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        for _ in range(20):
            if proc.poll() is not None:
                return
            time.sleep(0.1)
        os.killpg(pgid, signal.SIGKILL)
    except Exception:  # noqa: BLE001
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            return


def _extract_midscene_error_message(lines: list[str]) -> str | None:
    if not lines:
        return None

    # Prefer explicit stack-style error lines near the end.
    for line in reversed(lines):
        if line.startswith("Error: "):
            return line.removeprefix("Error: ").strip()

    # Midscene usually emits "error:" section lines.
    for line in reversed(lines):
        lower_line = line.lower()
        if lower_line.startswith("error:"):
            value = line.split(":", 1)[1].strip()
            if value:
                return value

    # Fallback for common android screenshot issue pattern.
    screenshot_error = re.compile(r"Fallback screenshot validation failed:[^\n]*", re.IGNORECASE)
    for line in reversed(lines):
        match = screenshot_error.search(line)
        if match:
            return match.group(0).strip()

    return None
