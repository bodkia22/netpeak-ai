import pandas as pd


def read_requests(file_path: str) -> pd.DataFrame:
    """Read incoming requests from a CSV file into a DataFrame."""
    return pd.read_csv(file_path)