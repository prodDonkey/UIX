from datetime import datetime

from pydantic import BaseModel, Field


class ScriptBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1)
    source_type: str = Field(default="manual")


class ScriptCreate(ScriptBase):
    pass


class ScriptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    content: str | None = Field(default=None, min_length=1)
    source_type: str | None = Field(default=None)


class ScriptRead(ScriptBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScriptValidateRequest(BaseModel):
    content: str = Field(min_length=1)


class ScriptValidateResponse(BaseModel):
    valid: bool
    line: int | None = None
    column: int | None = None
    message: str | None = None
