# PySig Future Development Specification: 0.4.5b and 0.4.5c

**Status:** Deferred implementation specification  
**Baseline:** PySig 0.4.5a  
**Purpose:** Preserve the agreed design for analytical network links/spillback and ARR 340 queue-discharge modelling while these items are on hold.

---

## 1. Release sequence

The agreed development sequence is:

- **0.4.5a:** analytical shared lanes with different signal groups using expected front blocking (agro-arrow case).
- **0.4.5b:** analytical inter-intersection network links, deterministic travel time, finite storage and spillback.
- **0.4.5c:** optional ARR 340-informed queue-discharge model replacing the instantaneous constant-saturation service assumption.

0.4.5b and 0.4.5c must build on the event-driven analytical engine. Neither feature should be implemented by introducing a fixed time step into analytical mode.

---

# Part A - PySig 0.4.5b: Analytical Network Links and Spillback

## 2. Objective

Extend the analytical engine from isolated intersections to connected signalised intersections while retaining continuous/event-driven queue evolution.

The network model must represent:

1. upstream movement departures;
2. deterministic link travel time;
3. downstream arrivals;
4. finite link storage;
5. downstream receiving restrictions;
6. spillback to the upstream intersection;
7. queue and flow conservation throughout.

---

## 3. Network-link model

A network link connects an upstream movement to a downstream movement:

```yaml
network_links:
  - id: LINK_I1_I2
    from_intersection_id: I1
    to_intersection_id: I2
    upstream_movement_id: M1_E
    downstream_movement_id: M2_W
    length_m: 500
    speed_kmh: 60
    storage_pcu: 65
```

### 3.1 Free-flow travel time

For link length `L` in metres and speed `v` in km/h:

```text
t_ff = 3.6 L / v
```

Example:

```text
L = 500 m
v = 60 km/h

t_ff = 30 s
```

A departure-flow segment from the upstream intersection is shifted forward by this exact travel time to form the corresponding downstream arrival segment.

### 3.2 Link occupancy

Let `N(t)` be PCU occupying the link:

```text
dN/dt = q_in(t) - q_out(t)
```

with:

```text
0 <= N(t) <= K_link
```

where `K_link` is `storage_pcu`.

For constant inflow and outflow over an interval:

```text
N1 = N0 + (q_in - q_out) dt
```

If `q_in > q_out`, exact time to full storage is:

```text
t_full = (K_link - N0) / (q_in - q_out)
```

This storage boundary becomes a new analytical event.

---

## 4. Spillback

Spillback begins when the link reaches its finite storage limit while downstream discharge remains insufficient to accommodate upstream inflow.

At full storage:

```text
upstream receiving capacity <= downstream release rate
```

The upstream movement must therefore be supply constrained even if its own signal is green and it otherwise has available saturation capacity.

### 4.1 Spillback event chain

```text
Downstream effective red / restricted service
            ↓
Downstream queue or link occupancy increases
            ↓
Link reaches K_link
            ↓
SPILLBACK START event
            ↓
Upstream receiving capacity is restricted
            ↓
Upstream lane queue may grow
            ↓
Downstream service releases storage
            ↓
SPILLBACK CLEAR event
            ↓
Upstream receiving capacity restored
```

### 4.2 Required analytical events

The network event queue must support at least:

- signal-group effective service start;
- signal-group effective service end;
- priority state change;
- agro-arrow front blocking;
- queue clearance;
- link inflow segment start/end;
- shifted arrival segment start/end;
- link reaches storage;
- link leaves full storage;
- spillback begins;
- spillback clears;
- demand-profile change;
- analysis horizon.

Use a chronological priority queue (for example, Python `heapq`) with deterministic tie handling.

---

## 5. Departure and arrival profiles

The analytical network should represent flow as piecewise-constant or piecewise-analytical segments rather than arrays indexed by a simulation time step.

Suggested object:

```python
@dataclass(frozen=True, slots=True)
class FlowSegment:
    start_s: float
    end_s: float
    rate_pcu_per_s: float
    source_id: str | None = None
```

An upstream departure segment:

```text
20-40 s at 0.5 PCU/s
```

on a 30-second link becomes:

```text
50-70 s at 0.5 PCU/s
```

at the downstream stop line before dispersion.

---

## 6. Initial 0.4.5b scope

Support:

- deterministic free-flow travel time;
- one upstream movement to one downstream movement per link;
- finite link storage;
- downstream receiving restriction;
- spillback;
- exact event timing;
- no overtaking;
- no stochastic travel time;
- no lane changing within links;
- no merge/diverge node model initially;
- no analytical platoon dispersion initially.

Reject unsupported merge/diverge configurations explicitly rather than silently simplifying them.

---

## 7. Network result contract

Add analytical link results compatible with common outputs:

