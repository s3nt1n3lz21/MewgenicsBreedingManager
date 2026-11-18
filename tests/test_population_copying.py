import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mewgenics.populations import Population, TraitCategory
from mewgenics.populations.copying import (
    CopyMode,
    copy_scores,
    preview_copy_scores,
)


def _population(name, population_id, values):
    result = Population.create(name, population_id)
    for category, key, value in values:
        result = result.with_score(category, key, value)
    return result


def test_fill_unset_copies_selected_categories_and_preserves_existing_zero():
    source = _population("Fighter", "fighter", [
        (TraitCategory.MUTATION, "m", 3),
        (TraitCategory.PASSIVE, "p", 2),
    ])
    destination = _population("Ranged", "ranged", [
        (TraitCategory.MUTATION, "m", 0),
    ])

    result = copy_scores(
        source, destination, {TraitCategory.MUTATION, TraitCategory.PASSIVE}, CopyMode.FILL_UNSET
    )
    preview = preview_copy_scores(
        source, destination, {TraitCategory.MUTATION, TraitCategory.PASSIVE}, CopyMode.FILL_UNSET
    )

    assert result.scores[TraitCategory.MUTATION]["m"] == 0
    assert result.scores[TraitCategory.PASSIVE]["p"] == 2
    assert (preview.copied, preview.preserved, preview.overwritten) == (1, 1, 0)


def test_overwrite_replaces_existing_and_reports_counts():
    source = _population("Fighter", "fighter", [(TraitCategory.MUTATION, "m", 3)])
    destination = _population("Ranged", "ranged", [(TraitCategory.MUTATION, "m", -1)])

    result = copy_scores(
        source, destination, {TraitCategory.MUTATION}, CopyMode.OVERWRITE
    )
    preview = preview_copy_scores(
        source, destination, {TraitCategory.MUTATION}, CopyMode.OVERWRITE
    )

    assert result.scores[TraitCategory.MUTATION]["m"] == 3
    assert (preview.copied, preview.preserved, preview.overwritten) == (0, 0, 1)
    assert source.scores[TraitCategory.MUTATION]["m"] == 3
    assert destination.scores[TraitCategory.MUTATION]["m"] == -1


def test_unselected_categories_are_not_copied():
    source = _population("Fighter", "fighter", [(TraitCategory.DISORDER, "d", -3)])
    destination = Population.create("Ranged", "ranged")

    result = copy_scores(source, destination, {TraitCategory.PASSIVE}, CopyMode.FILL_UNSET)

    assert not result.scores[TraitCategory.DISORDER]
