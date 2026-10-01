from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from .loader import load_yaml
from .models import (
    FridayInPersonData,
    WeeklyData,
    WeeklyStatus,
    parse_weekly_data,
)


class ValidationState(str, Enum):
    VALID = "VALID"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ValidationResult:
    state: ValidationState
    data: WeeklyData | None = None
    unresolved: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


def _collect_unset_paths(
    value: Any,
    path: str = "",
) -> list[str]:
    found: list[str] = []

    if isinstance(value, BaseModel):
        status = getattr(value, "status", None)

        if status == WeeklyStatus.UNSET:
            found.append(path or value.__class__.__name__)

        for field_name in value.__class__.model_fields:
            child = getattr(value, field_name)

            child_path = (
                f"{path}.{field_name}"
                if path
                else field_name
            )

            found.extend(
                _collect_unset_paths(child, child_path)
            )

    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(
                _collect_unset_paths(
                    child,
                    f"{path}[{index}]",
                )
            )

    return found


def _format_pydantic_errors(
    exc: ValidationError,
) -> tuple[str, ...]:
    messages: list[str] = []

    for error in exc.errors():
        location = ".".join(
            str(part) for part in error["loc"]
        )

        messages.append(
            f"{location}: {error['msg']}"
        )

    return tuple(messages)


def validate_weekly_file(
    path: str | Path,
) -> ValidationResult:
    try:
        raw = load_yaml(path)
        data = parse_weekly_data(raw)

    except ValidationError as exc:
        return ValidationResult(
            state=ValidationState.INVALID,
            errors=_format_pydantic_errors(exc),
        )

    except (
        OSError,
        ValueError,
        yaml.YAMLError,
    ) as exc:
        return ValidationResult(
            state=ValidationState.INVALID,
            errors=(str(exc),),
        )

    # 금요 대면은 아직 상세 스키마가 확정되지 않았다.
    if isinstance(data, FridayInPersonData):
        return ValidationResult(
            state=ValidationState.INCOMPLETE,
            data=data,
            unresolved=(
                "friday.in_person 상세 스키마 미확정",
            ),
        )

    unresolved = tuple(
        _collect_unset_paths(data)
    )

    if unresolved:
        return ValidationResult(
            state=ValidationState.INCOMPLETE,
            data=data,
            unresolved=unresolved,
        )

    return ValidationResult(
        state=ValidationState.VALID,
        data=data,
    )