```python
@dataclass(frozen=True, slots=True)
class AnalyticalLinkResult:
    link_id: str
    free_flow_time_s: float
    inflow_pcu: float
    outflow_pcu: float
    final_occupancy_pcu: float
    maximum_occupancy_pcu: float
    maximum_storage_utilisation: float
    spillback_seconds: float
    spillback_start_s: float | None
    flow_restricted_by_spillback_pcu: float
```

`AnalyticalResult` then reports:

```text
links
maximum_link_storage_utilisation
```

from actual analytical results rather than hard-coded zero values.

---

## 8. Conservation requirements

For every isolated link over the reporting horizon:

```text
initial occupancy + inflow
=
outflow + final occupancy + explicitly modelled rejected inflow
```

For the full network:

```text
fixed OD demand
=
completed trips + vehicles remaining in lanes + vehicles occupying links
+ explicitly reported blocked/overflow demand
```

No traffic may disappear because storage is full.

---

## 9. 0.4.5b tests

Required unit/regression cases:

### Travel time

- 500 m at 60 km/h gives exactly 30 seconds.
- A 20-40 s upstream departure segment arrives at 50-70 s.

### Link occupancy

- constant inflow/outflow analytical occupancy;
- exact time to empty;
- exact time to full;
- no negative occupancy;
- no occupancy above storage.

### Spillback

- downstream red causes storage growth;
- storage-full event occurs at the hand-calculated time;
- upstream discharge becomes receiving constrained;
- downstream green releases storage;
- spillback-clear event occurs correctly;
- upstream restriction is removed after clearance.

### Conservation

- link conservation identity;
- network vehicle conservation;
- OD conservation unaffected by network storage.

### Comparison

For cases representable by both engines:

- compare analytical results with increasingly small simulation time slices;
- expect simulation to converge toward the analytical result;
- do not require equality at finite simulation resolution.

---

# Part B - PySig 0.4.5c: ARR 340 Queue-Discharge Model

## 10. Objective

Replace the optional analytical assumption of an instantaneous step from zero service to constant saturation-flow service with a calibrated queue-discharge relationship informed by:

**Akçelik, R., Besley, M. and Roper, R. (1999), _Fundamental Relationships for Traffic Flows at Signalised Intersections_, Research Report ARR 340, ARRB Transport Research Ltd.**

The ARR 340 reference is particularly relevant because it reports Australian empirical observations from signalised intersections in Sydney and Melbourne, including:

- queue-discharge headways;
- queue-discharge flow and speed;
- saturation headway and saturation flow;
- departure response time;
- start loss;
- end gain;
- jam spacing;
- queue-clearance wave speed;
- downstream interference at paired intersections.

---

## 11. Current PySig service assumption

The basic analytical engine currently uses:

```text
mu(t) = 0                     outside effective service
mu(t) = saturation flow       during effective service
```

This is a useful transparent baseline but implies immediate saturation discharge once effective service begins.

0.4.5c should retain this as:

```yaml
queue_discharge:
  method: constant_saturation
```

and add a second explicitly selected method:

```yaml
queue_discharge:
  method: arr340_exponential
```

---

## 12. Discharge-model interface

Introduce:

```python
class QueueDischargeModel(Protocol):
    def rate(
        self,
        elapsed_service_s: float,
        saturation_flow_pcu_per_hour: float,
    ) -> float:
        ...

    def cumulative_service(
        self,
        start_elapsed_s: float,
        end_elapsed_s: float,
        saturation_flow_pcu_per_hour: float,
    ) -> float:
        ...
```

Proposed module:

```text
traffic_model/
└── calculation/
    └── analytical/
        └── discharge.py
```

Implementations:

```text
ConstantSaturationDischarge
ARR340ExponentialDischarge
```

---

## 13. ARR 340 implementation rule

Do **not** derive the 0.4.5c equation from an abstract, summary page or memory.

Before implementation:

1. transcribe the exact relevant ARR 340 equations;
2. identify every parameter and unit;
3. identify the applicable vehicle/PCU convention;
4. identify recommended/default/calibrated parameter values, if any;
5. identify equation applicability conditions;
6. reproduce at least one published numerical/calibration example where possible;
7. record the citation and equation/table reference in code comments and the user guide.

If the report provides related but distinct models for flow, headway and speed, select the model appropriate to PySig's service-rate formulation and document why.

---

## 14. Queue clearance with variable service

With a non-constant discharge rate, queue clearance time `t_c` solves:

```text
Q0
+ integral(arrival_rate(t), t0..tc)
- integral(service_rate(t), t0..tc)
= 0
```

For constant arrivals:

```text
Q0 + a (tc - t0) - cumulative_service(t0, tc) = 0
```

The engine should solve this event time by:

- a closed-form solution where available from the selected ARR 340 equation; or
- a deterministic root solver with explicit tolerances and iteration limits.

The solver becomes part of the analytical event system. Queue clearance is not rounded to a time step.

---

## 15. Start loss and end gain

ARR 340 terminology must be reconciled explicitly with PySig's existing:

