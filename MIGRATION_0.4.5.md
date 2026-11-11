# Migrating to PySig 0.4.5

## Calculation method

Existing files default to the time-sliced engine. Select the analytical engine with:

```yaml
calculation:
  method: analytical
```

The first analytical release supports fixed-time, independent-lane intersection
models. It deliberately rejects network links and shared-lane interactions.

## Phase sequences

Legacy files derive one sequence per controller from phase order. Explicit form:

```yaml
phase_sequences:
  - id: SEQ_C1
    controller_id: C1
    phase_ids: [P_A, P_B, P_C]
```

A signal group appearing in consecutive phases is continuous. The intermediate
phase intergreen is not applied to that signal group.

## Priority movements

Use the corrected key names:

```yaml
movement_conflicts:
  - yielding_movement_id: R_WS
    priority_movement_ids: [T_EW, L_ES]
    active_capacity_factor: 0.40
```

The old `gives_way_to` spelling remains accepted. The historical misspelling
`yeilding_movement_id` is accepted for migration but should be corrected.

## LOS

The default LOS output is a queueing-delay screening classification. It must not
be described as formal HCM control-delay LOS.
