from fastapi import APIRouter, HTTPException, status

from app.schemas.script import ScriptGenerateRequest, ScriptGenerateResponse
from app.services.llm_service import generate_yaml_from_prompt
from app.services.yaml_validator import validate_yaml_content

router = APIRouter(prefix="/api/scripts", tags=["scripts-generate"])


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

    validate_result = validate_yaml_content(generated_yaml)
    if not validate_result.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": validate_result.message,
                "line": validate_result.line,
                "column": validate_result.column,
                "yaml": generated_yaml,
            },
        )

    warnings: list[str] = []
    if payload.device_id is None:
        warnings.append("deviceId 未提供，运行时请通过环境变量或参数指定。")

    return ScriptGenerateResponse(yaml=generated_yaml, warnings=warnings)

