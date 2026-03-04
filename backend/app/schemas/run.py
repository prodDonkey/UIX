from datetime import datetime

from pydantic import BaseModel, Field


class RunCreateRequest(BaseModel):
    script_id: int = Field(gt=0)


class RunRead(BaseModel):
    id: int
    script_id: int
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None
    log_path: str | None
    report_path: str | None
    summary_path: str | None
    error_message: str | None
    current_task: str | None = None
    current_action: str | None = None
    progress_json: str | None = None

    class Config:
        from_attributes = True


class RunLogsResponse(BaseModel):
    content: str


class RunProgressRead(BaseModel):
    run_id: int
    status: str
    current_task: str | None = None
    current_action: str | None = None
    progress_json: str | None = None
    updated_at: datetime | None = None
