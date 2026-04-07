from __future__ import annotations

import copy
import json
import re
import time
from typing import Any

import httpx

from app.services.scene_compiler import load_task_snapshot, task_snapshot_variable_meta

VARIABLE_PATTERN = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_MISSING = object()


class HttpExecutionError(ValueError):
    pass


def execute_scene_http_tasks(
    *,
    task_snapshots: list[str],
    timeout_sec: float,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    task_results: list[dict[str, Any]] = []

    with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
        for index, snapshot in enumerate(task_snapshots):
            raw_task = load_task_snapshot(snapshot)
            task = copy.deepcopy(raw_task)
            task_name = str(task.get("name") or f"task-{index + 1}")
            variable_meta = task_snapshot_variable_meta(snapshot)
            continue_on_error = bool(task.get("continueOnError", False))

            try:
                _apply_input_bindings(task, variable_meta["inputs"], outputs)
                interface_config = _extract_interface_config(task, index=index)
                start_at = time.perf_counter()
                response = _send_interface_request(client, interface_config)
                duration_ms = int((time.perf_counter() - start_at) * 1000)
                response_payload = _build_response_payload(response)
                produced_outputs = _extract_output_variables(variable_meta["outputs"], response_payload)
                outputs.update(produced_outputs)
                task_results.append(
                    {
                        "task_name": task_name,
                        "ok": True,
                        "method": interface_config["method"],
                        "url": interface_config["url"],
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "outputs": produced_outputs,
                        "response": response_payload["body"],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                task_results.append(
                    {
                        "task_name": task_name,
                        "ok": False,
                        "method": _safe_read_interface_field(task, "method"),
                        "url": _safe_read_interface_field(task, "url"),
                        "status_code": None,
                        "duration_ms": None,
                        "outputs": {},
                        "error": str(exc),
                    }
                )
                if continue_on_error:
                    continue
                return {
                    "success": False,
                    "message": f"场景执行失败：{task_name}",
                    "outputs": outputs,
                    "task_results": task_results,
                }

    return {
        "success": True,
        "message": "场景执行完成",
        "outputs": outputs,
        "task_results": task_results,
    }


def _extract_interface_config(task: dict[str, Any], *, index: int) -> dict[str, Any]:
    interface = task.get("interface")
    if not isinstance(interface, dict):
        raise HttpExecutionError(f"第 {index + 1} 个任务缺少 interface 配置")

    method = str(interface.get("method") or "").strip().upper()
    url = str(interface.get("url") or "").strip()
    if not method:
        raise HttpExecutionError(f"第 {index + 1} 个任务的 interface.method 不能为空")
    if not url:
        raise HttpExecutionError(f"第 {index + 1} 个任务的 interface.url 不能为空")

    headers = interface.get("headers") or {}
    if headers and not isinstance(headers, dict):
        raise HttpExecutionError(f"第 {index + 1} 个任务的 interface.headers 必须是对象")

    return {
        "method": method,
        "url": url,
        "content_type": str(interface.get("contentType") or "").strip(),
        "headers": {str(key): _stringify_header_value(value) for key, value in dict(headers).items()},
        "query": copy.deepcopy(interface.get("query") or interface.get("queryParams") or {}),
        "params": copy.deepcopy(interface.get("params")),
        "body": copy.deepcopy(interface.get("body")),
        "json": copy.deepcopy(interface.get("json")),
    }


def _send_interface_request(client: httpx.Client, interface: dict[str, Any]) -> httpx.Response:
    request_kwargs: dict[str, Any] = {
        "method": interface["method"],
        "url": interface["url"],
        "headers": interface["headers"],
    }
    query = interface["query"]
    if query:
        if not isinstance(query, dict):
            raise HttpExecutionError("interface.query 必须是对象")
        request_kwargs["params"] = query

    content_type = interface["content_type"].lower()
    payload = interface["json"]
    if payload is None:
        payload = interface["body"]
    if payload is None:
        payload = interface["params"]

    if content_type == "multipart/form-data":
        request_kwargs["files"] = _build_multipart_files(payload)
    elif content_type == "application/x-www-form-urlencoded":
        request_kwargs["data"] = _coerce_mapping_payload(payload, field_name="interface.params")
    elif content_type == "application/json":
        request_kwargs["json"] = payload
    elif payload is not None:
        if isinstance(payload, (dict, list)):
            request_kwargs["json"] = payload
        else:
            request_kwargs["content"] = _stringify_body_value(payload)

    response = client.request(**request_kwargs)
    response.raise_for_status()
    return response


def _apply_input_bindings(task: dict[str, Any], bindings: list[dict[str, Any]], outputs: dict[str, Any]) -> None:
    for binding in bindings:
        target_path = str(binding.get("target_path") or "").strip()
        expression = str(binding.get("expression") or "").strip()
        if not target_path or not expression:
            continue
        resolved = _resolve_expression(expression, outputs)
        _set_by_path(task, target_path, resolved)


def _resolve_expression(expression: str, outputs: dict[str, Any]) -> Any:
    exact_match = VARIABLE_PATTERN.fullmatch(expression)
    if exact_match:
        variable_name = exact_match.group(1)
        if variable_name not in outputs:
            raise HttpExecutionError(f"变量未定义：{variable_name}")
        return copy.deepcopy(outputs[variable_name])

    def replacer(match: re.Match[str]) -> str:
        variable_name = match.group(1)
        if variable_name not in outputs:
            raise HttpExecutionError(f"变量未定义：{variable_name}")
        value = outputs[variable_name]
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    return VARIABLE_PATTERN.sub(replacer, expression)


def _extract_output_variables(definitions: list[dict[str, Any]], response_payload: dict[str, Any]) -> dict[str, Any]:
    produced: dict[str, Any] = {}
    body = response_payload["body"]
    wrapper = {
        "status_code": response_payload["status_code"],
        "headers": response_payload["headers"],
        "body": body,
        "text": response_payload["text"],
        "url": response_payload["url"],
    }

    for definition in definitions:
        name = str(definition.get("name") or "").strip()
        source_path = str(definition.get("source_path") or "").strip()
        if not name:
            continue
        if not source_path:
            produced[name] = copy.deepcopy(body)
            continue
        value = _get_by_path(body, source_path)
        if value is _MISSING:
            value = _get_by_path(wrapper, source_path)
        if value is _MISSING:
            raise HttpExecutionError(f"输出变量提取失败：{name} <- {source_path}")
        produced[name] = copy.deepcopy(value)
    return produced


def _build_response_payload(response: httpx.Response) -> dict[str, Any]:
    text = response.text
    try:
        body: Any = response.json()
    except ValueError:
        body = text
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": body,
        "text": text,
        "url": str(response.request.url),
    }


def _build_multipart_files(payload: Any) -> list[tuple[str, tuple[None, str]]]:
    mapping = _coerce_mapping_payload(payload, field_name="interface.params")
    parts: list[tuple[str, tuple[None, str]]] = []
    for key, value in mapping.items():
        parts.append((str(key), (None, _stringify_body_value(value))))
    return parts


def _coerce_mapping_payload(payload: Any, *, field_name: str) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise HttpExecutionError(f"{field_name} 必须是对象")
    return payload


def _stringify_body_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _stringify_header_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_read_interface_field(task: dict[str, Any], key: str) -> str | None:
    interface = task.get("interface")
    if not isinstance(interface, dict):
        return None
    value = interface.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _set_by_path(root: dict[str, Any], path: str, value: Any) -> None:
    segments = [segment for segment in path.split(".") if segment]
    if not segments:
        raise HttpExecutionError("变量 target_path 不能为空")

    current: Any = root
    for segment in segments[:-1]:
        if not isinstance(current, dict):
            raise HttpExecutionError(f"变量 target_path 非法：{path}")
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            next_value = {}
            current[segment] = next_value
        current = next_value

    if not isinstance(current, dict):
        raise HttpExecutionError(f"变量 target_path 非法：{path}")
    current[segments[-1]] = value


def _get_by_path(root: Any, path: str) -> Any:
    segments = [segment for segment in path.split(".") if segment]
    current = root
    for segment in segments:
        if isinstance(current, dict):
            if segment not in current:
                return _MISSING
            current = current[segment]
            continue
        if isinstance(current, list):
            try:
                index = int(segment)
            except ValueError:
                return _MISSING
            if index < 0 or index >= len(current):
                return _MISSING
            current = current[index]
            continue
        return _MISSING
    return current
