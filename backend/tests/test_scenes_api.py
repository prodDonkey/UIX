from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.scenes import router as scenes_router
from app.api.scripts import router as scripts_router
from app.core.database import Base, get_db


def _build_test_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "test-scenes.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(scripts_router)
    app.include_router(scenes_router)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_scene_crud_and_script_binding(tmp_path: Path) -> None:
    client = _build_test_client(tmp_path)

    first_script = client.post(
        "/api/scripts",
        json={"name": "登录脚本", "content": "tasks:\n  - name: 登录\n", "source_type": "manual"},
    )
    second_script = client.post(
        "/api/scripts",
        json={"name": "签到脚本", "content": "tasks:\n  - name: 签到\n", "source_type": "ai"},
    )
    assert first_script.status_code == 201
    assert second_script.status_code == 201

    created_scene = client.post(
        "/api/scenes",
        json={"name": "前往服务-签到", "description": "登录后执行签到", "source_type": "manual"},
    )
    assert created_scene.status_code == 201
    scene_id = created_scene.json()["id"]

    bind_first = client.post(
        f"/api/scenes/{scene_id}/scripts",
        json={"script_id": first_script.json()["id"], "remark": "先登录"},
    )
    bind_second = client.post(
        f"/api/scenes/{scene_id}/scripts",
        json={"script_id": second_script.json()["id"], "remark": "再签到", "sort_order": 2},
    )
    assert bind_first.status_code == 201
    assert bind_second.status_code == 201

    detail = client.get(f"/api/scenes/{scene_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["script_count"] == 2
    assert [item["script"]["name"] for item in detail_payload["scripts"]] == ["登录脚本", "签到脚本"]

    relation_id = detail_payload["scripts"][0]["id"]
    updated_relation = client.put(
        f"/api/scenes/{scene_id}/scripts/{relation_id}",
        json={"sort_order": 3, "remark": "第一步：登录"},
    )
    assert updated_relation.status_code == 200
    assert updated_relation.json()["remark"] == "第一步：登录"

    scripts_list = client.get("/api/scripts")
    assert scripts_list.status_code == 200
    first_script_from_list = next(item for item in scripts_list.json() if item["id"] == first_script.json()["id"])
    assert first_script_from_list["scene_count"] == 1

    second_scene = client.post(
        "/api/scenes",
        json={"name": "复用场景", "description": "", "source_type": "manual"},
    )
    assert second_scene.status_code == 201
    second_scene_id = second_scene.json()["id"]

    reuse = client.post(
        f"/api/scenes/{second_scene_id}/scripts",
        json={"script_id": first_script.json()["id"], "remark": "复用登录脚本"},
    )
    assert reuse.status_code == 201

    script_detail = client.get(f"/api/scripts/{first_script.json()['id']}")
    assert script_detail.status_code == 200
    assert script_detail.json()["scene_count"] == 2
    assert {item["name"] for item in script_detail.json()["scenes"]} == {"前往服务-签到", "复用场景"}

    copied_scene = client.post(f"/api/scenes/{scene_id}/copy")
    assert copied_scene.status_code == 201
    copied_scene_payload = copied_scene.json()
    assert copied_scene_payload["name"] == "前往服务-签到-copy"
    assert len(copied_scene_payload["scripts"]) == 2

    deleted_relation = client.delete(f"/api/scenes/{scene_id}/scripts/{relation_id}")
    assert deleted_relation.status_code == 204

    deleted_scene = client.delete(f"/api/scenes/{scene_id}")
    assert deleted_scene.status_code == 204

    script_still_exists = client.get(f"/api/scripts/{first_script.json()['id']}")
    assert script_still_exists.status_code == 200
