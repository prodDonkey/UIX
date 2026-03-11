from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scene import Scene
from app.models.scene_script import SceneScript
from app.models.script import Script
from app.schemas.scene import (
    SceneCreate,
    SceneDetailRead,
    SceneRead,
    SceneScriptCreate,
    SceneScriptRead,
    SceneScriptUpdate,
    SceneUpdate,
)
from app.schemas.script import ScriptRead

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


def _scene_list_stmt() -> Select[tuple[Scene, int]]:
    return (
        select(Scene, func.count(SceneScript.id).label("script_count"))
        .outerjoin(SceneScript, SceneScript.scene_id == Scene.id)
        .group_by(Scene.id)
        .order_by(Scene.updated_at.desc())
    )


def _serialize_scene(scene: Scene, script_count: int = 0) -> SceneRead:
    return SceneRead.model_validate(
        {
            "id": scene.id,
            "name": scene.name,
            "description": scene.description,
            "source_type": scene.source_type,
            "created_at": scene.created_at,
            "updated_at": scene.updated_at,
            "script_count": script_count,
        }
    )


def _get_scene_or_404(db: Session, scene_id: int) -> Scene:
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
    return scene


def _get_relation_or_404(db: Session, scene_id: int, relation_id: int) -> SceneScript:
    relation = db.get(SceneScript, relation_id)
    if not relation or relation.scene_id != scene_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene script relation not found")
    return relation


def _next_sort_order(db: Session, scene_id: int) -> int:
    current_max = db.scalar(
        select(func.coalesce(func.max(SceneScript.sort_order), 0)).where(SceneScript.scene_id == scene_id)
    )
    return int(current_max or 0) + 1


def _build_scene_detail(db: Session, scene: Scene) -> SceneDetailRead:
    script_count = db.scalar(select(func.count(SceneScript.id)).where(SceneScript.scene_id == scene.id)) or 0
    relations = list(
        db.scalars(
            select(SceneScript)
            .where(SceneScript.scene_id == scene.id)
            .order_by(SceneScript.sort_order.asc(), SceneScript.id.asc())
        ).all()
    )
    script_ids = [relation.script_id for relation in relations]
    scripts = list(db.scalars(select(Script).where(Script.id.in_(script_ids))).all()) if script_ids else []
    script_map = {script.id: script for script in scripts}

    relation_payload: list[SceneScriptRead] = []
    for relation in relations:
        script = script_map.get(relation.script_id)
        if not script:
            continue
        relation_payload.append(
            SceneScriptRead.model_validate(
                {
                    "id": relation.id,
                    "scene_id": relation.scene_id,
                    "script_id": relation.script_id,
                    "sort_order": relation.sort_order,
                    "remark": relation.remark,
                    "created_at": relation.created_at,
                    "script": ScriptRead.model_validate(
                        {
                            "id": script.id,
                            "name": script.name,
                            "content": script.content,
                            "source_type": script.source_type,
                            "created_at": script.created_at,
                            "updated_at": script.updated_at,
                            "scene_count": db.scalar(
                                select(func.count(SceneScript.id)).where(SceneScript.script_id == script.id)
                            )
                            or 0,
                        }
                    ),
                }
            )
        )

    return SceneDetailRead.model_validate(
        {
            "id": scene.id,
            "name": scene.name,
            "description": scene.description,
            "source_type": scene.source_type,
            "created_at": scene.created_at,
            "updated_at": scene.updated_at,
            "script_count": script_count,
            "scripts": relation_payload,
        }
    )


@router.get("", response_model=list[SceneRead])
def list_scenes(db: Session = Depends(get_db)) -> list[SceneRead]:
    return [_serialize_scene(scene, script_count) for scene, script_count in db.execute(_scene_list_stmt()).all()]


@router.post("", response_model=SceneRead, status_code=status.HTTP_201_CREATED)
def create_scene(payload: SceneCreate, db: Session = Depends(get_db)) -> SceneRead:
    scene = Scene(name=payload.name, description=payload.description, source_type=payload.source_type)
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return _serialize_scene(scene, script_count=0)


