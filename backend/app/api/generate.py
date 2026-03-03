import logging
from time import perf_counter

from fastapi import APIRouter, HTTPException, status
import yaml

from app.schemas.script import ScriptGenerateRequest, ScriptGenerateResponse
from app.services.llm_service import generate_yaml_from_prompt
from app.services.yaml_validator import validate_yaml_content

router = APIRouter(prefix="/api/scripts", tags=["scripts-generate"])
logger = logging.getLogger("uvicorn.error")

_PLACEHOLDER_DEVICE_IDS = {"", "test", "test-device", "android-device", "device-id"}


def _normalize_generated_yaml(raw_yaml: str) -> tuple[str, bool]:
    """Normalize model output to reduce common schema issues.

    Current rule:
    - If android.deviceId is provided as empty value, remove this key because
      deviceId is optional and may be injected at runtime.
    """
    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return raw_yaml, False

    if not isinstance(parsed, dict):
        return raw_yaml, False

    android = parsed.get("android")
    removed_placeholder_device = False
    if isinstance(android, dict):
        device_id = android.get("deviceId")
        if device_id is None:
            pass
        elif isinstance(device_id, str) and device_id.strip().lower() in _PLACEHOLDER_DEVICE_IDS:
            android.pop("deviceId", None)
            removed_placeholder_device = True

    normalized = yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True)
    return normalized, removed_placeholder_device


@router.post("/generate", response_model=ScriptGenerateResponse)
async def generate_script(payload: ScriptGenerateRequest) -> ScriptGenerateResponse:
    started_at = perf_counter()
    logger.info(
        "收到 AI YAML 生成请求：language=%s has_device_id=%s has_model_override=%s prompt_len=%s",
        payload.language,
        bool(payload.device_id),
        bool(payload.model),
        len(payload.prompt or ""),
    )
    try:
        generated_yaml = await generate_yaml_from_prompt(
            prompt=payload.prompt,
            device_id=payload.device_id,
            language=payload.language,
            model_override=payload.model,
        )
    except HTTPException:
        logger.exception("AI YAML 生成失败：HTTPException")
        raise
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        logger.exception("AI YAML 生成失败：elapsed_ms=%s error=%s", elapsed_ms, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"LLM generation failed: {exc}",
        ) from exc

    normalized_yaml, removed_placeholder_device = _normalize_generated_yaml(generated_yaml)
    validate_result = validate_yaml_content(normalized_yaml)
    if not validate_result.valid:
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        logger.warning(
            "AI YAML 校验失败：elapsed_ms=%s message=%s line=%s column=%s",
            elapsed_ms,
            validate_result.message,
            validate_result.line,
            validate_result.column,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": validate_result.message,
                "line": validate_result.line,
                "column": validate_result.column,
                "yaml": normalized_yaml,
            },
        )

    warnings: list[str] = []
    if payload.device_id is None:
        warnings.append("deviceId 未提供，运行时请通过环境变量或参数指定。")
    if removed_placeholder_device:
        warnings.append("已移除模型生成的占位 deviceId，请在运行前填写真实设备 ID。")

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "AI YAML 生成成功：elapsed_ms=%s yaml_len=%s warnings=%s",
        elapsed_ms,
        len(normalized_yaml),
        warnings if warnings else "[]",
    )
    return ScriptGenerateResponse(yaml=normalized_yaml, warnings=warnings)
