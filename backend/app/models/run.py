from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[int | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_task: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_name_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    script_name_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    script_content_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    script_updated_at_snapshot: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
