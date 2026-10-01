import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from types import SimpleNamespace

from mewgenics.populations import AssignmentState, Population, TraitCategory, TraitRef
from mewgenics.populations.copying import CopyMode
from mewgenics.views.population_widgets import (
    CopyScoresDialog,
    NullableScoreEditor,
    PopulationEditor,
    TraitScoreTable,
)
from mewgenics.views.population_scoring import PopulationScoringView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_nullable_editor_distinguishes_blank_zero_and_range(app):
    editor = NullableScoreEditor()
    assert editor.score() is None

    editor.set_score(0)
    assert editor.score() == 0

    editor.set_score(-99)
    assert editor.score() == -99
    with pytest.raises(ValueError):
        editor.set_score(100)

    editor.set_score(None)
    assert editor.score() is None


def test_trait_table_lists_encountered_traits_and_filters_reviewed_zero(app):
    population = Population.create("Fighter", "fighter").with_score(
        TraitCategory.PASSIVE, "reviewed", 0
    )
    encountered = [
        TraitRef(TraitCategory.PASSIVE, "reviewed", "Reviewed"),
        TraitRef(TraitCategory.MUTATION, "missing", "Missing"),
    ]
    table = TraitScoreTable()
    table.set_population(
        population,
        encountered,
        {"reviewed": 2, "missing": 1},
        {
            (TraitCategory.PASSIVE, "reviewed"): "A reviewed passive description.",
            (TraitCategory.MUTATION, "missing"): "Head Mutation (ID 12)\nMissing\n+2 STR",
        },
    )

    assert table.visible_trait_keys() == ["reviewed", "missing"]
    assert table.table.columnCount() == 5
    assert table.table.horizontalHeaderItem(2).text() == "Description"
    assert table.table.item(0, 2).text() == "A reviewed passive description."
    assert table.table.item(1, 2).text() == "+2 STR"
    assert "Head Mutation" in table.table.item(1, 2).toolTip()
    table.set_needs_review_only(True)
    assert table.visible_trait_keys() == ["missing"]


def test_population_editor_defaults_validate_names(app):
    editor = PopulationEditor([
        Population.create("Fighter", "fighter"), Population.create("Ranged", "ranged")
    ])

    assert editor.population_names() == ["Fighter", "Ranged"]
    with pytest.raises(ValueError):
        editor.validate_new_name(" ")
    with pytest.raises(ValueError):
        editor.validate_new_name("fighter")


def test_copy_dialog_defaults_to_all_categories_and_fill_unset(app):
    source = Population.create("Fighter", "fighter").with_score(
        TraitCategory.MUTATION, "strong", 3
    )
    destination = Population.create("Ranged", "ranged").with_score(
        TraitCategory.MUTATION, "strong", 1
    )
    dialog = CopyScoresDialog([source, destination], destination.id)

    assert dialog.selected_categories() == set(TraitCategory)
    assert dialog.copy_mode() is CopyMode.FILL_UNSET
    assert "Preserve: 57" in dialog.preview_label.text()

    dialog.overwrite.setChecked(True)
    assert "Overwrite: 57" in dialog.preview_label.text()


def _cat(uid, name, room="Attic", **traits):
    values = {
        "unique_id": uid,
        "name": name,
        "room": room,
        "status": "In House",
        "generation": 0,
        "parent_a": None,
        "parent_b": None,
        "abilities": [],
        "passive_abilities": [],
        "mutations": [],
        "disorders": [],
        "defects": [],
        "mutation_chip_items": [],
        "defect_chip_items": [],
    }
    values.update(traits)
    return SimpleNamespace(**values)


def test_view_supplies_ability_mutation_and_missing_descriptions(app, tmp_path, monkeypatch):
    monkeypatch.setitem(
        __import__("mewgenics.utils.abilities", fromlist=["_ABILITY_DESC"])._ABILITY_DESC,
        "scratch",
        "Deal damage to an adjacent enemy.",
    )
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    cat = _cat(
        "cat",
        "Cat",
        abilities=["scratch"],
        mutations=["Strong Head"],
        disorders=["UnknownDisorder"],
        mutation_chip_items=[("Strong Head", "Head Mutation (ID 12)\nStrong Head\n+2 STR")],
    )

    view.set_cats([cat])

    descriptions = {
        view.trait_table.table.item(row, 1).text(): view.trait_table.table.item(row, 2).text()
        for row in range(view.trait_table.table.rowCount())
    }
    assert descriptions["scratch"] == "Deal damage to an adjacent enemy."
    assert descriptions["Strong Head"] == "+2 STR"
    assert descriptions["UnknownDisorder"] == "No description available"


