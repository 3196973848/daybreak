class InsufficientCapacityError(ValueError):
    def __init__(self, required_hours, available_hours, minimum_days):
        self.required_hours = round(required_hours, 1)
        self.available_hours = round(available_hours, 1)
        self.minimum_days = minimum_days
        self.suggested_duration = {"value": minimum_days, "unit": "day"}
        super().__init__("当前时间不足")

    def as_detail(self):
        return {
            "code": "insufficient_capacity",
            "message": "当前时间不足",
            "required_hours": self.required_hours,
            "available_hours": self.available_hours,
            "minimum_days": self.minimum_days,
            "suggested_duration": self.suggested_duration,
        }
