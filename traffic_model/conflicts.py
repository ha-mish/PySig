"""Priority and yielding movement relationships."""


def conflict_for(model, movement_id):
    return next(
        (x for x in model.conflicts if x.yielding_movement_id == movement_id),
        None,
    )


def active_capacity_factor(model, movement_id, active_movement_ids):
    """Return the most restrictive active priority factor for a movement."""
    conflicts = [
        x
        for x in model.conflicts
        if x.yielding_movement_id == movement_id
        and any(mid in active_movement_ids for mid in x.priority_movement_ids)
    ]
    return min((x.active_capacity_factor for x in conflicts), default=1.0)
