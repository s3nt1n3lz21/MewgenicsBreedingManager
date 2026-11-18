from __future__ import annotations

from save_parser import Cat

from mewgenics.scoring.cat_stats import get_cat_stats

from .models import CatScoreResult, Population, ScoreContribution, TraitCategory, TraitRef
from .traits import traits_for_cat


def score_cat(
    cat: Cat, population: Population, constitution_penalty_per_point: int = 0
) -> CatScoreResult:
    contributions: list[ScoreContribution] = []
    unresolved = []
    for trait in traits_for_cat(cat):
        category_scores = population.scores[trait.category]
        if trait.identity[1] not in category_scores:
            unresolved.append(trait)
            continue
        contributions.append(ScoreContribution(trait, category_scores[trait.identity[1]]))
    total = sum(item.value for item in contributions)
    overall_constitution = get_cat_stats(cat, use_current=True).get("CON")
    if overall_constitution is not None and constitution_penalty_per_point > 0:
        penalty = -max(0, 10 - int(overall_constitution)) * constitution_penalty_per_point
        if penalty:
            contributions.append(ScoreContribution(
                TraitRef(TraitCategory.BASE_STAT, "overall-con-penalty", "Overall CON penalty"),
                penalty,
            ))
            total += penalty
    return CatScoreResult(
        total=total,
        is_complete=not unresolved,
        contributions=tuple(contributions),
        unresolved=tuple(unresolved),
    )