```yaml
lane_start_displacement_s
lane_end_displacement_s
```

The current PySig effective-green relationship is:

```text
g = G - start displacement + end displacement
```

Before 0.4.5c release, document whether these properties directly represent the ARR 340 start-loss/end-gain quantities or require revised names/definitions.

Do not double count an ARR 340 discharge-response effect and a separately applied start displacement if both represent the same physical phenomenon.

---

## 16. Queue-clearance wave and spatial queue

ARR 340 also provides context for queue-clearance-wave behaviour and jam spacing.

PySig must distinguish:

- **vertical/fluid queue:** PCU waiting over time;
- **estimated spatial queue:** PCU multiplied by configured spacing;
- **kinematic/shockwave queue:** spatial queue boundary governed by wave relationships.

0.4.5c may continue to report the simple spatial estimate:

```text
queue_m = queue_pcu * pcu_length_m
```

but must label it as an estimate unless the queue-clearance/shockwave model is actually implemented.

A future version may use ARR 340 jam spacing and clearance-wave relationships to improve spatial queue propagation.

---

## 17. 0.4.5c configuration

Suggested YAML:

```yaml
calculation:
  method: analytical
  queue_discharge:
    method: arr340_exponential
    parameters:
      # Exact parameter names to be defined from ARR 340.
```

Results must state:

```json
{
  "queue_discharge_method": "arr340_exponential",
  "queue_discharge_source": "ARR 340",
  "queue_discharge_parameters": {},
  "saturation_flow_pcu_per_hour": 1900.0
}
```

No hidden calibration values.

---

## 18. 0.4.5c tests

Required tests:

- constant-saturation method still reproduces existing analytical cases;
- exact ARR 340 rate at known published/calibrated points;
- cumulative-service calculation;
- cumulative service approaches the correct long-run saturation behaviour;
- start-loss/end-gain treatment does not double count;
- analytical queue-clearance root satisfies conservation;
- queue remains non-negative;
- service never becomes physically invalid;
- changing ARR 340 parameters moves outputs in the expected direction;
- published/hand-calculated benchmark case;
- user-guide equations match code equations.

---

# Part C - Combined Future Architecture

## 19. Target analytical package

```text
traffic_model/
└── calculation/
    └── analytical/
        ├── engine.py
        ├── events.py
        ├── queue.py
        ├── signals.py
        ├── shared_lane.py      # 0.4.5a
        ├── link.py             # 0.4.5b
        ├── network.py          # 0.4.5b
        ├── spillback.py        # 0.4.5b
        └── discharge.py        # 0.4.5c
```

---

## 20. Recommended implementation order when development resumes

### 0.4.5b

1. `FlowSegment` object.
2. Deterministic link time shifting.
3. Link occupancy conservation.
4. Exact storage-full/empty events.
5. Downstream receiving capacity.
6. Spillback to upstream movement.
7. Two-intersection corridor tests.
8. Common output integration.
9. User-guide chapter.

### 0.4.5c

1. Extract ARR 340 equations and parameters from the primary report.
2. Add discharge-model protocol.
3. Preserve constant-saturation implementation.
4. Implement ARR 340 rate and cumulative service.
5. Implement variable-service queue-clearance root solving.
6. Reconcile start loss/end gain with PySig displacement terminology.
7. Add published/calibrated benchmark tests.
8. Add methodology/audit output.
9. Update LaTeX documentation.

---

## 21. Deferred acceptance criteria

### 0.4.5b is complete when

- network departures become downstream arrivals at exact travel times;
- finite link occupancy is conserved;
- exact storage boundary events are generated;
- downstream congestion restricts upstream discharge;
- spillback start and clear times are reported;
- no vehicle/PCU disappears;
- network analytical outputs satisfy hand calculations;
- common output/optimisation interfaces remain usable;
- CI passes.

### 0.4.5c is complete when

- the exact selected ARR 340 model is documented and cited;
- equation parameters and units are explicit;
- constant and ARR 340 discharge are selectable;
- cumulative service is analytically available;
- queue-clearance events solve conservation to tolerance;
- start/end timing effects are not double counted;
- at least one published or hand-verifiable ARR 340 benchmark passes;
- output metadata makes the discharge methodology auditable;
- CI and LaTeX builds pass.

---

## 22. Key cautions

- Keep 0.4.5a stable while 0.4.5b and 0.4.5c are deferred.
- Do not reintroduce `time_slice_s` into analytical calculations.
- Do not implement network spillback by deleting excess link inflow.
- Do not permit link occupancy above storage.
- Do not silently simplify merges/diverges into one-to-one links.
- Do not invent ARR 340 coefficients.
- Do not mix ARR 340 headway, speed and flow equations without documenting their respective roles.
- Do not double count discharge response through both ARR 340 dynamics and start-loss displacement.
- Do not call PCU-times-spacing a dynamic shockwave queue.
- Maintain exact fixed-OD conservation throughout network analysis.
