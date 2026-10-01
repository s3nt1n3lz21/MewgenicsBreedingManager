from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import tempfile
from typing import Mapping, Sequence

from .models import Population, TraitCategory, default_populations


SCHEMA_VERSION = 1


class RepositoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnownCat:
    first_seen_room: str
    first_seen_generation: int


@dataclass(frozen=True)
class AssignmentState:
    assignments: dict[str, str] = field(default_factory=dict)
    known_cats: dict[str, KnownCat] = field(default_factory=dict)


def atomic_write_json(path: str, data: Mapping) -> None:
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    descriptor = None
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".populations.", suffix=".tmp", dir=parent)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = None
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except (OSError, TypeError, ValueError) as error:
        raise RepositoryError(f"failed to save {path}: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary and os.path.exists(temporary):
            os.remove(temporary)


def _load_document(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError, TypeError):
        backup = path + ".corrupt"
        try:
            os.replace(path, backup)
        except OSError as error:
            raise RepositoryError(f"failed to preserve corrupt file {path}: {error}") from error
        return None
    if not isinstance(data, dict):
        raise RepositoryError(f"invalid repository document in {path}")
    version = data.get("schemaVersion", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise RepositoryError(f"unsupported schema version {version} in {path}")
    return data


class PopulationRepository:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> list[Population]:
        document = _load_document(self.path)
        if document is None:
            return default_populations()
        result = []
        for item in document.get("populations", []):
            scores = {}
            raw_scores = item.get("scores", {})
            for category in TraitCategory:
                scores[category] = raw_scores.get(category.value, {})
            result.append(Population(item["id"], item["name"], scores))
        return result or default_populations()

    def save(self, populations: Sequence[Population]) -> None:
        atomic_write_json(self.path, {
            "schemaVersion": SCHEMA_VERSION,
            "populations": [
                {
                    "id": population.id,
                    "name": population.name,
                    "scores": {
                        category.value: dict(population.scores[category])
                        for category in TraitCategory
                    },
                }
                for population in populations
            ],
        })


class AssignmentRepository:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> AssignmentState:
        document = _load_document(self.path)
        if document is None:
            return AssignmentState()
        known = {
            cat_id: KnownCat(
                value.get("firstSeenRoom", ""),
                int(value.get("firstSeenGeneration", 0)),
            )
            for cat_id, value in document.get("knownCats", {}).items()
        }
        return AssignmentState(dict(document.get("assignments", {})), known)

    def save(self, state: AssignmentState) -> None:
        atomic_write_json(self.path, {
            "schemaVersion": SCHEMA_VERSION,
            "assignments": dict(state.assignments),
            "knownCats": {
                cat_id: {
                    "firstSeenRoom": value.first_seen_room,
                    "firstSeenGeneration": value.first_seen_generation,
                }
                for cat_id, value in state.known_cats.items()
            },
        })
