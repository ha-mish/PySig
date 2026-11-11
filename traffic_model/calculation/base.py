"""Common calculation-engine protocol."""
from typing import Protocol


class CalculationEngine(Protocol):
    def calculate(self, model, movement_flows, controllers=None):
        ...
