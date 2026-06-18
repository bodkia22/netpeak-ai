from enum import Enum

from pydantic import BaseModel


class Category(str, Enum):
    """Allowed request categories."""

    AUTOMATION = "автоматизація"
    INTEGRATION = "інтеграція"
    REPORT = "звіт/аналітика"
    BUG = "баг/підтримка"
    QUESTION = "питання/консультація"
    OUT_OF_SCOPE = "поза скоупом"


class Priority(str, Enum):
    """Allowed urgency levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RequestClassification(BaseModel):
    """Structured classification result for a single incoming request."""

    category: Category
    target_department: str | None
    priority: Priority
    short_summary: str
    requested_actions: list[str]
    needs_clarification: bool