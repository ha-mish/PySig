# PySig 0.4.4 integration notes

This update is designed to be applied to the current public PySig source.

## 1. Copy new modules

Copy into `traffic_model/`:

- `timing.py`
- `output_rounding.py`

## 2. Extend the model settings

Add these fields to the main model/domain dataclass, with defaults:

```python
start_displacement_s: float = 3.0
end_displacement_s: float = 3.0
```

In `loader.py`, read:

```python
start_displacement_s = float(
    settings.get("lane_start_displacement_s", 3.0)
)
end_displacement_s = float(
    settings.get("lane_end_displacement_s", 3.0)
)
```

Pass both values into the model constructor.

## 3. Extend lane and movement result dataclasses

Replace the ambiguous fields with explicit quantities:

```python
cycle_time_s: float
signal_green_s: float
start_displacement_s: float
end_displacement_s: float
effective_green_s: float
effective_green_ratio: float
saturation_flow_pcu_per_hour: float
nominal_capacity_pcu_per_hour: float
nominal_degree_of_saturation: float
simulated_service_capacity_pcu_per_hour: float
simulated_degree_of_saturation: float
```

For one release, retain compatibility aliases in serialised output if desired:

```python
capacity_pcu_per_hour = simulated_service_capacity_pcu_per_hour
degree_of_saturation = simulated_degree_of_saturation
```

Document those aliases as deprecated.

## 4. Use effective timing in simulation

For each lane/controller/signal group:

```python
from .timing import (
    green_time,
    nominal_capacity_pcu_per_hour,
    nominal_degree_of_saturation,
)

timing = green_time(
    controller=controller,
    signal_group_id=movement.signal_group_id,
    start_displacement_s=model.start_displacement_s,
    end_displacement_s=model.end_displacement_s,
)

nominal_capacity = nominal_capacity_pcu_per_hour(
    saturation_flow_pcu_per_hour=saturation,
    effective_green_ratio=timing.effective_green_ratio,
)
nominal_dos = nominal_degree_of_saturation(
    demand_pcu_per_hour=demand,
    nominal_capacity=nominal_capacity,
)
```

The time-sliced service window must use the same displacement assumptions. A
signal group is effectively serving when the cycle-local time is between the
phase green start plus start displacement and the phase green end plus end
displacement. Intergreen itself is not added wholesale to green.

## 5. Round outputs only

In `output.py`, apply `round_output()` after constructing the complete serialised
dictionary and to every CSV row. Do not round values inside assignment,
simulation, queue, cost or optimisation calculations.

```python
from .output_rounding import round_output

data = round_output(rich_result(...))
```

## 6. Add tests

Copy both supplied test files to `tests/` and add one integration test using the
normal example model to assert that displayed green excludes intergreen and that
the final selected controller timing appears in the rich result.

## 7. Update LaTeX

Copy the supplied chapter into `docs/manual/chapters/` and add this line to
`pysig_manual.tex` after the results/testing chapter:

```latex
\input{chapters/12_traffic_engineering_methodology}
```

## 8. Version and changelog

Update the package version to `0.4.4` and add the supplied CHANGELOG entry.
