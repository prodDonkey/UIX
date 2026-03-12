from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.runs import router as runs_router
from app.api.scripts import router as scripts_router
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.run import Run
from app.models.script import Script
from app.services import run_service


def _build_test_client(tmp_path: Path) -> tuple[TestClient, sessionmaker[Session]]:
    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(scripts_router)
    app.include_router(runs_router)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, testing_session_local


def test_scripts_crud_and_validate_still_available(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)

    created = client.post(
        "/api/scripts",
        json={
            "name": "登录脚本",
            "content": "android:\n  deviceId: 'emulator-5554'\ntasks:\n  - name: 登录\n    flow:\n      - aiAction: 打开应用\n",
            "source_type": "manual",
        },
    )
    assert created.status_code == 201
    script_id = created.json()["id"]

    listed = client.get("/api/scripts")
    assert listed.status_code == 200
    assert any(item["id"] == script_id for item in listed.json())

    updated = client.put(
        f"/api/scripts/{script_id}",
        json={"content": "android:\n  deviceId: 'emulator-5554'\ntasks:\n  - name: 登录\n    flow:\n      - aiAction: 输入账号\n"},
    )
    assert updated.status_code == 200
    assert "输入账号" in updated.json()["content"]

    copied = client.post(f"/api/scripts/{script_id}/copy")
    assert copied.status_code == 201
    assert copied.json()["name"].endswith("-copy")

    validated = client.post(
        f"/api/scripts/{script_id}/validate",
        json={"content": "android:\n  deviceId: 'emulator-5554'\ntasks:\n  - name: 检查\n    flow:\n      - aiAction: 点击设置\n"},
    )
    assert validated.status_code == 200
    assert validated.json()["valid"] is True

    deleted = client.delete(f"/api/scripts/{script_id}")
    assert deleted.status_code == 204


