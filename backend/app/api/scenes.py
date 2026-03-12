from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scene import Scene
from app.models.scene_script import SceneScript
from app.models.scene_task_item import SceneTaskItem
from app.models.script import Script
from app.schemas.scene import (
    SceneCompiledScriptRead,
    SceneCreate,
    SceneDetailRead,
    SceneRead,
    SceneScriptCreate,
    SceneScriptRead,
    SceneScriptUpdate,
    SceneTaskItemCreate,
    SceneTaskItemRead,
    SceneTaskItemSyncResult,
    SceneTaskItemUpdate,
    SceneUpdate,
)
from app.schemas.script import ScriptRead
from app.services.scene_compiler import (
    SceneCompileError,
    compile_scene_script,
    dump_task_snapshot,
    extract_script_env,
    find_script_task,
    parse_script_tasks,
    scene_task_sync_status,
    task_snapshot_key,
)
from app.services.run_service import create_scene_run, start_run_async

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


def _next_task_sort_order(db: Session, scene_id: int) -> int:
    current_max = db.scalar(
        select(func.coalesce(func.max(SceneTaskItem.sort_order), 0)).where(SceneTaskItem.scene_id == scene_id)
    )
    return int(current_max or 0) + 1


def _script_read_payload(db: Session, script: Script) -> ScriptRead:
    return ScriptRead.model_validate(
        {
            "id": script.id,
            "name": script.name,
            "content": script.content,
            "source_type": script.source_type,
            "created_at": script.created_at,
            "updated_at": script.updated_at,
            "scene_count": db.scalar(select(func.count(SceneScript.id)).where(SceneScript.script_id == script.id)) or 0,
        }
    )


def _serialize_scene_task_item(db: Session, task_item: SceneTaskItem, script: Script) -> SceneTaskItemRead:
    sync_status, sync_message = scene_task_sync_status(
        script_content=script.content,
        task_index=task_item.task_index,
        task_name_snapshot=task_item.task_name_snapshot,
        task_content_snapshot=task_item.task_content_snapshot,
    )
    return SceneTaskItemRead.model_validate(
        {
            "id": task_item.id,
            "scene_id": task_item.scene_id,
            "script_id": task_item.script_id,
            "scene_script_id": task_item.scene_script_id,
            "task_index": task_item.task_index,
            "task_name_snapshot": task_item.task_name_snapshot,
            "task_content_snapshot": task_item.task_content_snapshot,
            "sort_order": task_item.sort_order,
            "remark": task_item.remark,
            "created_at": task_item.created_at,
            "sync_status": sync_status,
            "sync_message": sync_message,
            "script": _script_read_payload(db, script),
        }
    )


def _scene_task_items(db: Session, scene_id: int) -> list[SceneTaskItemRead]:
    items = list(
        db.scalars(
            select(SceneTaskItem)
            .where(SceneTaskItem.scene_id == scene_id)
            .order_by(SceneTaskItem.sort_order.asc(), SceneTaskItem.id.asc())
        ).all()
    )
    script_ids = [item.script_id for item in items]
    scripts = list(db.scalars(select(Script).where(Script.id.in_(script_ids))).all()) if script_ids else []
    script_map = {script.id: script for script in scripts}
    payload: list[SceneTaskItemRead] = []
    for item in items:
        script = script_map.get(item.script_id)
        if not script:
            continue
        payload.append(_serialize_scene_task_item(db, item, script))
    return payload


def _compiled_scene_script(db: Session, scene: Scene) -> SceneCompiledScriptRead:
    task_items = list(
        db.scalars(
            select(SceneTaskItem)
            .where(SceneTaskItem.scene_id == scene.id)
            .order_by(SceneTaskItem.sort_order.asc(), SceneTaskItem.id.asc())
        ).all()
    )
    if not task_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scene has no task items")

    first_script = db.get(Script, task_items[0].script_id)
    if not first_script:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scene task source script not found")

    try:
        yaml_content = compile_scene_script(
            extract_script_env(first_script.content),
            [item.task_content_snapshot for item in task_items],
        )
    except SceneCompileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SceneCompiledScriptRead(
        scene_id=scene.id,
        script_count=len({item.script_id for item in task_items}),
        task_count=len(task_items),
        yaml=yaml_content,
    )


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
                    "script": _script_read_payload(db, script),
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
            "task_items": _scene_task_items(db, scene.id),
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
            "script": _script_read_payload(db, script),
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
            "script": _script_read_payload(db, script),
        }
    )


