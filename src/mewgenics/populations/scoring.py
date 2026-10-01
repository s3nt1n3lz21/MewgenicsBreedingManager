from __future__ import annotations

from save_parser import Cat

from .models import CatScoreResult, Population, ScoreContribution
from .traits import traits_for_cat


def score_cat(cat: Cat, population: Population) -> CatScoreResult:
    contributions: list[ScoreContribution] = []
    unresolved = []
    for trait in traits_for_cat(cat):
        category_scores = population.scores[trait.category]
        if trait.identity[1] not in category_scores:
            unresolved.append(trait)
            continue
        contributions.append(ScoreContribution(trait, category_scores[trait.identity[1]]))
    return CatScoreResult(
        total=sum(item.value for item in contributions),
        is_complete=not unresolved,
        contributions=tuple(contributions),
        unresolved=tuple(unresolved),
    )
