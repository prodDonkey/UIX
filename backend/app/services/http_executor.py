from __future__ import annotations

import copy
import json
import re
import subprocess
import time
from typing import Any

import httpx

from app.core.config import settings
from app.services.scene_compiler import load_task_snapshot, task_snapshot_variable_meta

VARIABLE_PATTERN = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
PATH_SEGMENT_PATTERN = re.compile(r"([^\.\[\]]+)|\[(\d+)\]")
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
            runtime_defaults = _build_runtime_defaults()

            try:
                runtime_variables = {**runtime_defaults, **outputs}
                _apply_input_bindings(task, variable_meta["inputs"], runtime_variables)
                interface_config = _extract_interface_config(task, index=index)
                interface_config = _apply_known_variables(interface_config, runtime_variables)
                _ensure_interface_variables_resolved(interface_config)
                start_at = time.perf_counter()
                response = _send_interface_request(client, interface_config)
                duration_ms = int((time.perf_counter() - start_at) * 1000)
                response_payload = _build_response_payload(response)
                _raise_for_business_error(response_payload)
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

    try:
        response = client.request(**request_kwargs)
        response.raise_for_status()
        return response
    except httpx.ConnectError as exc:
        # 某些企业站点在当前 Python/OpenSSL 组合下会触发 SSL EOF，curl 可正常握手。
        response = _send_interface_request_with_curl(interface, request_kwargs)
        response.raise_for_status()
        return response
    except httpx.HTTPError:
        raise


def _apply_input_bindings(task: dict[str, Any], bindings: list[dict[str, Any]], variables: dict[str, Any]) -> None:
    for binding in bindings:
        target_path = str(binding.get("target_path") or "").strip()
        expression = str(binding.get("expression") or "").strip()
        if not target_path or not expression:
            continue
        resolved = _resolve_expression(expression, variables)
        _set_by_path(task, target_path, resolved)


