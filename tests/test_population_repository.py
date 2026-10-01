import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mewgenics.populations import Population, TraitCategory
from mewgenics.populations.repository import (
    AssignmentRepository,
    AssignmentState,
    KnownCat,
    PopulationRepository,
    RepositoryError,
)


def test_population_configuration_round_trips_all_categories_and_zero(tmp_path):
    path = tmp_path / "populations.json"
    population = Population.create("Fighter", "fighter")
    for category in TraitCategory:
        population = population.with_score(category, category.value, 0)

    PopulationRepository(str(path)).save([population])
    loaded = PopulationRepository(str(path)).load()

    assert loaded == [population]
    assert all(list(loaded[0].scores[c].values()) == [0] for c in TraitCategory)


def test_assignment_configuration_round_trips_known_cats(tmp_path):
    path = tmp_path / "save.populations.json"
    state = AssignmentState(
        assignments={"cat-1": "fighter"},
        known_cats={"cat-1": KnownCat("Attic", 1)},
    )

    AssignmentRepository(str(path)).save(state)

    assert AssignmentRepository(str(path)).load() == state


def test_missing_population_file_creates_only_defaults(tmp_path):
    populations = PopulationRepository(str(tmp_path / "missing.json")).load()

    assert [p.name for p in populations] == ["Fighter", "Ranged"]


def test_unknown_json_fields_are_ignored(tmp_path):
    path = tmp_path / "populations.json"
    path.write_text(json.dumps({
        "schemaVersion": 1,
        "future": True,
        "populations": [{"id": "x", "name": "Custom", "scores": {}, "future": 4}],
    }), encoding="utf-8")

    populations = PopulationRepository(str(path)).load()

    assert [(p.id, p.name) for p in populations] == [("x", "Custom")]


def test_unsupported_schema_version_is_descriptive(tmp_path):
    path = tmp_path / "populations.json"
    path.write_text('{"schemaVersion": 99, "populations": []}', encoding="utf-8")

    with pytest.raises(RepositoryError, match="schema version 99"):
        PopulationRepository(str(path)).load()


def test_corrupt_json_is_backed_up_before_defaults(tmp_path):
    path = tmp_path / "populations.json"
    path.write_text("not json", encoding="utf-8")

    populations = PopulationRepository(str(path)).load()

    assert [p.name for p in populations] == ["Fighter", "Ranged"]
    assert not path.exists()
    assert (tmp_path / "populations.json.corrupt").read_text(encoding="utf-8") == "not json"


def test_failed_atomic_replace_keeps_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "populations.json"
    repository = PopulationRepository(str(path))
    repository.save([Population.create("Fighter", "fighter")])
    original = path.read_text(encoding="utf-8")

    def fail_replace(*_args):
        raise OSError("disk error")

    monkeypatch.setattr("mewgenics.populations.repository.os.replace", fail_replace)
    with pytest.raises(RepositoryError, match="disk error"):
        repository.save([Population.create("Changed", "fighter")])

    assert path.read_text(encoding="utf-8") == original
