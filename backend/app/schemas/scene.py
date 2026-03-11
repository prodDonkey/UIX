from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.script import ScriptRead


class SceneBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="")
    source_type: str = Field(default="manual")


class SceneCreate(SceneBase):
    pass


class SceneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    source_type: str | None = None


class SceneRead(SceneBase):
    id: int
    created_at: datetime
    updated_at: datetime
    script_count: int = 0

    class Config:
        from_attributes = True


class SceneScriptCreate(BaseModel):
    script_id: int = Field(gt=0)
    sort_order: int | None = Field(default=None, ge=1)
    remark: str = Field(default="")


class SceneScriptUpdate(BaseModel):
    sort_order: int | None = Field(default=None, ge=1)
    remark: str | None = None


class SceneScriptRead(BaseModel):
    id: int
    scene_id: int
    script_id: int
    sort_order: int
    remark: str
    created_at: datetime
    script: ScriptRead


class ScriptTaskRead(BaseModel):
    script_id: int
    task_index: int
    task_name: str
    continue_on_error: bool = False
    task_content: str


class SceneTaskItemCreate(BaseModel):
    script_id: int = Field(gt=0)
    task_index: int = Field(ge=0)
    remark: str = Field(default="")


class SceneTaskItemUpdate(BaseModel):
    sort_order: int | None = Field(default=None, ge=1)
    remark: str | None = None


class SceneTaskItemRead(BaseModel):
    id: int
    scene_id: int
    script_id: int
    scene_script_id: int | None = None
    task_index: int
    task_name_snapshot: str
    task_content_snapshot: str
    sort_order: int
    remark: str
    created_at: datetime
    script: ScriptRead


class SceneCompiledScriptRead(BaseModel):
    scene_id: int
    script_count: int
    task_count: int
    yaml: str


class SceneDetailRead(SceneRead):
    scripts: list[SceneScriptRead] = []
    task_items: list[SceneTaskItemRead] = []
