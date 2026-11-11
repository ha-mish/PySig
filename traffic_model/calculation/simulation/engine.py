class SimulationEngine:
    def calculate(self, model, movement_flows, controllers=None):
        from ...simulation import simulate

        return simulate(model, movement_flows, controllers)
