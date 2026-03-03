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
    lang_hint = "中文" if language.lower().startswith("zh") else "English"
    device_line = (
        f'If provided, set android.deviceId to "{device_id}".'
        if device_id
        else "android.deviceId is optional; do not invent fake values."
    )
    system = (
        "You generate Midscene Android YAML scripts only. "
        "Return valid YAML only, no markdown fences, no explanations. "
        "Use this structure: android (object), tasks (non-empty list), each task has name and flow list. "
        "Flow actions can use aiAction, aiQuery, aiAssert, sleep, log. "
        f"{device_line} "
        "Prefer aiAction for interaction steps."
    )
    user = (
        f"Language hint: {lang_hint}\n"
        "Convert the following requirement into executable Midscene Android YAML:\n"
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