def test_trait_table_supports_numeric_and_additive_column_sorting(app):
    population = (
        Population.create("Fighter", "fighter")
        .with_score(TraitCategory.PASSIVE, "alpha", 10)
        .with_score(TraitCategory.PASSIVE, "beta", 2)
    )
    traits = [
        TraitRef(TraitCategory.PASSIVE, "alpha", "Alpha"),
        TraitRef(TraitCategory.PASSIVE, "beta", "Beta"),
        TraitRef(TraitCategory.MUTATION, "gamma", "Gamma"),
    ]
    table = TraitScoreTable()
    table.set_population(population, traits, {"alpha": 2, "beta": 10, "gamma": 1})

    assert table.sort_summary() == "Category ↑, Trait ↑"
    table.set_sort_column(3, additive=False)
    table.set_sort_column(3, additive=False)
    assert table.visible_trait_keys() == ["beta", "alpha", "gamma"]
    assert table.sort_summary() == "Cats ↓"

    table.set_sort_column(4, additive=False)
    table.set_sort_column(4, additive=False)
    assert table.visible_trait_keys() == ["alpha", "beta", "gamma"]
    assert table.sort_summary() == "Score ↓"

    table.set_sort_column(0, additive=False)
    table.set_sort_column(1, additive=True)
    assert table.sort_summary() == "Category ↑, Trait ↑"


