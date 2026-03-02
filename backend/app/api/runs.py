from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.run import Run
from app.schemas.run import RunCreateRequest, RunLogsResponse, RunRead
from app.services.run_service import (
    cancel_run,
    create_run,
    get_report_path,
    list_runs,
    read_run_logs,
    start_run_async,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunRead])
def get_runs(
    script_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
) -> list[Run]:
    return list_runs(db, script_id=script_id)


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


@router.get("/{run_id}/logs", response_model=RunLogsResponse)
def get_run_logs(run_id: int, db: Session = Depends(get_db)) -> RunLogsResponse:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return RunLogsResponse(content=read_run_logs(run))


@router.post("/{run_id}/cancel", response_model=RunRead)
def cancel_run_task(run_id: int, db: Session = Depends(get_db)) -> Run:
    run = cancel_run(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/{run_id}/report")
def get_run_report(run_id: int, db: Session = Depends(get_db)) -> dict[str, str | None]:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return {"report_path": get_report_path(run)}

