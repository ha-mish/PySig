# Integrating PySig 0.4.5a

Replace:

- `traffic_model/calculation/results.py`
- `traffic_model/calculation/analytical/queue.py`
- `traffic_model/calculation/analytical/engine.py`

Add:

- `traffic_model/calculation/analytical/shared_lane.py`
- `tests/test_analytical_agro_arrow.py`
- `docs/manual/chapters/16_agro_arrow_shared_lanes.tex`

Add to `docs/manual/pysig_manual.tex`:

```latex
\input{chapters/16_agro_arrow_shared_lanes}
```

This release supports analytical shared lanes with different signal groups by
using expected geometric front blocking. Analytical network links and ARR 340
exponential discharge are reserved for 0.4.5b and 0.4.5c respectively.
