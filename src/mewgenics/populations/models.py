from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4


class TraitCategory(str, Enum):
    ACTIVE_ABILITY = "activeAbilities"
    PASSIVE = "passives"
    MUTATION = "mutations"
    DISORDER = "disorders"
    BIRTH_DEFECT = "birthDefects"


def empty_scores() -> dict[TraitCategory, dict[str, int]]:
    return {category: {} for category in TraitCategory}


def normalize_trait_key(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


@dataclass(frozen=True)
class TraitRef:
    category: TraitCategory
    key: str
    label: str

    @property
    def identity(self) -> tuple[TraitCategory, str]:
        return self.category, normalize_trait_key(self.key)


@dataclass(frozen=True)
class Population:
    id: str
    name: str
    scores: Mapping[TraitCategory, Mapping[str, int]] = field(default_factory=empty_scores)

    def __post_init__(self):
        name = self.name.strip()
        if not name:
            raise ValueError("population name cannot be blank")
        normalized = empty_scores()
        for raw_category, values in self.scores.items():
            category = raw_category if isinstance(raw_category, TraitCategory) else TraitCategory(raw_category)
            for key, value in values.items():
                _validate_score(value)
                normalized[category][normalize_trait_key(key)] = value
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "scores",
            MappingProxyType({k: MappingProxyType(v) for k, v in normalized.items()}),
        )

    @classmethod
    def create(cls, name: str, population_id: str | None = None) -> "Population":
        return cls(population_id or uuid4().hex, name, empty_scores())

    def with_score(self, category: TraitCategory, key: str, value: int | None) -> "Population":
        copied = {item: dict(values) for item, values in self.scores.items()}
        normalized_key = normalize_trait_key(key)
        if value is None:
            copied[category].pop(normalized_key, None)
        else:
            _validate_score(value)
            copied[category][normalized_key] = value
        return replace(self, scores=copied)


def _validate_score(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("score must be a whole number")
    if not -99 <= value <= 99:
        raise ValueError("score must be between -99 and 99")


@dataclass(frozen=True)
class ScoreContribution:
    trait: TraitRef
    value: int


@dataclass(frozen=True)
class CatScoreResult:
    total: int
    is_complete: bool
    contributions: tuple[ScoreContribution, ...]
    unresolved: tuple[TraitRef, ...]


def default_populations() -> list[Population]:
    return [
        Population.create("Fighter", "fighter"),
        Population.create("Ranged", "ranged"),
    ]
