import pandas as pd
from pydantic import ValidationError

from src.models import IncomingRequest


def read_requests(file_path: str) -> list[IncomingRequest]:
    """Read incoming requests from a CSV file and parse them into validated models."""
    df = pd.read_csv(file_path).fillna("")

    requests: list[IncomingRequest] = []
    for row in df.to_dict(orient="records"):
        try:
            requests.append(IncomingRequest(**row))
        except ValidationError as exc:
            row_id = row.get("id", "?")
            print(f"[{row_id}] SKIPPED (invalid row): {exc}")

    return requests