def _resolve_expression(expression: str, outputs: dict[str, Any]) -> Any:
    expression = _normalize_variable_placeholders(expression)
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
    parsed_resp_msg = _parse_resp_msg(body)
    wrapper = {
        "respMsg": parsed_resp_msg if parsed_resp_msg is not _MISSING else body,
        "response": body,
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


def _parse_resp_msg(body: Any) -> Any:
    if not isinstance(body, dict):
        return _MISSING
    resp_msg = body.get("respMsg")
    if not isinstance(resp_msg, str):
        return _MISSING
    try:
        return json.loads(resp_msg)
    except ValueError:
        return _MISSING


def _raise_for_business_error(response_payload: dict[str, Any]) -> None:
    body = response_payload["body"]
    url = str(response_payload.get("url") or "")
    text = str(response_payload.get("text") or "")
    parsed_resp_msg = _parse_resp_msg(body)

    if "zzsso.zhuanspirit.com/login" in url or "zzsso.zhuanspirit.com/login" in text:
        raise HttpExecutionError("接口调用失败：登录态已失效，需要重新登录后刷新 Cookie")

    if isinstance(body, dict) and int(body.get("status", 0) or 0) == -3:
        desc = str(body.get("desc") or "调用接口错误").strip() or "调用接口错误"
        raise HttpExecutionError(f"接口调用失败：{desc}，可能是 Cookie 已失效，需要重新登录")

    if isinstance(parsed_resp_msg, dict):
        code = parsed_resp_msg.get("code")
        if isinstance(code, int) and code != 0:
            message = str(
                parsed_resp_msg.get("errorMsg") or parsed_resp_msg.get("errMsg") or parsed_resp_msg.get("message") or ""
            ).strip()
            if message:
                raise HttpExecutionError(f"接口业务失败：{message}")
            raise HttpExecutionError(f"接口业务失败：code={code}")


def _ensure_interface_variables_resolved(interface: dict[str, Any]) -> None:
    unresolved = sorted(_collect_unresolved_variables(interface))
    if unresolved:
        joined = ", ".join(unresolved)
        raise HttpExecutionError(f"缺少执行变量：{joined}")


def _build_runtime_defaults() -> dict[str, Any]:
    defaults = {
        "cookie": settings.getresult_cookie,
        "uid": settings.getresult_uid,
        "addressId": settings.getresult_address_id,
        "appointmentTime": settings.getresult_appointment_time,
    }
    return {key: value for key, value in defaults.items() if value not in (None, "")}


def _apply_known_variables(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return _resolve_known_variables(value, variables)
    if isinstance(value, dict):
        return {key: _apply_known_variables(nested, variables) for key, nested in value.items()}
    if isinstance(value, list):
        return [_apply_known_variables(item, variables) for item in value]
    return value


def _resolve_known_variables(expression: str, variables: dict[str, Any]) -> Any:
    expression = _normalize_variable_placeholders(expression)
    exact_match = VARIABLE_PATTERN.fullmatch(expression)
    if exact_match:
        variable_name = exact_match.group(1)
        if variable_name in variables:
            return copy.deepcopy(variables[variable_name])
        return expression

    def replacer(match: re.Match[str]) -> str:
        variable_name = match.group(1)
        if variable_name not in variables:
            return match.group(0)
        value = variables[variable_name]
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    return VARIABLE_PATTERN.sub(replacer, expression)


def _normalize_variable_placeholders(expression: str) -> str:
    return expression.replace(r"\${", "${")


def _collect_unresolved_variables(value: Any) -> set[str]:
    if isinstance(value, str):
        return {match.group(1) for match in VARIABLE_PATTERN.finditer(value)}
    if isinstance(value, dict):
        unresolved: set[str] = set()
        for nested in value.values():
            unresolved.update(_collect_unresolved_variables(nested))
        return unresolved
    if isinstance(value, list):
        unresolved: set[str] = set()
        for nested in value:
            unresolved.update(_collect_unresolved_variables(nested))
        return unresolved
    return set()


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


def _send_interface_request_with_curl(interface: dict[str, Any], request_kwargs: dict[str, Any]) -> httpx.Response:
    command = [
        "curl",
        "-sS",
        "-L",
        "-X",
        interface["method"],
        interface["url"],
        "-D",
        "-",
        "--max-time",
        "30",
    ]

    for key, value in (request_kwargs.get("headers") or {}).items():
        command.extend(["-H", f"{key}: {value}"])

    if "params" in request_kwargs and request_kwargs["params"]:
        for key, value in dict(request_kwargs["params"]).items():
            command.extend(["--get", "--data-urlencode", f"{key}={_stringify_body_value(value)}"])

    if "json" in request_kwargs:
        command.extend(["-H", "Content-Type: application/json", "--data-raw", json.dumps(request_kwargs["json"], ensure_ascii=False)])
    elif "data" in request_kwargs:
        for key, value in dict(request_kwargs["data"]).items():
            command.extend(["--data-urlencode", f"{key}={_stringify_body_value(value)}"])
    elif "files" in request_kwargs:
        for key, file_tuple in request_kwargs["files"]:
            field_value = file_tuple[1] if isinstance(file_tuple, tuple) and len(file_tuple) > 1 else file_tuple
            command.extend(["-F", f"{key}={_stringify_body_value(field_value)}"])
    elif "content" in request_kwargs:
        command.extend(["--data-raw", _stringify_body_value(request_kwargs["content"])])

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise HttpExecutionError(result.stderr.strip() or "curl 执行失败")

    raw_output = result.stdout
    separator = "\r\n\r\n" if "\r\n\r\n" in raw_output else "\n\n"
    parts = [part for part in raw_output.split(separator) if part.strip()]
    if not parts:
        raise HttpExecutionError("curl 未返回任何响应")

    response_text = parts[-1]
    header_block = ""
    for candidate in reversed(parts[:-1]):
        if candidate.lstrip().startswith("HTTP/"):
            header_block = candidate
            break
    if not header_block and parts[0].lstrip().startswith("HTTP/"):
        header_block = parts[0]

    status_code = 200
    headers: dict[str, str] = {}
    if header_block:
        header_lines = [line for line in header_block.splitlines() if line.strip()]
        if header_lines:
            first_line = header_lines[0].strip()
            match = re.search(r"HTTP/\S+\s+(\d{3})", first_line)
            if match:
                status_code = int(match.group(1))
            for line in header_lines[1:]:
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()

    request = httpx.Request(interface["method"], interface["url"], headers=request_kwargs.get("headers"))
    return httpx.Response(status_code=status_code, headers=headers, text=response_text, request=request)


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
    segments = _parse_path(path, field_name="target_path")
    if not segments:
        raise HttpExecutionError("变量 target_path 不能为空")

    current: Any = root
    for index, segment in enumerate(segments[:-1]):
        next_segment = segments[index + 1]
        container = [] if isinstance(next_segment, int) else {}
        if isinstance(segment, str):
            if not isinstance(current, dict):
                raise HttpExecutionError(f"变量 target_path 非法：{path}")
            next_value = current.get(segment)
            if not isinstance(next_value, (dict, list)):
                next_value = copy.deepcopy(container)
                current[segment] = next_value
            current = next_value
            continue
        if not isinstance(current, list):
            raise HttpExecutionError(f"变量 target_path 非法：{path}")
        if segment < 0:
            raise HttpExecutionError(f"变量 target_path 非法：{path}")
        while len(current) <= segment:
            current.append(copy.deepcopy(container))
        next_value = current[segment]
        if not isinstance(next_value, (dict, list)):
            next_value = copy.deepcopy(container)
            current[segment] = next_value
        current = next_value

    last_segment = segments[-1]
    if isinstance(last_segment, str):
        if not isinstance(current, dict):
            raise HttpExecutionError(f"变量 target_path 非法：{path}")
        current[last_segment] = value
        return
    if not isinstance(current, list):
        raise HttpExecutionError(f"变量 target_path 非法：{path}")
    if last_segment < 0:
        raise HttpExecutionError(f"变量 target_path 非法：{path}")
    while len(current) <= last_segment:
        current.append(None)
    current[last_segment] = value


def _get_by_path(root: Any, path: str) -> Any:
    try:
        segments = _parse_path(path, field_name="source_path")
    except HttpExecutionError:
        return _MISSING
    current = root
    for segment in segments:
        if isinstance(current, dict):
            if not isinstance(segment, str) or segment not in current:
                return _MISSING
            current = current[segment]
            continue
        if isinstance(current, list):
            if not isinstance(segment, int):
                return _MISSING
            if segment < 0 or segment >= len(current):
                return _MISSING
            current = current[segment]
            continue
        return _MISSING
    return current


def _parse_path(path: str, *, field_name: str) -> list[str | int]:
    tokens: list[str | int] = []
    for raw_segment in [segment for segment in path.split(".") if segment]:
        consumed = ""
        for match in PATH_SEGMENT_PATTERN.finditer(raw_segment):
            consumed += match.group(0)
            key = match.group(1)
            index = match.group(2)
            if key is not None:
                tokens.append(key)
                continue
            tokens.append(int(index))
        if consumed != raw_segment:
            raise HttpExecutionError(f"变量 {field_name} 非法：{path}")
    return tokens
