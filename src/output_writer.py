import json
from collections import Counter
from src.models import RequestClassification


def write_output_json(classifications: list[RequestClassification], file_path: str) -> None:
    """Write the full structured classification result for all requests to a JSON file."""
    data = [item.model_dump(mode="json") for item in classifications]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)



def write_report(classifications: list[RequestClassification], file_path: str) -> None:
    """Write a Markdown summary report with aggregates by category, priority, and department."""
    by_category = Counter(item.category.value for item in classifications)
    by_priority = Counter(item.priority.value for item in classifications)
    by_department = Counter(item.target_department or "не визначено" for item in classifications)
    needs_clarification = [
        (item.request_id, item.short_summary)
        for item in classifications
        if item.needs_clarification
    ]

    lines = ["# Звіт по класифікації запитів", ""]

    lines.append("## По категоріях")
    for category, count in by_category.most_common():
        lines.append(f"- {category}: {count}")
    lines.append("")

    lines.append("## По пріоритету")
    for priority, count in by_priority.most_common():
        lines.append(f"- {priority}: {count}")
    lines.append("")

    lines.append("## По відділах")
    for department, count in by_department.most_common():
        lines.append(f"- {department}: {count}")
    lines.append("")

    lines.append(f"## Потребують уточнення ({len(needs_clarification)})")
    if needs_clarification:
        for request_id, summary in needs_clarification:
            lines.append(f"- **{request_id}**: {summary}")
    else:
        lines.append("Немає.")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))