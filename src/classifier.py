from anthropic import Anthropic
from anthropic.types import ToolUseBlock

from src.config import settings
from src.models import RequestClassification
from src.prompts import SYSTEM_PROMPT

client = Anthropic(api_key=settings.anthropic_api_key)

TOOL_NAME = "classify_request"

INPUT_SCHEMA = RequestClassification.model_json_schema()

CLASSIFY_TOOL = {
    "name": TOOL_NAME,
    "description": "Classify an internal request into structured fields.",
    "input_schema": INPUT_SCHEMA,
}


def classify_request(raw_text: str) -> RequestClassification:
    """Send a single request's text to the LLM and return its validated classification."""
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        temperature=0,
        system=SYSTEM_PROMPT,
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": raw_text}],
    )

    tool_use_block = next(
        block for block in response.content if isinstance(block, ToolUseBlock)
    )

    return RequestClassification(**tool_use_block.input)