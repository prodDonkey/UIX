from fastapi import APIRouter, HTTPException, status
import yaml

from app.schemas.script import ScriptGenerateRequest, ScriptGenerateResponse
from app.services.llm_service import generate_yaml_from_prompt
from app.services.yaml_validator import validate_yaml_content

router = APIRouter(prefix="/api/scripts", tags=["scripts-generate"])


def _normalize_generated_yaml(raw_yaml: str) -> str:
    """Normalize model output to reduce common schema issues.

    Current rule:
    - If android.deviceId is provided as empty value, remove this key because
      deviceId is optional and may be injected at runtime.
    """
    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return raw_yaml

    if not isinstance(parsed, dict):
        return raw_yaml

    android = parsed.get("android")
    if isinstance(android, dict) and android.get("deviceId") in ("", None):
        android.pop("deviceId", None)

    return yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True)


@router.post("/generate", response_model=ScriptGenerateResponse)
async def generate_script(payload: ScriptGenerateRequest) -> ScriptGenerateResponse:
    try:
        generated_yaml = await generate_yaml_from_prompt(
            prompt=payload.prompt,
            device_id=payload.device_id,
            language=payload.language,
            model_override=payload.model,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"LLM generation failed: {exc}",
        ) from exc

    normalized_yaml = _normalize_generated_yaml(generated_yaml)
    validate_result = validate_yaml_content(normalized_yaml)
    if not validate_result.valid:
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

    return ScriptGenerateResponse(yaml=normalized_yaml, warnings=warnings)
