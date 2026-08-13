import calendar
from datetime import date, timedelta
from typing import Literal

DurationUnit = Literal["day", "week", "month"]


def calculate_target_date(start_date: date, value: int, unit: DurationUnit) -> date:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("duration_value 蹇呴』涓烘鏁存暟")
    if unit == "day":
        return start_date + timedelta(days=value)
    if unit == "week":
        return start_date + timedelta(days=value * 7)
    if unit == "month":
        month_index = start_date.year * 12 + start_date.month - 1 + value
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(start_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    raise ValueError("duration_unit 蹇呴』涓?day銆亀eek 鎴?month")
