from enum import Enum

from pydantic import BaseModel, Field


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

    category: Category = Field(
        description="Категорія запиту з фіксованого переліку."
    )
    target_department: str | None = Field(
        description="Відділ-замовник, якщо видно з тексту (напр. 'HR', 'продажі'). "
        "null, якщо з тексту незрозуміло."
    )
    priority: Priority = Field(
        description="Пріоритет запиту, виведений з тону й змісту тексту."
    )
    short_summary: str = Field(
        description="Суть запиту одним реченням українською."
    )
    requested_actions: list[str] = Field(
        description="Список конкретних дій, які просять виконати. "
        "Порожній список, якщо конкретного прохання немає."
    )
    needs_clarification: bool = Field(
        description="True, якщо запит надто розмитий, щоб брати в роботу без уточнень."
    )