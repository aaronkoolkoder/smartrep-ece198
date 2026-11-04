"""An exponential moving average smooths noise without storing a window."""
class EMA:
    def __init__(self, alpha):
        if not 0 < alpha <= 1:
            raise ValueError("EMA alpha must be in (0, 1]")
        self.alpha = alpha
        self.value = None

    def update(self, value):
        self.value = value if self.value is None else self.value + self.alpha * (value - self.value)
        return self.value
