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

    class Config:
        from_attributes = True


class RunLogsResponse(BaseModel):
    content: str

