from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mewgenics.populations import (
    Population,
    TraitCategory,
    TraitRef,
    default_populations,
    score_cat,
)
from save_parser import STAT_NAMES


def _cat(**overrides):
    values = {
        "abilities": [],
        "passive_abilities": [],
        "mutations": [],
        "disorders": [],
        "defects": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_default_populations_are_fighter_and_ranged_with_empty_scores():
    populations = default_populations()

    assert [population.name for population in populations] == ["Fighter", "Ranged"]
    assert all(
        not population.scores[category]
        for population in populations
        for category in TraitCategory
        if category is not TraitCategory.BASE_STAT
    )


def test_default_populations_seed_each_base_stat_value_minus_five():
    population = default_populations()[0]

    assert len(population.scores[TraitCategory.BASE_STAT]) == len(STAT_NAMES) * 8
    for stat in STAT_NAMES:
        for value in range(8):
            assert population.scores[TraitCategory.BASE_STAT][f"{stat.lower()}:{value}"] == value - 5


def test_base_stats_contribute_one_configured_score_per_stat():
    population = Population.create("Fighter", "fighter")
    cat = _cat(base_stats={stat: 5 for stat in STAT_NAMES})
    cat.base_stats.update({"STR": 7, "DEX": 3})

    result = score_cat(cat, population)

    assert result.total == 0
    assert result.is_complete
    assert len(result.contributions) == len(STAT_NAMES)


def test_base_stat_score_can_be_changed_or_explicitly_unset():
    population = Population.create("Fighter", "fighter")
    population = population.with_score(TraitCategory.BASE_STAT, "dex:7", 0)
    population = population.with_score(TraitCategory.BASE_STAT, "str:7", None)
    cat = _cat(base_stats={stat: 5 for stat in STAT_NAMES})
    cat.base_stats.update({"STR": 7, "DEX": 7})

    result = score_cat(cat, population)

    assert result.total == 0
    assert not result.is_complete
    assert [trait.key for trait in result.unresolved] == ["str:7"]


def test_zero_is_configured_while_absent_key_is_unresolved():
    population = Population.create("Fighter").with_score(
        TraitCategory.ACTIVE_ABILITY, "pawmissile", 0
    )
    cat = _cat(abilities=["pawmissile", "scratch"])

    result = score_cat(cat, population)

    assert result.total == 0
    assert not result.is_complete
    assert [trait.key for trait in result.unresolved] == ["scratch"]
    assert [(item.trait.key, item.value) for item in result.contributions] == [
        ("pawmissile", 0)
    ]


def test_all_five_trait_categories_sum_signed_whole_numbers():
    population = Population.create("Fighter")
    configured = [
        (TraitCategory.ACTIVE_ABILITY, "a", 2),
        (TraitCategory.PASSIVE, "p", -1),
        (TraitCategory.MUTATION, "m", 3),
        (TraitCategory.DISORDER, "d", -2),
        (TraitCategory.BIRTH_DEFECT, "b", 0),
    ]
    for category, key, value in configured:
        population = population.with_score(category, key, value)

    result = score_cat(
        _cat(
            abilities=["a"], passive_abilities=["p"], mutations=["m"],
            disorders=["d"], defects=["b"],
        ),
        population,
    )

    assert result.total == 2
    assert result.is_complete
    assert len(result.contributions) == 5


def test_duplicate_normalized_traits_are_counted_once():
    population = Population.create("Fighter").with_score(
        TraitCategory.PASSIVE, "quiver", 2
    )

    result = score_cat(_cat(passive_abilities=["Quiver", " quiver "]), population)

    assert result.total == 2
    assert len(result.contributions) == 1


def test_trait_identity_ignores_display_label():
    old = TraitRef(TraitCategory.MUTATION, "head:416", "Old label")
    renamed = TraitRef(TraitCategory.MUTATION, "head:416", "New label")

    assert old.identity == renamed.identity


@pytest.mark.parametrize("value", [-100, 100, 1.5])
def test_out_of_range_score_is_rejected(value):
    with pytest.raises((TypeError, ValueError)):
        Population.create("Fighter").with_score(
            TraitCategory.MUTATION, "mutation", value
        )
