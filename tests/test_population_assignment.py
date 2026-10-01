import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mewgenics.populations.assignment import (
    apply_newborn_assignments,
    assign_cat_and_peers,
    unassigned_room_peers,
)
from mewgenics.populations.repository import AssignmentState


def _cat(uid, room="Attic", generation=0, status="In House", parents=False):
    return SimpleNamespace(
        unique_id=uid,
        room=room,
        generation=generation,
        status=status,
        parent_a=object() if parents else None,
        parent_b=None,
    )


def test_room_peers_include_only_unassigned_living_cats_in_same_room():
    selected = _cat("selected")
    eligible = _cat("eligible")
    assigned = _cat("assigned")
    elsewhere = _cat("elsewhere", room="Cellar")
    gone = _cat("gone", status="Gone")

    peers = unassigned_room_peers(
        selected, [selected, eligible, assigned, elsewhere, gone], {"assigned": "ranged"}
    )

    assert [cat.unique_id for cat in peers] == ["eligible"]


def test_assign_cat_and_peers_never_overwrites_existing_assignment():
    selected, peer, existing = _cat("selected"), _cat("peer"), _cat("existing")
    state = AssignmentState(assignments={"existing": "ranged"})

    result = assign_cat_and_peers(selected, "fighter", [peer, existing], state)

    assert result.assignments == {
        "selected": "fighter", "peer": "fighter", "existing": "ranged"
    }


def test_moving_assigned_cat_does_not_change_assignment():
    cat = _cat("cat", room="Cellar")
    state = AssignmentState(assignments={"cat": "fighter"})

    result = apply_newborn_assignments({"cat"}, [cat], state)

    assert result.assignments["cat"] == "fighter"


def test_stray_remains_unassigned():
    resident = _cat("resident")
    stray = _cat("stray", generation=0)
    state = AssignmentState(assignments={"resident": "fighter"})

    result = apply_newborn_assignments({"resident"}, [resident, stray], state)

    assert "stray" not in result.assignments


def test_newborn_inherits_from_fully_assigned_homogeneous_room():
    residents = [_cat("a"), _cat("b")]
    newborn = _cat("baby", generation=1, parents=True)
    state = AssignmentState(assignments={"a": "fighter", "b": "fighter"})

    result = apply_newborn_assignments({"a", "b"}, residents + [newborn], state)

    assert result.assignments["baby"] == "fighter"


def test_mixed_partially_unassigned_and_empty_rooms_do_not_assign():
    cases = [
        ([_cat("a"), _cat("b")], {"a": "fighter", "b": "ranged"}),
        ([_cat("a"), _cat("b")], {"a": "fighter"}),
        ([], {}),
    ]
    for residents, assignments in cases:
        baby = _cat("baby", room="Attic", generation=1, parents=True)
        state = AssignmentState(assignments=assignments)
        result = apply_newborn_assignments(
            {cat.unique_id for cat in residents}, residents + [baby], state
        )
        assert "baby" not in result.assignments


def test_siblings_use_only_preexisting_residents():
    first = _cat("first", generation=1, parents=True)
    second = _cat("second", generation=1, parents=True)
    state = AssignmentState(assignments={"first": "fighter"})

    result = apply_newborn_assignments(set(), [first, second], state)

    assert "second" not in result.assignments


def test_gone_residents_do_not_influence_homogeneity():
    living = _cat("living")
    gone = _cat("gone", status="Gone")
    baby = _cat("baby", generation=1, parents=True)
    state = AssignmentState(assignments={"living": "fighter", "gone": "ranged"})

    result = apply_newborn_assignments({"living", "gone"}, [living, gone, baby], state)

    assert result.assignments["baby"] == "fighter"
