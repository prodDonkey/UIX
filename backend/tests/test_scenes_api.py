from __future__ import annotations

import os
from collections.abc import Generator
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.scenes import router as scenes_router
from app.api.scripts import router as scripts_router
from app.core.database import Base, get_db


def _build_test_client() -> TestClient:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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


def test_scene_crud_and_script_binding() -> None:
    client = _build_test_client()

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


def test_scene_task_items_and_compiled_script() -> None:
    client = _build_test_client()

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


def test_scene_task_items_detect_and_sync_script_changes() -> None:
    client = _build_test_client()

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


def test_copy_scene_keeps_task_item_relation_binding() -> None:
    client = _build_test_client()

    script_response = client.post(
        "/api/scripts",
        json={
            "name": "复制关联脚本",
            "content": (
                "tasks:\n"
                "  - name: 第一步\n"
                "    flow:\n"
                "      - aiAction: 点击第一步\n"
            ),
            "source_type": "manual",
        },
    )
    assert script_response.status_code == 201
    script_id = script_response.json()["id"]

    scene_response = client.post(
        "/api/scenes",
        json={"name": "原场景", "description": "", "source_type": "manual"},
    )
    assert scene_response.status_code == 201
    scene_id = scene_response.json()["id"]

    bind_response = client.post(
        f"/api/scenes/{scene_id}/scripts",
        json={"script_id": script_id, "remark": "原始脚本"},
    )
    assert bind_response.status_code == 201
    relation_id = bind_response.json()["id"]

    item_response = client.post(
        f"/api/scenes/{scene_id}/task-items",
        json={"script_id": script_id, "task_index": 0},
    )
    assert item_response.status_code == 201
    assert item_response.json()["scene_script_id"] == relation_id

    copied_scene = client.post(f"/api/scenes/{scene_id}/copy")
    assert copied_scene.status_code == 201
    copied_payload = copied_scene.json()
    copied_scene_id = copied_payload["id"]
    copied_relation_id = copied_payload["scripts"][0]["id"]

    copied_item = copied_payload["task_items"][0]
    assert copied_item["scene_script_id"] == copied_relation_id

    delete_copied_relation = client.delete(f"/api/scenes/{copied_scene_id}/scripts/{copied_relation_id}")
    assert delete_copied_relation.status_code == 204

    copied_items = client.get(f"/api/scenes/{copied_scene_id}/task-items")
    assert copied_items.status_code == 200
    assert copied_items.json() == []


def test_scene_task_items_support_variable_binding_and_validation() -> None:
    client = _build_test_client()

    script_response = client.post(
        "/api/scripts",
        json={
            "name": "接口链路脚本",
            "content": (
                "tasks:\n"
                "  - name: 下单\n"
                "    flow:\n"
                "      - aiAction: 调用下单接口\n"
                "  - name: 分配\n"
                "    flow:\n"
                "      - aiAction: 调用分配接口\n"
                "  - name: 用户确认\n"
                "    flow:\n"
                "      - aiAction: 调用确认接口\n"
            ),
            "source_type": "manual",
        },
    )
    assert script_response.status_code == 201
    script_id = script_response.json()["id"]

    scene_response = client.post(
        "/api/scenes",
        json={"name": "变量传递场景", "description": "", "source_type": "manual"},
    )
    assert scene_response.status_code == 201
    scene_id = scene_response.json()["id"]

    bind_response = client.post(f"/api/scenes/{scene_id}/scripts", json={"script_id": script_id})
    assert bind_response.status_code == 201

    order_item = client.post(f"/api/scenes/{scene_id}/task-items", json={"script_id": script_id, "task_index": 0})
    assign_item = client.post(f"/api/scenes/{scene_id}/task-items", json={"script_id": script_id, "task_index": 1})
    assert order_item.status_code == 201
    assert assign_item.status_code == 201

    configured_order = client.put(
        f"/api/scenes/{scene_id}/task-items/{order_item.json()['id']}",
        json={
            "sort_order": 1,
            "output_variables": [
                {
                    "name": "recycleOrderId",
                    "source_path": "respMsg.data.fields.recycleOrderId",
                    "description": "下单返回单号",
                }
            ],
        },
    )
    assert configured_order.status_code == 200
    assert configured_order.json()["output_variables"][0]["name"] == "recycleOrderId"

    configured_assign = client.put(
        f"/api/scenes/{scene_id}/task-items/{assign_item.json()['id']}",
        json={
            "sort_order": 2,
            "input_bindings": [
                {
                    "target_path": "interface.params.orderNo",
                    "expression": "${recycleOrderId}",
                    "description": "引用上一步单号",
                }
            ],
        },
    )
    assert configured_assign.status_code == 200
    assert configured_assign.json()["input_bindings"][0]["expression"] == "${recycleOrderId}"

    compiled = client.get(f"/api/scenes/{scene_id}/compiled-script")
    assert compiled.status_code == 200
    compiled_yaml = compiled.json()["yaml"]
    assert "sceneVariables:" in compiled_yaml
    assert "name: recycleOrderId" in compiled_yaml
    assert "expression: ${recycleOrderId}" in compiled_yaml

    invalid_scene = client.post(
        "/api/scenes",
        json={"name": "非法变量场景", "description": "", "source_type": "manual"},
    )
    assert invalid_scene.status_code == 201
    invalid_scene_id = invalid_scene.json()["id"]
    bind_invalid = client.post(f"/api/scenes/{invalid_scene_id}/scripts", json={"script_id": script_id})
    assert bind_invalid.status_code == 201
    invalid_item = client.post(
        f"/api/scenes/{invalid_scene_id}/task-items",
        json={"script_id": script_id, "task_index": 1},
    )
    assert invalid_item.status_code == 201
    update_invalid = client.put(
        f"/api/scenes/{invalid_scene_id}/task-items/{invalid_item.json()['id']}",
        json={
            "input_bindings": [
                {
                    "target_path": "interface.params.orderNo",
                    "expression": "${missingOrderNo}",
                    "description": "引用不存在变量",
                }
            ],
        },
    )
    assert update_invalid.status_code == 200

    invalid_compiled = client.get(f"/api/scenes/{invalid_scene_id}/compiled-script")
    assert invalid_compiled.status_code == 400
    assert "未定义变量" in invalid_compiled.json()["detail"]


