import pandas as pd

from src.models import IncomingRequest


def read_requests(file_path: str) -> list[IncomingRequest]:
    """Read incoming requests from a CSV file and parse them into validated models."""
    df = pd.read_csv(file_path).fillna("")
    return [IncomingRequest(**row) for row in df.to_dict(orient="records")]