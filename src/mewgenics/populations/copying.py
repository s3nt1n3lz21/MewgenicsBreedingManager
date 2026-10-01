from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .models import Population, TraitCategory


class CopyMode(str, Enum):
    FILL_UNSET = "fillUnset"
    OVERWRITE = "overwrite"


@dataclass(frozen=True)
class CopyPreview:
    copied: int = 0
    preserved: int = 0
    overwritten: int = 0


def _copy_result(
    source: Population,
    destination: Population,
    categories: set[TraitCategory],
    mode: CopyMode,
) -> tuple[Population, CopyPreview]:
    scores = {category: dict(values) for category, values in destination.scores.items()}
    copied = preserved = overwritten = 0
    for category in categories:
        for key, value in source.scores[category].items():
            exists = key in scores[category]
            if exists and mode is CopyMode.FILL_UNSET:
                preserved += 1
                continue
            if exists:
                overwritten += 1
            else:
                copied += 1
            scores[category][key] = value
    return replace(destination, scores=scores), CopyPreview(copied, preserved, overwritten)


def preview_copy_scores(
    source: Population,
    destination: Population,
    categories: set[TraitCategory],
    mode: CopyMode,
) -> CopyPreview:
    return _copy_result(source, destination, categories, mode)[1]


def copy_scores(
    source: Population,
    destination: Population,
    categories: set[TraitCategory],
    mode: CopyMode,
) -> Population:
    return _copy_result(source, destination, categories, mode)[0]