def test_roster_defaults_to_room_then_score_descending_and_can_sort_name(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    cats = [
        _cat("b", "Bravo", room="B", abilities=["high"]),
        _cat("a-low", "Alpha Low", room="A", abilities=["low"]),
        _cat("a-high", "Alpha High", room="A", abilities=["high"]),
    ]
    view.set_cats(cats)
    for cat in cats:
        view.assign_population(cat.unique_id, "fighter", include_room_peers=False)
    view.set_trait_score("fighter", TraitCategory.ACTIVE_ABILITY, "high", 5)
    view.set_trait_score("fighter", TraitCategory.ACTIVE_ABILITY, "low", 1)

    assert [view.table.item(row, 0).text() for row in range(3)] == [
        "Alpha High", "Alpha Low", "Bravo"
    ]
    assert view.roster_sort_summary() == "Room ↑, Score ↓"

    view.set_roster_sort_column(0, additive=False)
    assert [view.table.item(row, 0).text() for row in range(3)] == [
        "Alpha High", "Alpha Low", "Bravo"
    ]
    view.set_roster_sort_column(0, additive=False)
    assert [view.table.item(row, 0).text() for row in range(3)] == [
        "Bravo", "Alpha Low", "Alpha High"
    ]


def test_view_lists_all_base_stat_values_and_allows_population_override(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    cat = _cat("cat", "Cat", base_stats={
        "STR": 7, "DEX": 6, "CON": 5, "INT": 4, "SPD": 3, "CHA": 2, "LCK": 1,
    })
    view.set_cats([cat])
    view.assign_population("cat", "fighter", include_room_peers=False)

    stat_rows = [
        view.trait_table.table.item(row, 1).text()
        for row in range(view.trait_table.table.rowCount())
        if view.trait_table.table.item(row, 0).text() == TraitCategory.BASE_STAT.value
    ]
    assert len(stat_rows) == 56
    assert "STR = 0" in stat_rows
    assert "LCK = 7" in stat_rows
    assert view.score_for("cat").total == -7

    view.set_trait_score("fighter", TraitCategory.BASE_STAT, "str:7", 10)

    assert view.score_for("cat").total == 1


def test_roster_shows_unassigned_unresolved_and_complete_states(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    view.set_save_path(str(tmp_path / "campaign.sav"))
    cat = _cat("cat", "Mittens", abilities=["scratch"])
    view.set_cats([cat])
    assert view.review_state_for("cat") == "?"

    view.assign_population("cat", "fighter", include_room_peers=False)
    assert view.review_state_for("cat") == "!"
    assert view.score_for("cat").total == 0

    view.set_trait_score("fighter", TraitCategory.ACTIVE_ABILITY, "scratch", 0)
    assert view.review_state_for("cat") == ""
    assert view.score_for("cat").is_complete


def test_room_assignment_does_not_overwrite_existing_population(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    view.set_save_path(str(tmp_path / "campaign.sav"))
    cats = [_cat("selected", "Selected"), _cat("peer", "Peer"), _cat("existing", "Existing")]
    view.set_cats(cats)
    view.assign_population("existing", "ranged", include_room_peers=False)

    view.assign_population("selected", "fighter", include_room_peers=True)

    assert view.assignment_for("selected") == "fighter"
    assert view.assignment_for("peer") == "fighter"
    assert view.assignment_for("existing") == "ranged"


def test_editing_shared_trait_recomputes_all_cats(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    view.set_save_path(str(tmp_path / "campaign.sav"))
    cats = [_cat("a", "A", abilities=["scratch"]), _cat("b", "B", abilities=["scratch"])]
    view.set_cats(cats)
    view.assign_population("a", "fighter", include_room_peers=True)

    view.set_trait_score("fighter", TraitCategory.ACTIVE_ABILITY, "scratch", 3)

    assert view.score_for("a").total == 3
    assert view.score_for("b").total == 3


def test_refresh_preserves_unset_editor_state(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    view.set_save_path(str(tmp_path / "campaign.sav"))
    cat = _cat("cat", "Cat", abilities=["scratch"])
    view.set_cats([cat])
    view.assign_population("cat", "fighter", include_room_peers=False)
    assert view.trait_score("fighter", TraitCategory.ACTIVE_ABILITY, "scratch") is None

    view.set_cats([cat])

    assert view.trait_score("fighter", TraitCategory.ACTIVE_ABILITY, "scratch") is None


def test_add_and_rename_population_require_unique_names(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    population = view.add_population("  Support  ")

    assert population.name == "Support"
    view.rename_population(population.id, "Healer")
    assert "Healer" in view.population_editor.population_names()
    with pytest.raises(ValueError):
        view.rename_population(population.id, "fighter")


def test_copy_population_scores_supports_fill_and_overwrite(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    view.set_trait_score("fighter", TraitCategory.MUTATION, "strong", 4)
    view.set_trait_score("ranged", TraitCategory.MUTATION, "strong", 1)
    view.set_trait_score("fighter", TraitCategory.PASSIVE, "focused", 2)

    view.copy_population_scores(
        "fighter", "ranged", set(TraitCategory), CopyMode.FILL_UNSET
    )
    assert view.trait_score("ranged", TraitCategory.MUTATION, "strong") == 1
    assert view.trait_score("ranged", TraitCategory.PASSIVE, "focused") == 2

    view.copy_population_scores(
        "fighter", "ranged", {TraitCategory.MUTATION}, CopyMode.OVERWRITE
    )
    assert view.trait_score("ranged", TraitCategory.MUTATION, "strong") == 4


def test_overwrite_copy_requires_confirmation(app, tmp_path, monkeypatch):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    view.set_trait_score("fighter", TraitCategory.MUTATION, "strong", 4)
    view.set_trait_score("ranged", TraitCategory.MUTATION, "strong", 1)

    class AcceptedOverwriteDialog:
        def __init__(self, *_args):
            pass

        def exec(self):
            return True

        def source_population_id(self):
            return "fighter"

        def selected_categories(self):
            return {TraitCategory.MUTATION}

        def copy_mode(self):
            return CopyMode.OVERWRITE

    monkeypatch.setattr(
        "mewgenics.views.population_scoring.CopyScoresDialog", AcceptedOverwriteDialog
    )
    monkeypatch.setattr(
        "mewgenics.views.population_scoring.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.No,
    )

    view._prompt_copy_scores("ranged")

    assert view.trait_score("ranged", TraitCategory.MUTATION, "strong") == 1


def test_delete_unassigns_and_undo_restores_affected_cats(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    view.set_save_path(str(tmp_path / "campaign.sav"))
    view.set_cats([_cat("cat", "Cat")])
    view.assign_population("cat", "fighter", include_room_peers=False)

    deleted = view.delete_population("fighter")
    assert view.assignment_for("cat") is None
    assert "Fighter" not in view.population_editor.population_names()

    view.undo_delete(deleted)
    assert view.assignment_for("cat") == "fighter"
    assert "Fighter" in view.population_editor.population_names()


def test_delete_undo_preserves_newer_reassignment(app, tmp_path):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    view.set_save_path(str(tmp_path / "campaign.sav"))
    view.set_cats([_cat("cat", "Cat")])
    view.assign_population("cat", "fighter", include_room_peers=False)

    deleted = view.delete_population("fighter")
    view.assign_population("cat", "ranged", include_room_peers=False)
    view.undo_delete(deleted)

    assert view.assignment_for("cat") == "ranged"


def test_delete_confirmation_cancellation_keeps_population(app, tmp_path, monkeypatch):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    monkeypatch.setattr(
        "mewgenics.views.population_scoring.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.No,
    )

    view._confirm_delete_population("fighter")

    assert "Fighter" in view.population_editor.population_names()


def test_unknown_saved_population_id_is_treated_as_unassigned(app, tmp_path):
    save_path = tmp_path / "campaign.sav"
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    view.set_save_path(str(save_path))
    view._assignment_repository.save(AssignmentState(assignments={"cat": "removed"}))

    view.set_save_path(str(save_path))
    view.set_cats([_cat("cat", "Cat")])

    assert view.assignment_for("cat") is None
    assert view.review_state_for("cat") == "?"
    assert view.unknown_assignment_for("cat") == "removed"

    view.save_session_state()
    assert view._assignment_repository.load().assignments["cat"] == "removed"


def test_failed_population_save_keeps_edit_in_memory_for_retry(app, tmp_path, monkeypatch):
    view = PopulationScoringView(population_path=str(tmp_path / "populations.json"))
    calls = {"count": 0}

    def fail_once(_populations):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("disk full")

    monkeypatch.setattr(view._population_repository, "save", fail_once)
    population = view.add_population("Support")

    assert population.id in {item.id for item in view._populations}
    assert view.has_pending_persistence
    assert view.retry_persistence()
    assert not view.has_pending_persistence