@router.delete("/{scene_id}/scripts/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene_script(scene_id: int, relation_id: int, db: Session = Depends(get_db)) -> None:
    relation = _get_relation_or_404(db, scene_id, relation_id)
    related_task_items = list(
        db.scalars(select(SceneTaskItem).where(SceneTaskItem.scene_script_id == relation.id)).all()
    )
    for task_item in related_task_items:
        db.delete(task_item)
    db.delete(relation)
    db.commit()


@router.get("/{scene_id}/task-items", response_model=list[SceneTaskItemRead])
def list_scene_task_items(scene_id: int, db: Session = Depends(get_db)) -> list[SceneTaskItemRead]:
    _get_scene_or_404(db, scene_id)
    return _scene_task_items(db, scene_id)


@router.post("/{scene_id}/task-items", response_model=SceneTaskItemRead, status_code=status.HTTP_201_CREATED)
def add_scene_task_item(
    scene_id: int,
    payload: SceneTaskItemCreate,
    db: Session = Depends(get_db),
) -> SceneTaskItemRead:
    _get_scene_or_404(db, scene_id)
    script = db.get(Script, payload.script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    try:
        task_list = parse_script_tasks(script.content)
    except SceneCompileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    matched_task = next((item for item in task_list if item["task_index"] == payload.task_index), None)
    if not matched_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found in script")

    scene_script = db.scalar(
        select(SceneScript).where(SceneScript.scene_id == scene_id, SceneScript.script_id == payload.script_id)
    )

    task_item = SceneTaskItem(
        scene_id=scene_id,
        script_id=payload.script_id,
        scene_script_id=scene_script.id if scene_script else None,
        task_index=payload.task_index,
        task_name_snapshot=matched_task["task_name"],
        task_content_snapshot=dump_task_snapshot(matched_task["task"]),
        sort_order=_next_task_sort_order(db, scene_id),
        remark=payload.remark,
    )
    db.add(task_item)
    db.commit()
    db.refresh(task_item)
    return _serialize_scene_task_item(db, task_item, script)


@router.put("/{scene_id}/task-items/{item_id}", response_model=SceneTaskItemRead)
def update_scene_task_item(
    scene_id: int,
    item_id: int,
    payload: SceneTaskItemUpdate,
    db: Session = Depends(get_db),
) -> SceneTaskItemRead:
    task_item = db.get(SceneTaskItem, item_id)
    if not task_item or task_item.scene_id != scene_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene task item not found")
    if payload.sort_order is not None:
        task_item.sort_order = payload.sort_order
    if payload.remark is not None:
        task_item.remark = payload.remark
    db.commit()
    db.refresh(task_item)
    script = db.get(Script, task_item.script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    return _serialize_scene_task_item(db, task_item, script)


@router.delete("/{scene_id}/task-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene_task_item(scene_id: int, item_id: int, db: Session = Depends(get_db)) -> None:
    task_item = db.get(SceneTaskItem, item_id)
    if not task_item or task_item.scene_id != scene_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene task item not found")
    db.delete(task_item)
    db.commit()


@router.post("/{scene_id}/task-items/{item_id}/sync", response_model=SceneTaskItemRead)
def sync_scene_task_item(scene_id: int, item_id: int, db: Session = Depends(get_db)) -> SceneTaskItemRead:
    task_item = db.get(SceneTaskItem, item_id)
    if not task_item or task_item.scene_id != scene_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene task item not found")

    script = db.get(Script, task_item.script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    matched_task = find_script_task(script.content, task_item.task_index)
    if not matched_task:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task not found in current script")

    task_item.task_name_snapshot = matched_task["task_name"]
    task_item.task_content_snapshot = dump_task_snapshot(matched_task["task"])
    db.commit()
    db.refresh(task_item)
    return _serialize_scene_task_item(db, task_item, script)


@router.post("/{scene_id}/task-items/sync", response_model=SceneTaskItemSyncResult)
def sync_scene_task_items(scene_id: int, db: Session = Depends(get_db)) -> SceneTaskItemSyncResult:
    _get_scene_or_404(db, scene_id)
    items = list(
        db.scalars(
            select(SceneTaskItem)
            .where(SceneTaskItem.scene_id == scene_id)
            .order_by(SceneTaskItem.sort_order.asc(), SceneTaskItem.id.asc())
        ).all()
    )
    if not items:
        return SceneTaskItemSyncResult(updated_count=0, missing_count=0, task_items=[])

    script_ids = {item.script_id for item in items}
    scripts = list(db.scalars(select(Script).where(Script.id.in_(script_ids))).all())
    script_map = {script.id: script for script in scripts}

    updated_count = 0
    missing_count = 0
    for item in items:
        script = script_map.get(item.script_id)
        if not script:
            missing_count += 1
            continue
        matched_task = find_script_task(script.content, item.task_index)
        if not matched_task:
            missing_count += 1
            continue
        next_name = matched_task["task_name"]
        next_snapshot = dump_task_snapshot(matched_task["task"])
        if next_name == item.task_name_snapshot and task_snapshot_key(next_snapshot) == task_snapshot_key(
            item.task_content_snapshot
        ):
            continue
        item.task_name_snapshot = next_name
        item.task_content_snapshot = next_snapshot
        updated_count += 1

    db.commit()
    return SceneTaskItemSyncResult(
        updated_count=updated_count,
        missing_count=missing_count,
        task_items=_scene_task_items(db, scene_id),
    )


@router.get("/{scene_id}/compiled-script", response_model=SceneCompiledScriptRead)
def get_scene_compiled_script(scene_id: int, db: Session = Depends(get_db)) -> SceneCompiledScriptRead:
    scene = _get_scene_or_404(db, scene_id)
    return _compiled_scene_script(db, scene)


@router.post("/{scene_id}/runs", status_code=status.HTTP_201_CREATED)
def create_scene_run_task(scene_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        run = create_scene_run(db, scene_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail in {"Scene not found"} else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    start_run_async(run.id)
    return {"run_id": run.id}
