from pydantic import BaseModel
import yaml


class ValidationResult(BaseModel):
    valid: bool
    line: int | None = None
    column: int | None = None
    message: str | None = None


def validate_yaml_content(content: str) -> ValidationResult:
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        return ValidationResult(
            valid=False,
            line=(mark.line + 1) if mark else None,
            column=(mark.column + 1) if mark else None,
            message=str(exc),
        )

    if not isinstance(parsed, dict):
        return ValidationResult(valid=False, message="YAML root must be an object")

    android = parsed.get("android")
    tasks = parsed.get("tasks")

    if not isinstance(android, dict):
        return ValidationResult(valid=False, message="Missing or invalid 'android' section")

    if not android.get("deviceId"):
        return ValidationResult(valid=False, message="Missing 'android.deviceId'")

    if not isinstance(tasks, list) or len(tasks) == 0:
        return ValidationResult(valid=False, message="Missing or empty 'tasks' list")

    return ValidationResult(valid=True)
