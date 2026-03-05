import logging
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.run import Run
from app.schemas.run import (
    RunCreateRequest,
    RunListRead,
    RunLogsResponse,
    RunProgressRead,
    RunRead,
    RunRemarkUpdateRequest,
    RunStarUpdateRequest,
)
from app.services.run_service import (
    cancel_run,
    create_run,
    get_report_path,
    list_runs,
    read_run_logs,
    start_run_async,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])
logger = logging.getLogger("uvicorn.error")


@router.get("", response_model=list[RunListRead])
def get_runs(
    script_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[Run]:
    return list_runs(db, script_id=script_id, limit=limit)


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
def create_run_task(payload: RunCreateRequest, db: Session = Depends(get_db)) -> Run:
    try:
        run = create_run(db, payload.script_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    start_run_async(run.id)
    return run


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: int, db: Session = Depends(get_db)) -> Run:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/{run_id}/progress", response_model=RunProgressRead)
def get_run_progress(run_id: int, db: Session = Depends(get_db)) -> RunProgressRead:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    compact_progress_json = _compact_progress_json(run.progress_json)
    return RunProgressRead(
        run_id=run.id,
        status=run.status,
        current_task=run.current_task,
        current_action=run.current_action,
        progress_json=compact_progress_json,
        updated_at=run.ended_at or run.started_at,
    )


@router.get("/{run_id}/logs", response_model=RunLogsResponse)
def get_run_logs(
    run_id: int,
    tail_bytes: int = Query(default=50_000, ge=1_000, le=500_000),
    db: Session = Depends(get_db),
) -> RunLogsResponse:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return RunLogsResponse(content=read_run_logs(run, tail_bytes=tail_bytes))


@router.post("/{run_id}/cancel", response_model=RunRead)
def cancel_run_task(run_id: int, db: Session = Depends(get_db)) -> Run:
    run = cancel_run(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.patch("/{run_id}/remark", response_model=RunRead)
def update_run_remark(run_id: int, payload: RunRemarkUpdateRequest, db: Session = Depends(get_db)) -> Run:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    # 备注支持清空，统一将空白字符串落为 null，便于前端判断“无备注”。
    normalized_remark = payload.remark.strip() if isinstance(payload.remark, str) else None
    run.remark = normalized_remark or None
    db.commit()
    db.refresh(run)
    logger.info("运行备注已更新 runId=%s hasRemark=%s", run_id, bool(run.remark))
    return run


@router.patch("/{run_id}/star", response_model=RunRead)
def update_run_star(run_id: int, payload: RunStarUpdateRequest, db: Session = Depends(get_db)) -> Run:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    run.is_starred = payload.is_starred
    db.commit()
    db.refresh(run)
    logger.info("运行星标已更新 runId=%s isStarred=%s", run_id, run.is_starred)
    return run


@router.get("/{run_id}/report")
def get_run_report(
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    report_path = get_report_path(run)
    if not report_path:
        return {"report_path": None, "preview_url": None, "download_url": None}
    preview_url = str(request.url_for("get_run_report_file", run_id=run_id))
    download_url = f"{preview_url}?download=1"
    return {
        "report_path": report_path,
        "preview_url": preview_url,
        "download_url": download_url,
    }


@router.get("/{run_id}/report/file", name="get_run_report_file")
def get_run_report_file(
    run_id: int,
    download: int = Query(default=0),
    db: Session = Depends(get_db),
) -> FileResponse:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    report_path = get_report_path(run)
    if not report_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    report_file = Path(report_path).resolve()
    allowed_root = Path(settings.report_root_dir).resolve()
    if not report_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found")
    if not report_file.is_relative_to(allowed_root):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Report path not allowed")

    if download:
        return FileResponse(path=report_file, filename=report_file.name, media_type="text/html")
    return FileResponse(
        path=report_file,
        filename=report_file.name,
        media_type="text/html",
        headers={"Content-Disposition": f'inline; filename="{report_file.name}"'},
    )


def _compact_progress_json(progress_json: str | None) -> str | None:
    """
    兼容历史数据：若 progress_json 含有超大 uiContext/screenshot，返回瘦身后的 JSON 字符串。
    """
    if not progress_json:
        return progress_json
    try:
        payload = json.loads(progress_json)
    except Exception:  # noqa: BLE001
        return progress_json
    if not isinstance(payload, dict):
        return progress_json

    execution_dump = payload.get("executionDump")
    if not isinstance(execution_dump, dict):
        return progress_json

    tasks = execution_dump.get("tasks")
    if not isinstance(tasks, list):
        return progress_json

    compact_tasks: list[dict] = []
    changed = False
    for task in tasks[-20:]:
        if not isinstance(task, dict):
            continue
        if "uiContext" in task or "recorder" in task:
            changed = True
        compact_tasks.append(
            {
                "taskId": task.get("taskId"),
                "status": task.get("status"),
                "type": task.get("type"),
                "subType": task.get("subType"),
                "thought": task.get("thought"),
                "param": task.get("param"),
                "timing": task.get("timing"),
                "error": task.get("error"),
            }
        )
    if not changed and len(compact_tasks) == len(tasks):
        return progress_json

    compact_payload = {
        "runId": payload.get("runId"),
        "status": payload.get("status"),
        "currentTask": payload.get("currentTask"),
        "currentAction": payload.get("currentAction"),
        "completed": payload.get("completed"),
        "total": payload.get("total"),
        "updatedAt": payload.get("updatedAt"),
        "executionDump": {
            "logTime": execution_dump.get("logTime"),
            "name": execution_dump.get("name"),
            "tasks": compact_tasks,
        },
    }
    return json.dumps(compact_payload, ensure_ascii=False)