def test_runs_detail_report_and_progress_still_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_root = tmp_path / "reports"
    report_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "report_root_dir", str(report_root))

    client, session_local = _build_test_client(tmp_path)

    # 避免测试中触发真实 Runner 异步执行。
    monkeypatch.setattr("app.api.runs.start_run_async", lambda run_id: None)

    created_script = client.post(
        "/api/scripts",
        json={
            "name": "运行脚本",
            "content": "android:\n  deviceId: 'emulator-5554'\ntasks:\n  - name: 执行\n    flow:\n      - aiAction: 打开首页\n",
            "source_type": "manual",
        },
    )
    assert created_script.status_code == 201
    script_id = created_script.json()["id"]

    created_run = client.post("/api/runs", json={"script_id": script_id})
    assert created_run.status_code == 201
    run_id = created_run.json()["id"]

    report_file = report_root / f"run-{run_id}.html"
    report_file.write_text("<html><body>ok</body></html>", encoding="utf-8")

    with session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        run.status = "running"
        run.report_path = str(report_file)
        run.current_task = "登录流程"
        run.current_action = "点击登录"
        run.progress_json = '{"status":"running","completed":1,"total":3}'
        db.commit()

    listed = client.get("/api/runs", params={"script_id": script_id})
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    detail = client.get(f"/api/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["current_task"] == "登录流程"
    assert detail.json()["script_name_snapshot"] == "运行脚本"
    assert "打开首页" in detail.json()["script_content_snapshot"]
    assert detail.json()["total_tokens"] is None

    progress = client.get(f"/api/runs/{run_id}/progress")
    assert progress.status_code == 200
    progress_payload = progress.json()
    assert progress_payload["status"] == "running"
    assert progress_payload["current_action"] == "点击登录"
    assert "completed" in progress_payload["progress_json"]

    report = client.get(f"/api/runs/{run_id}/report")
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["preview_url"] is not None

    preview = client.get(f"/api/runs/{run_id}/report/file")
    assert preview.status_code == 200
    assert "text/html" in preview.headers.get("content-type", "")

    preview_head = client.head(f"/api/runs/{run_id}/report/file")
    assert preview_head.status_code == 200
    assert "text/html" in preview_head.headers.get("content-type", "")


def test_runs_task_progress_returns_lightweight_summary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, session_local = _build_test_client(tmp_path)
    monkeypatch.setattr("app.api.runs.start_run_async", lambda run_id: None)

    created_script = client.post(
        "/api/scripts",
        json={
            "name": "日志脚本",
            "content": "android:\n  deviceId: 'emulator-5554'\ntasks:\n  - name: 执行\n    flow:\n      - aiAction: 打开首页\n",
            "source_type": "manual",
        },
    )
    assert created_script.status_code == 201
    script_id = created_script.json()["id"]

    created_run = client.post("/api/runs", json={"script_id": script_id})
    assert created_run.status_code == 201
    run_id = created_run.json()["id"]

    with session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        run.status = "running"
        run.request_id = "req-progress-123"
        db.commit()

    heavy_progress = {
        "status": "running",
        "executionDump": {
            "name": "大型日志",
            "logTime": 1773297213518,
            "tasks": [
                {
                    "taskId": "task-1",
                    "status": "running",
                    "type": "Locate",
                    "subType": "AI",
                    "thought": "正在识别页面元素",
                    "param": {
                        "userInstruction": "点击提交按钮",
                        "screenshot": {"base64": "data:image/png;base64,AAAA"},
                        "locate": {"name": "提交按钮"},
                    },
                    "output": {
                        "log": "找到目标按钮",
                        "thought": "准备执行点击",
                        "actions": [
                            {
                                "type": "Tap",
                                "thought": "点击提交按钮",
                                "param": {
                                    "description": "提交按钮",
                                    "image": "data:image/png;base64,BBBB",
                                },
                            }
                        ],
                        "uiContext": {"screenshot": {"base64": "data:image/png;base64,CCCC"}},
                    },
                    "recorder": [{"kind": "debug", "message": "huge"}],
                }
            ],
        },
    }
    monkeypatch.setattr(run_service, "_midscene_task_progress", lambda request_id: heavy_progress)

    response = client.get(f"/api/runs/{run_id}/task-progress")
    assert response.status_code == 200
    payload = response.json()
    assert payload["executionDump"]["name"] == "大型日志"
    assert payload["executionDump"]["logTime"] == 1773297213518
    task = payload["executionDump"]["tasks"][0]
    assert task["taskId"] == "task-1"
    assert task["output"]["log"] == "找到目标按钮"
    assert "screenshot" not in task["param"]
    assert "recorder" not in task
    assert task["output"]["actions"][0]["param"]["description"] == "提交按钮"
    assert "image" not in task["output"]["actions"][0]["param"]


def test_create_run_persists_script_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, session_local = _build_test_client(tmp_path)
    monkeypatch.setattr("app.api.runs.start_run_async", lambda run_id: None)

    created_script = client.post(
        "/api/scripts",
        json={
            "name": "快照脚本",
            "content": "android:\n  deviceId: ''\ntasks:\n  - name: 执行快照\n    flow:\n      - aiAction: 打开设置\n",
            "source_type": "manual",
        },
    )
    assert created_script.status_code == 201
    script_payload = created_script.json()

    created_run = client.post("/api/runs", json={"script_id": script_payload["id"]})
    assert created_run.status_code == 201
    run_id = created_run.json()["id"]

    with session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        assert run.script_name_snapshot == "快照脚本"
        assert "打开设置" in (run.script_content_snapshot or "")
        assert run.script_updated_at_snapshot is not None

    detail = client.get(f"/api/runs/{run_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["script_name_snapshot"] == "快照脚本"
    assert "打开设置" in payload["script_content_snapshot"]


def test_runs_report_can_fallback_to_midscene_report_html(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_root = tmp_path / "reports"
    report_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "report_root_dir", str(report_root))

    client, session_local = _build_test_client(tmp_path)
    monkeypatch.setattr("app.api.runs.start_run_async", lambda run_id: None)
    monkeypatch.setattr("app.api.runs.get_report_html", lambda run: "<html><body>midsce-report</body></html>")

    created_script = client.post(
        "/api/scripts",
        json={
            "name": "运行脚本",
            "content": "android:\n  deviceId: 'emulator-5554'\ntasks:\n  - name: 执行\n    flow:\n      - aiAction: 打开首页\n",
            "source_type": "manual",
        },
    )
    assert created_script.status_code == 201
    script_id = created_script.json()["id"]

    created_run = client.post("/api/runs", json={"script_id": script_id})
    assert created_run.status_code == 201
    run_id = created_run.json()["id"]

    with session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        run.status = "success"
        run.request_id = "req-report-123"
        run.report_path = None
        db.commit()

    report = client.get(f"/api/runs/{run_id}/report")
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["report_path"] == "midsce://req-report-123"
    assert report_payload["preview_url"] is not None

    preview = client.get(f"/api/runs/{run_id}/report/file")
    assert preview.status_code == 200
    assert "midsce-report" in preview.text

    download = client.get(f"/api/runs/{run_id}/report/file?download=1")
    assert download.status_code == 200
    assert "attachment;" in (download.headers.get("content-disposition") or "")


def test_runs_report_prefers_runtime_report_path_when_midscene_html_is_placeholder(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_root = tmp_path / "reports"
    report_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "report_root_dir", str(report_root))

    client, session_local = _build_test_client(tmp_path)
    monkeypatch.setattr("app.api.runs.start_run_async", lambda run_id: None)

    runtime_report = report_root / "runtime-report.html"
    runtime_report.write_text("<html><body>runtime-report</body></html>", encoding="utf-8")
    monkeypatch.setattr("app.api.runs.get_runtime_report_path", lambda run: str(runtime_report))
    monkeypatch.setattr("app.api.runs.get_report_html", lambda run: None)

    created_script = client.post(
        "/api/scripts",
        json={
            "name": "运行脚本",
            "content": "android:\n  deviceId: 'emulator-5554'\ntasks:\n  - name: 执行\n    flow:\n      - aiAction: 打开首页\n",
            "source_type": "manual",
        },
    )
    assert created_script.status_code == 201
    script_id = created_script.json()["id"]

    created_run = client.post("/api/runs", json={"script_id": script_id})
    assert created_run.status_code == 201
    run_id = created_run.json()["id"]

    with session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        run.status = "success"
        run.request_id = "req-report-runtime"
        run.report_path = None
        db.commit()

    report = client.get(f"/api/runs/{run_id}/report")
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["report_path"] == str(runtime_report.resolve())
    assert report_payload["preview_url"] is not None

    preview = client.get(f"/api/runs/{run_id}/report/file")
    assert preview.status_code == 200
    assert "runtime-report" in preview.text


def test_run_execute_retries_midscene_poll_timeout_without_marking_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "run-service.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with testing_session_local() as db:
        script = Script(name="轮询超时脚本", content="tasks: []", source_type="manual")
        db.add(script)
        db.commit()
        db.refresh(script)

        run = Run(script_id=script.id, status="queued")
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    monkeypatch.setattr(run_service, "SessionLocal", testing_session_local)
    monkeypatch.setattr(settings, "midscene_status_poll_interval_ms", 1)
    monkeypatch.setattr(run_service.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        run_service,
        "_midscene_run_yaml",
        lambda _: {"requestId": "req-timeout-retry"},
    )
    monkeypatch.setattr(
        run_service,
        "_midscene_task_progress",
        lambda _: {
            "status": "running",
            "currentTask": "质检流程",
            "currentAction": "点击无以上问题",
            "tasks": [],
        },
    )

    result_calls = {"count": 0}

    def fake_task_result(_: str) -> dict:
        result_calls["count"] += 1
        if result_calls["count"] == 1:
            raise httpx.ReadTimeout("poll timeout")
        return {
            "status": "completed",
            "reportPath": "/tmp/report.html",
        }

    monkeypatch.setattr(run_service, "_midscene_task_result", fake_task_result)

    run_service._execute_run(run_id)

    with testing_session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        assert run.status == "success"
        assert run.error_message is None
        assert run.request_id == "req-timeout-retry"
        assert run.report_path == "/tmp/report.html"
        assert run.current_task == "质检流程"
        assert run.current_action == "点击无以上问题"
        assert result_calls["count"] == 2


def test_run_execute_persists_total_tokens_from_progress(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "run-service-tokens.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with testing_session_local() as db:
        script = Script(name="token脚本", content="tasks: []", source_type="manual")
        db.add(script)
        db.commit()
        db.refresh(script)

        run = Run(script_id=script.id, status="queued")
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    monkeypatch.setattr(run_service, "SessionLocal", testing_session_local)
    monkeypatch.setattr(settings, "midscene_status_poll_interval_ms", 1)
    monkeypatch.setattr(run_service.time, "sleep", lambda _: None)
    monkeypatch.setattr(run_service, "_midscene_run_yaml", lambda _: {"requestId": "req-token-usage"})
    monkeypatch.setattr(
        run_service,
        "_midscene_task_progress",
        lambda _: {
            "status": "running",
            "currentTask": "执行任务",
            "currentAction": "点击按钮",
            "tasks": [
                {"taskId": "plan-1", "status": "finished", "usage": {"total_tokens": 120}},
                {"taskId": "act-1", "status": "finished", "usage": {"prompt_tokens": 80, "completion_tokens": 20}},
            ],
        },
    )
    monkeypatch.setattr(
        run_service,
        "_midscene_task_result",
        lambda _: {"status": "completed", "reportPath": "/tmp/report.html"},
    )

    run_service._execute_run(run_id)

    with testing_session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        assert run.status == "success"
        assert run.total_tokens == 220


def test_get_run_can_reconcile_midscene_not_found_to_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, session_local = _build_test_client(tmp_path)
    monkeypatch.setattr("app.api.runs.start_run_async", lambda run_id: None)
    monkeypatch.setattr(
        "app.services.run_service._midscene_task_result",
        lambda _: {
            "status": "not_found",
            "error": "Task result not found",
        },
    )
    monkeypatch.setattr(
        "app.services.run_service._midscene_task_progress",
        lambda _: {
            "status": "not_found",
            "tasks": [],
        },
    )

    created_script = client.post(
        "/api/scripts",
        json={
            "name": "状态收敛脚本",
            "content": "tasks:\n  - name: 执行\n    flow:\n      - aiAction: 打开首页\n",
            "source_type": "manual",
        },
    )
    assert created_script.status_code == 201
    script_id = created_script.json()["id"]

    created_run = client.post("/api/runs", json={"script_id": script_id})
    assert created_run.status_code == 201
    run_id = created_run.json()["id"]

    with session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        run.status = "running"
        run.started_at = run.started_at or run_service.datetime.utcnow()
        run.request_id = "req-not-found-terminal"
        db.commit()

    detail = client.get(f"/api/runs/{run_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["status"] == "failed"
    assert payload["error_message"] == "Task result not found"
    assert payload["ended_at"] is not None

    with session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error_message == "Task result not found"


def test_get_runs_list_can_reconcile_midscene_not_found_to_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, session_local = _build_test_client(tmp_path)
    monkeypatch.setattr("app.api.runs.start_run_async", lambda run_id: None)
    monkeypatch.setattr(
        "app.services.run_service._midscene_task_result",
        lambda _: {
            "status": "not_found",
            "error": "Task result not found",
        },
    )
    monkeypatch.setattr(
        "app.services.run_service._midscene_task_progress",
        lambda _: {
            "status": "not_found",
            "tasks": [],
        },
    )

    created_script = client.post(
        "/api/scripts",
        json={
            "name": "列表状态收敛脚本",
            "content": "tasks:\n  - name: 执行\n    flow:\n      - aiAction: 打开首页\n",
            "source_type": "manual",
        },
    )
    assert created_script.status_code == 201
    script_id = created_script.json()["id"]

    created_run = client.post("/api/runs", json={"script_id": script_id})
    assert created_run.status_code == 201
    run_id = created_run.json()["id"]

    with session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        run.status = "running"
        run.started_at = run.started_at or run_service.datetime.utcnow()
        run.request_id = "req-list-not-found-terminal"
        db.commit()

    listed = client.get("/api/runs", params={"script_id": script_id})
    assert listed.status_code == 200
    payload = listed.json()
    target = next(item for item in payload if item["id"] == run_id)
    assert target["status"] == "failed"
    assert target["error_message"] == "Task result not found"

    with session_local() as db:
        run = db.get(Run, run_id)
        assert run is not None
        assert run.status == "failed"
