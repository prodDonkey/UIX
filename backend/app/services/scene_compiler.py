from __future__ import annotations

import json

import yaml


class SceneCompileError(ValueError):
    pass


def parse_script_tasks(content: str) -> list[dict]:
    try:
        parsed = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:  # noqa: PERF203
        raise SceneCompileError(f"脚本 YAML 解析失败：{exc}") from exc

    if not isinstance(parsed, dict):
        raise SceneCompileError("脚本内容必须是对象结构")

    tasks = parsed.get("tasks")
    if tasks is None:
        return []
    if not isinstance(tasks, list):
        raise SceneCompileError("脚本 tasks 必须是数组")

    task_items: list[dict] = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise SceneCompileError(f"第 {index + 1} 个 task 结构非法")
        name = str(task.get("name") or "").strip()
        if not name:
            raise SceneCompileError(f"第 {index + 1} 个 task 缺少 name")
        flow = task.get("flow")
        if not isinstance(flow, list):
            raise SceneCompileError(f"task {name} 缺少合法 flow")

        task_items.append(
            {
                "task_index": index,
                "task_name": name,
                "task": task,
                "flow": flow,
                "continue_on_error": bool(task.get("continueOnError", False)),
            }
        )
    return task_items


def dump_task_snapshot(task: dict) -> str:
    return yaml.safe_dump(task, sort_keys=False, allow_unicode=True).strip()


def load_task_snapshot(content: str) -> dict:
    try:
        parsed = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:  # noqa: PERF203
        raise SceneCompileError(f"任务快照解析失败：{exc}") from exc
    if not isinstance(parsed, dict):
        raise SceneCompileError("任务快照结构非法")
    return parsed


def extract_script_env(content: str) -> dict:
    try:
        parsed = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:  # noqa: PERF203
        raise SceneCompileError(f"脚本 YAML 解析失败：{exc}") from exc

    if not isinstance(parsed, dict):
        raise SceneCompileError("脚本内容必须是对象结构")

    env: dict = {}
    for key in ("android", "ios", "web", "computer", "agent", "config", "interface", "target"):
        value = parsed.get(key)
        if value is not None:
            env[key] = value
    return env


def compile_scene_script(env: dict, task_snapshots: list[str]) -> str:
    tasks: list[dict] = [load_task_snapshot(item) for item in task_snapshots]
    compiled = {**env, "tasks": tasks}
    return yaml.safe_dump(compiled, sort_keys=False, allow_unicode=True)


def task_snapshot_key(task_snapshot: str) -> str:
    return json.dumps(load_task_snapshot(task_snapshot), ensure_ascii=False, sort_keys=True)
