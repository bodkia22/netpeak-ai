import asyncio

from src.classifier import classify_request
from src.csv_reader import read_requests
from src.models import IncomingRequest, RequestClassification
from src.output_writer import write_output_json, write_report
from src.config import settings
MAX_CONCURRENT_REQUESTS = 20


async def _classify_one(request: IncomingRequest, semaphore: asyncio.Semaphore) -> RequestClassification:
    """Classify a single request, limited by the semaphore."""
    async with semaphore:
        classification = await classify_request(request.raw_text, request.id)
        print(f"[{request.id}] {classification.category.value} | {classification.priority.value}")
        return classification


async def main() -> None:
    """Read requests from the CSV and classify them concurrently via the LLM."""
    requests = read_requests(settings.input_csv_path)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    tasks: list = []
    for request in requests:
        coroutine = _classify_one(request, semaphore)
        tasks.append(coroutine)

    results: list[RequestClassification] = await asyncio.gather(*tasks)

    print(f"\nClassified {len(results)} requests.")

    write_output_json(results, "output.json")
    write_report(results, "report.md")


if __name__ == "__main__":
    asyncio.run(main())