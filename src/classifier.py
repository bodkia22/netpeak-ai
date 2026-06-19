import asyncio

from anthropic import AsyncAnthropic
from anthropic.types import ToolUseBlock
from pydantic import ValidationError

from src.config import settings
from src.models import Category, Priority, RequestClassification
from src.prompts import SYSTEM_PROMPT

client = AsyncAnthropic(api_key=settings.anthropic_api_key)

TOOL_NAME = "classify_request"

INPUT_SCHEMA = RequestClassification.model_json_schema()

CLASSIFY_TOOL = {
    "name": TOOL_NAME,
    "description": "Classify an internal request into structured fields.",
    "input_schema": INPUT_SCHEMA,
}

async def classify_request(raw_text: str, request_id: str) -> RequestClassification:
    """Classify a request via the LLM, retrying on failure. Returns a fallback
    result instead of raising if all attempts are exhausted."""
    last_error: Exception | None = None

    for attempt in range(1, settings.max_retries + 1):
        try:
            response = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                temperature=0,
                system=SYSTEM_PROMPT,
                tools=[CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": raw_text}],
            )

            tool_use_block = next(
                (block for block in response.content if isinstance(block, ToolUseBlock)),
                None,
            )

            if tool_use_block is None:
                raise ValueError(
                    f"LLM did not return a tool_use block (stop_reason={response.stop_reason})"
                )

            return RequestClassification(**tool_use_block.input, request_id=request_id)

        except ValidationError as exc:
            last_error = exc
            print(f"[{request_id}] Attempt {attempt}: LLM returned data that failed schema validation: {exc}")

        except Exception as exc:
            last_error = exc
            print(f"[{request_id}] Attempt {attempt}: API call failed: {exc}")

        if attempt < settings.max_retries:
            await asyncio.sleep(2 ** attempt)

    print(f"[{request_id}] All {settings.max_retries} attempts failed: {last_error}")
    return _fallback_classification(request_id, last_error)


def _fallback_classification(request_id: str, error: Exception | None) -> RequestClassification:
    """Placeholder result for a request that couldn't be classified after retries."""
    return RequestClassification(
        request_id=request_id,
        reasoning="Класифікація не виконана: усі спроби звернення до LLM завершились помилкою.",
        confidence="low",
        category=Category.OUT_OF_SCOPE,
        target_department=None,
        priority=Priority.LOW,
        short_summary=f"Не вдалося класифікувати автоматично: {error}",
        requested_actions=[],
        needs_clarification=True,
    )