def create_calculation_engine(method):
    if method == "simulation":
        from .simulation import SimulationEngine

        return SimulationEngine()
    if method == "analytical":
        from .analytical import AnalyticalEngine

        return AnalyticalEngine()
    raise ValueError(
        f"Unknown calculation method {method!r}; expected 'simulation' or 'analytical'"
    )


def calculate(model, movement_flows, controllers=None):
    return create_calculation_engine(model.calculation_method).calculate(
        model, movement_flows, controllers
    )
