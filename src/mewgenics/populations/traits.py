from __future__ import annotations

from save_parser import Cat, STAT_NAMES

from .models import TraitCategory, TraitRef, normalize_trait_key


_ATTRIBUTES = (
    (TraitCategory.ACTIVE_ABILITY, "abilities"),
    (TraitCategory.PASSIVE, "passive_abilities"),
    (TraitCategory.MUTATION, "mutations"),
    (TraitCategory.DISORDER, "disorders"),
    (TraitCategory.BIRTH_DEFECT, "defects"),
)


def base_stat_trait(stat: str, value: int) -> TraitRef:
    normalized_stat = str(stat).upper()
    numeric_value = int(value)
    return TraitRef(
        TraitCategory.BASE_STAT,
        f"{normalized_stat.lower()}:{numeric_value}",
        f"{normalized_stat} = {numeric_value}",
    )


def base_stat_catalog() -> tuple[TraitRef, ...]:
    return tuple(base_stat_trait(stat, value) for stat in STAT_NAMES for value in range(8))


def traits_for_cat(cat: Cat) -> tuple[TraitRef, ...]:
    seen: set[tuple[TraitCategory, str]] = set()
    result: list[TraitRef] = []
    base_stats = getattr(cat, "base_stats", None) or {}
    for stat in STAT_NAMES:
        if stat not in base_stats:
            continue
        trait = base_stat_trait(stat, base_stats[stat])
        seen.add(trait.identity)
        result.append(trait)
    for category, attribute in _ATTRIBUTES:
        for raw_value in getattr(cat, attribute, None) or []:
            label = str(raw_value).strip()
            key = normalize_trait_key(label)
            identity = (category, key)
            if not key or identity in seen:
                continue
            seen.add(identity)
            result.append(TraitRef(category, key, label))
    return tuple(result)
