import json

from src.models import RequestClassification


def write_output_json(classifications: list[RequestClassification], file_path: str) -> None:
    """Write the full structured classification result for all requests to a JSON file."""
    data = [item.model_dump(mode="json") for item in classifications]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)