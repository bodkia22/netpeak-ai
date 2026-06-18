from src.classifier import classify_request
from src.csv_reader import read_requests
from src.models import RequestClassification

INPUT_CSV_PATH = "input_requests.csv"


def main() -> None:
    """Read requests from the CSV and classify each one via the LLM."""
    requests = read_requests(INPUT_CSV_PATH)

    results: list[RequestClassification] = []
    for request in requests:
        classification = classify_request(request.raw_text)
        results.append(classification)
        print(f"[{request.id}] {classification.category.value} | {classification.priority.value}")

    print(f"\nClassified {len(results)} requests.")


if __name__ == "__main__":
    main()