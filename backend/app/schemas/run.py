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

    class Config:
        from_attributes = True


class RunListRead(BaseModel):
    """
    运行列表轻量响应：
    仅返回列表页需要字段，避免把 progress_json 等大字段传输到前端导致慢查询/慢序列化。
    """

    id: int
    script_id: int
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None
    error_message: str | None

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
