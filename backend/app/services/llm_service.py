from __future__ import annotations

import logging
from time import perf_counter
import re
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


def _resolve_llm_config(model_override: str | None = None) -> tuple[str, str, str]:
    # Generation prefers LLM_* config for explicit model isolation.
    # Fallback to MIDSCENE_* if LLM_* is not configured.
    base_url = settings.llm_base_url or settings.midscene_model_base_url or "https://open.bigmodel.cn/api/paas/v4"
    api_key = settings.llm_api_key or settings.midscene_model_api_key
    model_name = model_override or settings.llm_model_name or settings.midscene_model_name
    if not api_key or not model_name:
        raise ValueError("Model not configured: set LLM_API_KEY/LLM_MODEL_NAME (or MIDSCENE_* fallback)")
    return base_url.rstrip("/"), api_key, model_name


DEFAULT_SYSTEM_PROMPT_TEMPLATE = (
    "你是 Midscene Android YAML 脚本生成器。"
    "只输出 YAML 本体。"
    "必须包含 android 和非空 tasks。"
    "{device_rule}"
)


def _resolve_system_prompt_template() -> str:
    inline = settings.llm_generation_system_prompt.strip()
    if inline:
        return inline

    prompt_file = settings.llm_generation_system_prompt_file.strip()
    if prompt_file:
        prompt_path = Path(prompt_file).expanduser()
        if not prompt_path.is_absolute():
            backend_root = Path(__file__).resolve().parents[2]
            prompt_path = backend_root / prompt_path
        return prompt_path.read_text(encoding="utf-8").strip()

    return DEFAULT_SYSTEM_PROMPT_TEMPLATE


def _build_generation_prompt(prompt: str, device_id: str | None, language: str) -> tuple[str, str]:
    lang_hint = "中文" if language.lower().startswith("zh") else "英文"
    if device_id:
        device_rule = f'用户已提供 deviceId（{device_id}），必须写入 android.deviceId。'
    else:
        device_rule = "用户未提供 deviceId，不要生成 android.deviceId 字段。"

    system = _resolve_system_prompt_template().replace("{device_rule}", device_rule)
    user = (
        f"语言偏好：{lang_hint}\n"
        f"deviceId: {device_id if device_id else '(未提供)'}\n"
        "请将以下需求转换为可执行 Midscene Android YAML：\n"
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
    started_at = perf_counter()
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
    logger.info(
        "AI YAML 开始调用模型：model=%s base_url=%s language=%s has_device_id=%s prompt_len=%s",
        model_name,
        base_url,
        language,
        bool(device_id),
        len(prompt),
    )

    async with httpx.AsyncClient(timeout=settings.llm_timeout_sec) as client:
        try:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            yaml_text = _extract_yaml(content)
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            logger.info(
                "AI YAML 模型调用成功：status=%s elapsed_ms=%s output_len=%s",
                response.status_code,
                elapsed_ms,
                len(yaml_text),
            )
            return yaml_text
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            logger.exception("AI YAML 模型调用失败：elapsed_ms=%s error=%s", elapsed_ms, exc)
            raise
