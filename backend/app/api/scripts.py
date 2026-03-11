from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scene import Scene
from app.models.scene_script import SceneScript
from app.models.script import Script
from app.models.script_version import ScriptVersion
from app.schemas.script import (
    ScriptCreate,
    ScriptRead,
    ScriptSceneReference,
    ScriptUpdate,
    ScriptValidateRequest,
    ScriptValidateResponse,
)
from app.services.yaml_validator import validate_yaml_content

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


def _script_scene_references(db: Session, script_id: int) -> list[ScriptSceneReference]:
    scenes = list(
        db.scalars(
            select(Scene).join(SceneScript, SceneScript.scene_id == Scene.id).where(SceneScript.script_id == script_id)
        ).all()
    )
    return [ScriptSceneReference(id=scene.id, name=scene.name) for scene in scenes]


@router.get("", response_model=list[ScriptRead])
def list_scripts(db: Session = Depends(get_db)) -> list[ScriptRead]:
    stmt = (
        select(Script, func.count(SceneScript.id).label("scene_count"))
        .outerjoin(SceneScript, SceneScript.script_id == Script.id)
        .group_by(Script.id)
        .order_by(Script.updated_at.desc())
    )
    return [
        ScriptRead.model_validate(
            {
                "id": script.id,
                "name": script.name,
                "content": script.content,
                "source_type": script.source_type,
                "created_at": script.created_at,
                "updated_at": script.updated_at,
                "scene_count": scene_count,
                "scenes": [],
            }
        )
        for script, scene_count in db.execute(stmt).all()
    ]


@router.get("/{script_id}", response_model=ScriptRead)
def get_script(script_id: int, db: Session = Depends(get_db)) -> ScriptRead:
    script = db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    scene_count = db.scalar(select(func.count(SceneScript.id)).where(SceneScript.script_id == script_id)) or 0
    return ScriptRead.model_validate(
        {
            "id": script.id,
            "name": script.name,
            "content": script.content,
            "source_type": script.source_type,
            "created_at": script.created_at,
            "updated_at": script.updated_at,
            "scene_count": scene_count,
            "scenes": _script_scene_references(db, script_id),
        }
    )


@router.post("", response_model=ScriptRead, status_code=status.HTTP_201_CREATED)
def create_script(payload: ScriptCreate, db: Session = Depends(get_db)) -> ScriptRead:
    script = Script(name=payload.name, content=payload.content, source_type=payload.source_type)
    db.add(script)
    db.flush()

    version = ScriptVersion(script_id=script.id, version_no=1, content=script.content)
    db.add(version)

    db.commit()
    db.refresh(script)
    return ScriptRead.model_validate(
        {
            "id": script.id,
            "name": script.name,
            "content": script.content,
            "source_type": script.source_type,
            "created_at": script.created_at,
            "updated_at": script.updated_at,
            "scene_count": 0,
            "scenes": [],
        }
    )


@router.put("/{script_id}", response_model=ScriptRead)
def update_script(script_id: int, payload: ScriptUpdate, db: Session = Depends(get_db)) -> ScriptRead:
    script = db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    if payload.name is not None:
        script.name = payload.name
    if payload.content is not None:
        script.content = payload.content
    if payload.source_type is not None:
        script.source_type = payload.source_type

    current_version = db.scalar(
        select(func.coalesce(func.max(ScriptVersion.version_no), 0)).where(ScriptVersion.script_id == script_id)
    )
    new_version = ScriptVersion(
        script_id=script.id,
        version_no=(current_version or 0) + 1,
        content=script.content,
    )
    db.add(new_version)

    db.commit()
    db.refresh(script)
    scene_count = db.scalar(select(func.count(SceneScript.id)).where(SceneScript.script_id == script_id)) or 0
    return ScriptRead.model_validate(
        {
            "id": script.id,
            "name": script.name,
            "content": script.content,
            "source_type": script.source_type,
            "created_at": script.created_at,
            "updated_at": script.updated_at,
            "scene_count": scene_count,
            "scenes": _script_scene_references(db, script_id),
        }
    )


@router.delete("/{script_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_script(script_id: int, db: Session = Depends(get_db)) -> None:
    script = db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    db.delete(script)
    db.commit()


@router.post("/{script_id}/copy", response_model=ScriptRead, status_code=status.HTTP_201_CREATED)
def copy_script(script_id: int, db: Session = Depends(get_db)) -> ScriptRead:
    origin = db.get(Script, script_id)
    if not origin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    copied = Script(
        name=f"{origin.name}-copy",
        content=origin.content,
        source_type=origin.source_type,
    )
    db.add(copied)
    db.flush()

    db.add(ScriptVersion(script_id=copied.id, version_no=1, content=copied.content))
    db.commit()
    db.refresh(copied)
    return ScriptRead.model_validate(
        {
            "id": copied.id,
            "name": copied.name,
            "content": copied.content,
            "source_type": copied.source_type,
            "created_at": copied.created_at,
            "updated_at": copied.updated_at,
            "scene_count": 0,
            "scenes": [],
        }
    )


@router.post("/{script_id}/validate", response_model=ScriptValidateResponse)
def validate_script(
    script_id: int,
    payload: ScriptValidateRequest,
    db: Session = Depends(get_db),
) -> ScriptValidateResponse:
    if not db.get(Script, script_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    result = validate_yaml_content(payload.content)
    return ScriptValidateResponse(
        valid=result.valid,
        line=result.line,
        column=result.column,
        message=result.message,
    )
