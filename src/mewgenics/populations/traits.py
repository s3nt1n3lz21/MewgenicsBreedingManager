from __future__ import annotations

from save_parser import Cat

from .models import TraitCategory, TraitRef, normalize_trait_key


_ATTRIBUTES = (
    (TraitCategory.ACTIVE_ABILITY, "abilities"),
    (TraitCategory.PASSIVE, "passive_abilities"),
    (TraitCategory.MUTATION, "mutations"),
    (TraitCategory.DISORDER, "disorders"),
    (TraitCategory.BIRTH_DEFECT, "defects"),
)


def traits_for_cat(cat: Cat) -> tuple[TraitRef, ...]:
    seen: set[tuple[TraitCategory, str]] = set()
    result: list[TraitRef] = []
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
