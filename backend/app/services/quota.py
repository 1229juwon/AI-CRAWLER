class QuotaUnavailable(RuntimeError):
    """Raised when a task must wait instead of retrying an API call."""


class QuotaLedger:
    def __init__(self, daily_limit: int) -> None:
        if daily_limit < 0:
            raise ValueError("daily_limit must not be negative")
        self.daily_limit = daily_limit
        self.consumed = 0

    @property
    def remaining(self) -> int:
        return self.daily_limit - self.consumed

    def reserve(self, cost: int) -> None:
        if cost < 0:
            raise ValueError("quota cost must not be negative")
        if cost > self.remaining:
            raise QuotaUnavailable(
                f"quota unavailable: requested={cost}, remaining={self.remaining}"
            )
        self.consumed += cost