def test_scene_task_items_detect_script_side_variable_meta_changes() -> None:
    client = _build_test_client()

    script_response = client.post(
        "/api/scripts",
        json={
            "name": "变量元数据脚本",
            "content": (
                "tasks:\n"
                "  - name: 下单\n"
                "    flow:\n"
                "      - aiAction: 调用下单接口\n"
            ),
            "source_type": "manual",
        },
    )
    assert script_response.status_code == 201
    script_id = script_response.json()["id"]

    scene_response = client.post(
        "/api/scenes",
        json={"name": "变量元数据同步场景", "description": "", "source_type": "manual"},
    )
    assert scene_response.status_code == 201
    scene_id = scene_response.json()["id"]

    bind_response = client.post(f"/api/scenes/{scene_id}/scripts", json={"script_id": script_id})
    assert bind_response.status_code == 201

    item_response = client.post(
        f"/api/scenes/{scene_id}/task-items",
        json={"script_id": script_id, "task_index": 0},
    )
    assert item_response.status_code == 201
    item_id = item_response.json()["id"]
    assert item_response.json()["sync_status"] == "current"

    updated_script = client.put(
        f"/api/scripts/{script_id}",
        json={
            "name": "变量元数据脚本",
            "content": (
                "tasks:\n"
                "  - name: 下单\n"
                "    sceneVariables:\n"
                "      outputs:\n"
                "        - name: recycleOrderId\n"
                "          source_path: respMsg.data.fields.recycleOrderId\n"
                "          description: 下单返回单号\n"
                "    flow:\n"
                "      - aiAction: 调用下单接口\n"
            ),
            "source_type": "manual",
        },
    )
    assert updated_script.status_code == 200

    detail = client.get(f"/api/scenes/{scene_id}")
    assert detail.status_code == 200
    task_item = detail.json()["task_items"][0]
    assert task_item["sync_status"] == "stale"

    synced = client.post(f"/api/scenes/{scene_id}/task-items/{item_id}/sync")
    assert synced.status_code == 200
    assert synced.json()["sync_status"] == "current"
    assert synced.json()["output_variables"][0]["name"] == "recycleOrderId"


