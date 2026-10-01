from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Sequence

from save_parser import Cat

from .repository import AssignmentState, KnownCat


_INACTIVE_STATUSES = {"Gone", "Dead"}


def unassigned_room_peers(
    selected: Cat,
    cats: Sequence[Cat],
    assignments: Mapping[str, str],
) -> tuple[Cat, ...]:
    return tuple(
        cat
        for cat in cats
        if cat.unique_id != selected.unique_id
        and cat.room == selected.room
        and cat.status not in _INACTIVE_STATUSES
        and cat.unique_id not in assignments
    )


def assign_cat_and_peers(
    selected: Cat,
    population_id: str,
    peers: Sequence[Cat],
    state: AssignmentState,
) -> AssignmentState:
    assignments = dict(state.assignments)
    assignments[selected.unique_id] = population_id
    for cat in peers:
        assignments.setdefault(cat.unique_id, population_id)
    return replace(state, assignments=assignments)


def apply_newborn_assignments(
    previous_known_ids: set[str],
    cats: Sequence[Cat],
    state: AssignmentState,
) -> AssignmentState:
    assignments = dict(state.assignments)
    known_cats = dict(state.known_cats)
    preexisting = {
        cat.unique_id: cat
        for cat in cats
        if cat.unique_id in previous_known_ids
        and cat.status not in _INACTIVE_STATUSES
    }

    for cat in cats:
        if cat.unique_id in previous_known_ids or cat.unique_id in assignments:
            continue
        is_newborn = bool(
            getattr(cat, "generation", 0) > 0
            or getattr(cat, "parent_a", None) is not None
            or getattr(cat, "parent_b", None) is not None
        )
        if not is_newborn:
            continue
        residents = [resident for resident in preexisting.values() if resident.room == cat.room]
        if not residents or any(resident.unique_id not in assignments for resident in residents):
            continue
        populations = {assignments[resident.unique_id] for resident in residents}
        if len(populations) == 1:
            assignments[cat.unique_id] = populations.pop()

    for cat in cats:
        known_cats.setdefault(
            cat.unique_id,
            KnownCat(cat.room or "", int(getattr(cat, "generation", 0) or 0)),
        )
    return AssignmentState(assignments, known_cats)
