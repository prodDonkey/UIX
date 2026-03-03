from __future__ import annotations

import re

import httpx

from app.core.config import settings


def _resolve_llm_config(model_override: str | None = None) -> tuple[str, str, str]:
    # Generation prefers LLM_* config for explicit model isolation.
    # Fallback to MIDSCENE_* if LLM_* is not configured.
    base_url = settings.llm_base_url or settings.midscene_model_base_url or "https://open.bigmodel.cn/api/paas/v4"
    api_key = settings.llm_api_key or settings.midscene_model_api_key
    model_name = model_override or settings.llm_model_name or settings.midscene_model_name
    if not api_key or not model_name:
        raise ValueError("Model not configured: set LLM_API_KEY/LLM_MODEL_NAME (or MIDSCENE_* fallback)")
    return base_url.rstrip("/"), api_key, model_name


def _build_generation_prompt(prompt: str, device_id: str | None, language: str) -> tuple[str, str]:
    lang_hint = "中文" if language.lower().startswith("zh") else "英文"
    device_line = (
        f'如果提供了 deviceId，请将 android.deviceId 设置为 "{device_id}"。'
        if device_id
        else "android.deviceId 是可选字段；不要凭空编造设备 ID。"
    )
    system = (
        "你是 Midscene Android YAML 脚本生成器。"
        "只返回可执行的 YAML 本体，不要返回 Markdown 代码块，不要解释说明。"
        "脚本必须满足结构：android（对象）、tasks（非空数组），每个 task 必须包含 name 和 flow。"
        "flow 中可使用 aiAction、aiQuery、aiAssert、sleep、log。"
        f"{device_line} "
        "交互步骤优先使用 aiAction。"
    )
    user = (
        f"语言偏好：{lang_hint}\n"
        "请把下面需求转换为可执行的 Midscene Android YAML：\n"
        f"{prompt}"
    )
    return system, user


def _extract_yaml(raw: str) -> str:
    fenced = re.search(r"```(?:yaml)?\n([\s\S]*?)```", raw, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    return raw.strip()


async def generate_yaml_from_prompt(
    prompt: str,
    device_id: str | None = None,
    language: str = "zh",
    model_override: str | None = None,
) -> str:
    base_url, api_key, model_name = _resolve_llm_config(model_override)
    system, user = _build_generation_prompt(prompt, device_id, language)

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }

    headers = {"Authorization": f"Bearer {api_key}"}
    endpoint = f"{base_url}/chat/completions"

    async with httpx.AsyncClient(timeout=settings.llm_timeout_sec) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return _extract_yaml(content)
