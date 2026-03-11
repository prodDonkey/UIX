from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SceneTaskItem(Base):
    __tablename__ = "scene_task_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id", ondelete="CASCADE"), index=True)
    scene_script_id: Mapped[int | None] = mapped_column(
        ForeignKey("scene_scripts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_index: Mapped[int] = mapped_column(Integer, nullable=False)
    task_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    task_content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
