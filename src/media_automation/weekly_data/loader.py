from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if data is None:
        raise ValueError("YAML 파일이 비어 있습니다.")

    if not isinstance(data, dict):
        raise ValueError("Weekly Data의 최상위 구조는 객체여야 합니다.")

    return data