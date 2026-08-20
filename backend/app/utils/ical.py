"""iCal 格式生成工具"""
from datetime import date, datetime


def generate_ics(goal_title: str, tasks: list[dict]) -> str:
    """
    生成 iCal 格式的日历数据

    Args:
        goal_title: 目标标题（作为日历名称）
        tasks: 任务列表，每个任务包含 id, title, description, scheduled_date, status

    Returns:
        iCal 格式的字符串
    """
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Daybreak//PlanAgent//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{goal_title}",
    ]

    for task in tasks:
        if not task.get("scheduled_date"):
            continue

        scheduled = task["scheduled_date"]
        if isinstance(scheduled, str):
            dt = datetime.fromisoformat(scheduled)
        elif isinstance(scheduled, date):
            dt = datetime.combine(scheduled, datetime.min.time())
        else:
            continue

        dt_str = dt.strftime("%Y%m%d")
        uid = f"task-{task['id']}@planagent"

        status = "COMPLETED" if task.get("status") == "done" else "TENTATIVE"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE=DATE:{dt_str}",
            f"DTEND;VALUE=DATE:{dt_str}",
            f"SUMMARY:{task['title']}",
            f"DESCRIPTION:{task.get('description', '')}",
            f"STATUS:{status}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