@router.post("/{scene_id}/copy", response_model=SceneDetailRead, status_code=status.HTTP_201_CREATED)
def copy_scene(scene_id: int, db: Session = Depends(get_db)) -> SceneDetailRead:
    origin = _get_scene_or_404(db, scene_id)
    copied = Scene(
        name=f"{origin.name}-copy",
        description=origin.description,
        source_type=origin.source_type,
    )
    db.add(copied)
    db.flush()

    origin_relations = list(
        db.scalars(
            select(SceneScript)
            .where(SceneScript.scene_id == scene_id)
            .order_by(SceneScript.sort_order.asc(), SceneScript.id.asc())
        ).all()
    )
    for relation in origin_relations:
        db.add(
            SceneScript(
                scene_id=copied.id,
                script_id=relation.script_id,
                sort_order=relation.sort_order,
                remark=relation.remark,
            )
        )

    db.commit()
    db.refresh(copied)
    return _build_scene_detail(db, copied)


@router.get("/{scene_id}", response_model=SceneDetailRead)
def get_scene(scene_id: int, db: Session = Depends(get_db)) -> SceneDetailRead:
    scene = _get_scene_or_404(db, scene_id)
    return _build_scene_detail(db, scene)


@router.put("/{scene_id}", response_model=SceneRead)
def update_scene(scene_id: int, payload: SceneUpdate, db: Session = Depends(get_db)) -> SceneRead:
    scene = _get_scene_or_404(db, scene_id)
    if payload.name is not None:
        scene.name = payload.name
    if payload.description is not None:
        scene.description = payload.description
    if payload.source_type is not None:
        scene.source_type = payload.source_type
    db.commit()
    db.refresh(scene)
    script_count = db.scalar(select(func.count(SceneScript.id)).where(SceneScript.scene_id == scene.id)) or 0
    return _serialize_scene(scene, script_count=script_count)


@router.delete("/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene(scene_id: int, db: Session = Depends(get_db)) -> None:
    scene = _get_scene_or_404(db, scene_id)
    db.delete(scene)
    db.commit()


@router.post("/{scene_id}/scripts", response_model=SceneScriptRead, status_code=status.HTTP_201_CREATED)
def add_scene_script(scene_id: int, payload: SceneScriptCreate, db: Session = Depends(get_db)) -> SceneScriptRead:
    _get_scene_or_404(db, scene_id)
    script = db.get(Script, payload.script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    existing_relation = db.scalar(
        select(SceneScript).where(SceneScript.scene_id == scene_id, SceneScript.script_id == payload.script_id)
    )
    if existing_relation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Script already added to scene")

    relation = SceneScript(
        scene_id=scene_id,
        script_id=payload.script_id,
        sort_order=payload.sort_order or _next_sort_order(db, scene_id),
        remark=payload.remark,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)

    return SceneScriptRead.model_validate(
        {
            "id": relation.id,
            "scene_id": relation.scene_id,
            "script_id": relation.script_id,
            "sort_order": relation.sort_order,
            "remark": relation.remark,
            "created_at": relation.created_at,
            "script": ScriptRead.model_validate(
                {
                    "id": script.id,
                    "name": script.name,
                    "content": script.content,
                    "source_type": script.source_type,
                    "created_at": script.created_at,
                    "updated_at": script.updated_at,
                    "scene_count": db.scalar(
                        select(func.count(SceneScript.id)).where(SceneScript.script_id == script.id)
                    )
                    or 0,
                }
            ),
        }
    )


@router.put("/{scene_id}/scripts/{relation_id}", response_model=SceneScriptRead)
def update_scene_script(
    scene_id: int,
    relation_id: int,
    payload: SceneScriptUpdate,
    db: Session = Depends(get_db),
) -> SceneScriptRead:
    relation = _get_relation_or_404(db, scene_id, relation_id)
    if payload.sort_order is not None:
        relation.sort_order = payload.sort_order
    if payload.remark is not None:
        relation.remark = payload.remark
    db.commit()
    db.refresh(relation)

    script = db.get(Script, relation.script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    return SceneScriptRead.model_validate(
        {
            "id": relation.id,
            "scene_id": relation.scene_id,
            "script_id": relation.script_id,
            "sort_order": relation.sort_order,
            "remark": relation.remark,
            "created_at": relation.created_at,
            "script": ScriptRead.model_validate(
                {
                    "id": script.id,
                    "name": script.name,
                    "content": script.content,
                    "source_type": script.source_type,
                    "created_at": script.created_at,
                    "updated_at": script.updated_at,
                    "scene_count": db.scalar(
                        select(func.count(SceneScript.id)).where(SceneScript.script_id == script.id)
                    )
                    or 0,
                }
            ),
        }
    )


@router.delete("/{scene_id}/scripts/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene_script(scene_id: int, relation_id: int, db: Session = Depends(get_db)) -> None:
    relation = _get_relation_or_404(db, scene_id, relation_id)
    db.delete(relation)
    db.commit()