def test_script_level_interface_is_embedded_into_task_snapshot() -> None:
    client = _build_test_client()

    script_response = client.post(
        "/api/scripts",
        json={
            "name": "接口脚本",
            "content": (
                "interface:\n"
                "  name: 回收单下单\n"
                "  method: POST\n"
                "  url: https://datapt.zhuanspirit.com/api/basicdata/getresult\n"
                "tasks:\n"
                "  - name: 下单\n"
                "    flow:\n"
                "      - aiAction: 调用下单接口\n"
            ),
            "source_type": "manual",
        },
    )
    assert script_response.status_code == 201
    script_id = script_response.json()["id"]

    scene_response = client.post(
        "/api/scenes",
        json={"name": "接口脚本场景", "description": "", "source_type": "manual"},
    )
    assert scene_response.status_code == 201
    scene_id = scene_response.json()["id"]

    bind_response = client.post(f"/api/scenes/{scene_id}/scripts", json={"script_id": script_id})
    assert bind_response.status_code == 201

    item_response = client.post(
        f"/api/scenes/{scene_id}/task-items",
        json={"script_id": script_id, "task_index": 0},
    )
    assert item_response.status_code == 201
    assert "interface:" in item_response.json()["task_content_snapshot"]

    compiled = client.get(f"/api/scenes/{scene_id}/compiled-script")
    assert compiled.status_code == 200
    compiled_yaml = compiled.json()["yaml"]
    assert "interface:" in compiled_yaml
    assert "url: https://datapt.zhuanspirit.com/api/basicdata/getresult" in compiled_yaml


def test_execute_scene_runs_http_interface_tasks(monkeypatch) -> None:
    client = _build_test_client()

    script_response = client.post(
        "/api/scripts",
        json={
            "name": "执行脚本",
            "content": (
                "interface:\n"
                "  method: POST\n"
                "  url: https://example.test/orders\n"
                "  contentType: application/json\n"
                "  headers:\n"
                "    Authorization: Bearer demo-token\n"
                "tasks:\n"
                "  - name: 下单\n"
                "    sceneVariables:\n"
                "      outputs:\n"
                "        - name: orderNo\n"
                "          source_path: data.orderNo\n"
                "    flow:\n"
                "      - aiAction: 调用下单接口\n"
                "  - name: 查询订单\n"
                "    interface:\n"
                "      method: POST\n"
                "      url: https://example.test/query\n"
                "      contentType: application/json\n"
                "      params:\n"
                "        orderNo: \"\"\n"
                "    sceneVariables:\n"
                "      inputs:\n"
                "        - target_path: interface.params.orderNo\n"
                "          expression: ${orderNo}\n"
                "      outputs:\n"
                "        - name: orderStatus\n"
                "          source_path: data.status\n"
                "    flow:\n"
                "      - aiAction: 调用查询接口\n"
            ),
            "source_type": "manual",
        },
    )
    assert script_response.status_code == 201
    script_id = script_response.json()["id"]

    scene_response = client.post(
        "/api/scenes",
        json={"name": "可执行场景", "description": "", "source_type": "manual"},
    )
    assert scene_response.status_code == 201
    scene_id = scene_response.json()["id"]

    bind_response = client.post(f"/api/scenes/{scene_id}/scripts", json={"script_id": script_id})
    assert bind_response.status_code == 201
    item_response = client.post(
        f"/api/scenes/{scene_id}/task-items",
        json={"script_id": script_id, "task_index": 0},
    )
    assert item_response.status_code == 201
    second_item_response = client.post(
        f"/api/scenes/{scene_id}/task-items",
        json={"script_id": script_id, "task_index": 1},
    )
    assert second_item_response.status_code == 201

    requests: list[dict] = []

    class DummyResponse:
        def __init__(self, *, status_code: int, body: dict):
            self.status_code = status_code
            self._body = body
            self.text = str(body)
            self.headers = {"content-type": "application/json"}
            self.request = SimpleNamespace(url="https://example.test/mock")

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._body

    class DummyClient:
        def __init__(self, timeout: float, follow_redirects: bool = False):
            self.timeout = timeout
            self.follow_redirects = follow_redirects

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, **kwargs):
            requests.append(kwargs)
            url = kwargs["url"]
            if url == "https://example.test/orders":
                return DummyResponse(status_code=200, body={"data": {"orderNo": "ORD-001"}})
            return DummyResponse(status_code=200, body={"data": {"status": "CREATED"}})

    monkeypatch.setattr("app.services.http_executor.httpx.Client", DummyClient)

    execute_response = client.post(f"/api/scenes/{scene_id}/execute")
    assert execute_response.status_code == 200
    payload = execute_response.json()
    assert payload["scene_id"] == scene_id
    assert payload["success"] is True
    assert payload["message"] == "场景执行完成"
    assert payload["outputs"]["orderNo"] == "ORD-001"
    assert payload["outputs"]["orderStatus"] == "CREATED"
    assert requests[0]["url"] == "https://example.test/orders"
    assert requests[0]["method"] == "POST"
    assert requests[0]["headers"]["Authorization"] == "Bearer demo-token"
    assert requests[1]["url"] == "https://example.test/query"
    assert requests[1]["json"]["orderNo"] == "ORD-001"
    assert payload["detail"]["task_results"][1]["outputs"]["orderStatus"] == "CREATED"
