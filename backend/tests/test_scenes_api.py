from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.runs import router as runs_router
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
    app.include_router(runs_router)

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


def test_scene_task_items_and_compiled_script(tmp_path: Path) -> None:
    client = _build_test_client(tmp_path)

    script_response = client.post(
        "/api/scripts",
        json={
            "name": "回收脚本",
            "content": (
                "android:\n"
                "  deviceId: ''\n"
                "tasks:\n"
                "  - name: 前往服务\n"
                "    flow:\n"
                "      - aiAction: 点击待上门订单\n"
                "  - name: 点击预约点签到\n"
                "    flow:\n"
                "      - aiAction: 点击立即签到按钮\n"
            ),
            "source_type": "manual",
        },
    )
    assert script_response.status_code == 201
    script_id = script_response.json()["id"]

    scene_response = client.post(
        "/api/scenes",
        json={"name": "回收一段流程", "description": "任务级编排", "source_type": "manual"},
    )
    assert scene_response.status_code == 201
    scene_id = scene_response.json()["id"]

    bind_response = client.post(f"/api/scenes/{scene_id}/scripts", json={"script_id": script_id, "remark": "来源脚本"})
    assert bind_response.status_code == 201

    script_tasks = client.get(f"/api/scripts/{script_id}/tasks")
    assert script_tasks.status_code == 200
    task_payload = script_tasks.json()
    assert [item["task_name"] for item in task_payload] == ["前往服务", "点击预约点签到"]

    first_item = client.post(
        f"/api/scenes/{scene_id}/task-items",
        json={"script_id": script_id, "task_index": 0, "remark": "先前往服务"},
    )
    second_item = client.post(
        f"/api/scenes/{scene_id}/task-items",
        json={"script_id": script_id, "task_index": 1, "remark": "再签到"},
    )
    assert first_item.status_code == 201
    assert second_item.status_code == 201

    detail = client.get(f"/api/scenes/{scene_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert [item["task_name_snapshot"] for item in detail_payload["task_items"]] == ["前往服务", "点击预约点签到"]

    first_item_id = detail_payload["task_items"][0]["id"]
    second_item_id = detail_payload["task_items"][1]["id"]
    moved = client.put(
        f"/api/scenes/{scene_id}/task-items/{first_item_id}",
        json={"sort_order": 2, "remark": "第二步：前往服务"},
    )
    moved_peer = client.put(
        f"/api/scenes/{scene_id}/task-items/{second_item_id}",
        json={"sort_order": 1, "remark": "第一步：签到"},
    )
    assert moved.status_code == 200
    assert moved_peer.status_code == 200

    compiled = client.get(f"/api/scenes/{scene_id}/compiled-script")
    assert compiled.status_code == 200
    compiled_payload = compiled.json()
    assert compiled_payload["task_count"] == 2
    assert "name: 点击预约点签到" in compiled_payload["yaml"]
    assert compiled_payload["yaml"].index("name: 点击预约点签到") < compiled_payload["yaml"].index("name: 前往服务")

    deleted = client.delete(f"/api/scenes/{scene_id}/task-items/{second_item_id}")
    assert deleted.status_code == 204

    item_list = client.get(f"/api/scenes/{scene_id}/task-items")
    assert item_list.status_code == 200
    assert len(item_list.json()) == 1


def test_scene_run_creates_run_with_compiled_snapshot(tmp_path: Path, monkeypatch) -> None:
    client = _build_test_client(tmp_path)
    monkeypatch.setattr("app.api.scenes.start_run_async", lambda run_id: None)

    script_response = client.post(
        "/api/scripts",
        json={
            "name": "回收脚本",
            "content": (
                "android:\n"
                "  deviceId: ''\n"
                "tasks:\n"
                "  - name: 前往服务\n"
                "    flow:\n"
                "      - aiAction: 点击待上门订单\n"
            ),
            "source_type": "manual",
        },
    )
    assert script_response.status_code == 201
    script_id = script_response.json()["id"]

    scene_response = client.post(
        "/api/scenes",
        json={"name": "回收一段流程", "description": "场景执行", "source_type": "manual"},
    )
    assert scene_response.status_code == 201
    scene_id = scene_response.json()["id"]

    bind_response = client.post(f"/api/scenes/{scene_id}/scripts", json={"script_id": script_id, "remark": "来源脚本"})
    assert bind_response.status_code == 201

    add_task = client.post(
        f"/api/scenes/{scene_id}/task-items",
        json={"script_id": script_id, "task_index": 0, "remark": "执行 task"},
    )
    assert add_task.status_code == 201

    created_run = client.post(f"/api/scenes/{scene_id}/runs")
    assert created_run.status_code == 201
    run_id = created_run.json()["run_id"]

    run_detail = client.get(f"/api/runs/{run_id}")
    assert run_detail.status_code == 200
    payload = run_detail.json()
    assert payload["scene_id"] == scene_id
    assert payload["scene_name_snapshot"] == "回收一段流程"
    assert payload["script_id"] == script_id
    assert "name: 前往服务" in payload["script_content_snapshot"]


def test_scene_task_items_detect_and_sync_script_changes(tmp_path: Path) -> None:
    client = _build_test_client(tmp_path)

    script_response = client.post(
        "/api/scripts",
        json={
            "name": "提交流程",
            "content": (
                "tasks:\n"
                "  - name: 查看详情\n"
                "    flow:\n"
                "      - aiAction: 点击查看详情按钮\n"
                "  - name: 提交质检报告\n"
                "    flow:\n"
                "      - aiAction: 点击提交质检报告按钮\n"
            ),
            "source_type": "manual",
        },
    )
    assert script_response.status_code == 201
    script_id = script_response.json()["id"]

    scene_response = client.post(
        "/api/scenes",
        json={"name": "同步测试场景", "description": "", "source_type": "manual"},
    )
    assert scene_response.status_code == 201
    scene_id = scene_response.json()["id"]

    bind_response = client.post(f"/api/scenes/{scene_id}/scripts", json={"script_id": script_id})
    assert bind_response.status_code == 201

    add_first = client.post(f"/api/scenes/{scene_id}/task-items", json={"script_id": script_id, "task_index": 0})
    add_second = client.post(f"/api/scenes/{scene_id}/task-items", json={"script_id": script_id, "task_index": 1})
    assert add_first.status_code == 201
    assert add_second.status_code == 201

    updated_script = client.put(
        f"/api/scripts/{script_id}",
        json={
            "name": "提交流程",
            "content": (
                "tasks:\n"
                "  - name: 查看订单详情\n"
                "    flow:\n"
                "      - aiAction: 点击订单详情入口\n"
            ),
            "source_type": "manual",
        },
    )
    assert updated_script.status_code == 200

    detail = client.get(f"/api/scenes/{scene_id}")
    assert detail.status_code == 200
    task_items = detail.json()["task_items"]
    assert task_items[0]["sync_status"] == "stale"
    assert task_items[1]["sync_status"] == "missing"

    synced_item = client.post(f"/api/scenes/{scene_id}/task-items/{task_items[0]['id']}/sync")
    assert synced_item.status_code == 200
    assert synced_item.json()["task_name_snapshot"] == "查看订单详情"
    assert synced_item.json()["sync_status"] == "current"

    missing_sync = client.post(f"/api/scenes/{scene_id}/task-items/{task_items[1]['id']}/sync")
    assert missing_sync.status_code == 409

    sync_all = client.post(f"/api/scenes/{scene_id}/task-items/sync")
    assert sync_all.status_code == 200
    sync_payload = sync_all.json()
    assert sync_payload["updated_count"] == 0
    assert sync_payload["missing_count"] == 1
    assert sync_payload["task_items"][0]["sync_status"] == "current"
    assert sync_payload["task_items"][1]["sync_status"] == "missing"
