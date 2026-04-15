from __future__ import annotations

import json
import re

import yaml


SCENE_VARIABLE_META_KEY = "sceneVariables"
VARIABLE_PATTERN = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


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

    # 将脚本级 interface 下沉到 task 快照里，便于场景编排跨脚本组合后仍保留各自接口语义。
    interface_config = parsed.get("interface")

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

        task_snapshot = dict(task)
        if interface_config is not None and "interface" not in task_snapshot:
            task_snapshot["interface"] = interface_config

        task_items.append(
            {
                "task_index": index,
                "task_name": name,
                "task": task_snapshot,
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
    for key in ("android", "ios", "web", "computer", "agent", "config", "target"):
        value = parsed.get(key)
        if value is not None:
            env[key] = value
    return env


def compile_scene_script(env: dict, task_snapshots: list[str]) -> str:
    tasks: list[dict] = []
    available_variables: set[str] = set()
    for index, item in enumerate(task_snapshots):
        task = load_task_snapshot(item)
        meta = extract_task_variable_meta(task)
        _validate_task_variable_meta(meta, available_variables, index=index)
        tasks.append(task)
        available_variables.update(output["name"] for output in meta["outputs"])
    compiled = {**env, "tasks": tasks}
    return yaml.safe_dump(compiled, sort_keys=False, allow_unicode=True)


def task_snapshot_key(task_snapshot: str) -> str:
    return json.dumps(load_task_snapshot(task_snapshot), ensure_ascii=False, sort_keys=True)


def find_script_task(content: str, task_index: int) -> dict | None:
    tasks = parse_script_tasks(content)
    return next((item for item in tasks if item["task_index"] == task_index), None)


def scene_task_sync_status(
    *,
    script_content: str,
    task_index: int,
    task_name_snapshot: str,
    task_content_snapshot: str,
) -> tuple[str, str]:
    matched_task = find_script_task(script_content, task_index)
    if not matched_task:
        return "missing", "脚本中已不存在该任务"

    current_name = matched_task["task_name"]
    current_meta = task_snapshot_variable_meta(task_content_snapshot)
    current_snapshot = dump_task_snapshot(
        merge_task_variable_meta(
            matched_task["task"],
            input_bindings=current_meta["inputs"],
            output_variables=current_meta["outputs"],
        )
    )
    if current_name != task_name_snapshot or task_snapshot_key(current_snapshot) != task_snapshot_key(task_content_snapshot):
        return "stale", "脚本任务已更新，可同步快照"

    return "current", ""


def _normalize_variable_rows(rows: list[dict] | None, *, kind: str) -> list[dict]:
    normalized: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            raise SceneCompileError(f"{kind} 配置项必须是对象")

        cleaned = {
            key: str(value).strip()
            for key, value in row.items()
            if value is not None and str(value).strip()
        }
        if not cleaned:
            continue
        normalized.append(cleaned)
    return normalized


def apply_task_variable_meta(
    task: dict,
    *,
    input_bindings: list[dict] | None = None,
    output_variables: list[dict] | None = None,
) -> dict:
    next_task = dict(task)
    normalized_inputs = _normalize_variable_rows(input_bindings, kind="输入绑定")
    normalized_outputs = _normalize_variable_rows(output_variables, kind="输出变量")

    if not normalized_inputs and not normalized_outputs:
        next_task.pop(SCENE_VARIABLE_META_KEY, None)
        return next_task

    next_task[SCENE_VARIABLE_META_KEY] = {
        "inputs": normalized_inputs,
        "outputs": normalized_outputs,
    }
    return next_task


def merge_task_variable_meta(
    task: dict,
    *,
    input_bindings: list[dict] | None = None,
    output_variables: list[dict] | None = None,
) -> dict:
    base_meta = extract_task_variable_meta(task)
    normalized_inputs = _normalize_variable_rows(input_bindings, kind="输入绑定")
    normalized_outputs = _normalize_variable_rows(output_variables, kind="输出变量")

    merged_inputs = _merge_variable_rows(base_meta["inputs"], normalized_inputs, identity_key="target_path")
    merged_outputs = _merge_variable_rows(base_meta["outputs"], normalized_outputs, identity_key="name")
    return apply_task_variable_meta(task, input_bindings=merged_inputs, output_variables=merged_outputs)


def extract_task_variable_meta(task: dict) -> dict[str, list[dict]]:
    raw_meta = task.get(SCENE_VARIABLE_META_KEY)
    if not isinstance(raw_meta, dict):
        return {"inputs": [], "outputs": []}

    return {
        "inputs": _normalize_variable_rows(raw_meta.get("inputs"), kind="输入绑定"),
        "outputs": _normalize_variable_rows(raw_meta.get("outputs"), kind="输出变量"),
    }


def task_snapshot_variable_meta(task_snapshot: str) -> dict[str, list[dict]]:
    return extract_task_variable_meta(load_task_snapshot(task_snapshot))


def _merge_variable_rows(base_rows: list[dict], override_rows: list[dict], *, identity_key: str) -> list[dict]:
    merged: list[dict] = []
    override_index = {
        row.get(identity_key, "").strip(): row
        for row in override_rows
        if row.get(identity_key, "").strip()
    }
    consumed_keys: set[str] = set()

    for row in base_rows:
        row_key = row.get(identity_key, "").strip()
        if row_key and row_key in override_index:
            merged.append(override_index[row_key])
            consumed_keys.add(row_key)
            continue
        merged.append(row)

    for row in override_rows:
        row_key = row.get(identity_key, "").strip()
        if row_key and row_key in consumed_keys:
            continue
        if row_key and row_key in override_index and row is not override_index[row_key]:
            continue
        merged.append(row)

    return merged


def _validate_task_variable_meta(meta: dict[str, list[dict]], available_variables: set[str], *, index: int) -> None:
    seen_outputs: set[str] = set()
    for output in meta["outputs"]:
        name = output.get("name", "").strip()
        if not name:
            raise SceneCompileError(f"第 {index + 1} 个任务的输出变量缺少 name")
        if not VARIABLE_PATTERN.fullmatch(f"${{{name}}}"):
            raise SceneCompileError(f"第 {index + 1} 个任务的输出变量名非法：{name}")
        if name in seen_outputs:
            raise SceneCompileError(f"第 {index + 1} 个任务存在重复输出变量：{name}")
        seen_outputs.add(name)

    for binding in meta["inputs"]:
        expression = binding.get("expression", "").strip()
        target_path = binding.get("target_path", "").strip()
        if not target_path:
            raise SceneCompileError(f"第 {index + 1} 个任务的输入绑定缺少 target_path")
        if not expression:
            raise SceneCompileError(f"第 {index + 1} 个任务的输入绑定缺少 expression")

        for variable_name in VARIABLE_PATTERN.findall(expression):
            if variable_name not in available_variables:
                raise SceneCompileError(
                    f"第 {index + 1} 个任务引用了未定义变量：{variable_name}。只能引用前序任务输出变量"
                )
