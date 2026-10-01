# Population-Based Cat Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reusable, population-specific trait scoring with per-save cat assignments, newborn inheritance, unresolved-value warnings, and score-copying to Mewgenics Breeding Manager.

**Architecture:** Add a Qt-free `mewgenics.populations` package for models, trait extraction, scoring, persistence, assignment, and copying. Replace the current Simple Scoring presentation with a population-oriented view that consumes those services through the existing `set_cats()` refresh path while preserving old profile data untouched.

**Tech Stack:** Python 3.14+, PySide6, dataclasses/enums, JSON sidecars, pytest

**Spec:** `docs/superpowers/specs/2026-10-01-population-scoring-design.md`

## Global Constraints

- The application must never write to a Mewgenics `.sav` file.
- Initial reusable populations are editable `Fighter` and `Ranged` only.
- Trait categories are active abilities, passives, mutations, disorders, and birth defects.
- Scores are nullable signed integers from `-99` through `99`; absent means unset and stored `0` means reviewed neutral.
- Population definitions and scores are reusable across saves; cat assignments are isolated per save.
- Strays remain unassigned; eligible newborns inherit only from a fully assigned homogeneous room.
- Existing Simple/Detailed Scoring files remain readable and are not silently migrated or overwritten.
- Persistence uses UTF-8 JSON, `schemaVersion: 1`, and atomic temporary-file replacement.
- Run tests with `pytest tests/ --basetemp=tmp/pytest`.

## Review Focus

- A trait label changing after a game update must retain its score because identity uses a stable normalized key; Task 1 pins this in `test_trait_identity_ignores_display_label`.
- A save refresh arriving while the score editor is blank must not turn unset into zero; Task 6 pins this in `test_refresh_preserves_unset_editor_state`.
- Two newborn siblings discovered together must not establish a population for each other; Task 3 pins this in `test_siblings_use_only_preexisting_residents`.
- A corrupt assignment/config file must be backed up without overwriting it on fallback; Task 2 pins this in `test_corrupt_json_is_backed_up_before_defaults`.
- Deleting then undoing a population after one affected cat is manually reassigned must not overwrite that newer assignment; Task 7 pins this in `test_delete_undo_preserves_newer_reassignment`.

---

## File structure

**Create:**

- `src/mewgenics/populations/__init__.py` — public population-domain exports.
- `src/mewgenics/populations/models.py` — enums and immutable/domain dataclasses.
- `src/mewgenics/populations/traits.py` — normalize the five trait categories from parsed `Cat` objects.
- `src/mewgenics/populations/scoring.py` — pure score totals, contributions, and unresolved values.
- `src/mewgenics/populations/repository.py` — global population JSON and per-save assignment JSON.
- `src/mewgenics/populations/assignment.py` — room fill, new-cat detection, and newborn inheritance.
- `src/mewgenics/populations/copying.py` — copy preview and application.
- `src/mewgenics/views/population_widgets.py` — nullable integer editor, population editor, trait table, copy dialog.
- `tests/test_population_scoring.py`
- `tests/test_population_repository.py`
- `tests/test_population_assignment.py`
- `tests/test_population_copying.py`
- `tests/test_population_scoring_ui.py`

**Modify:**

- `src/mewgenics/views/manual_scoring.py` — population roster, assignment, breakdown, warnings, and configuration orchestration.
- `src/mewgenics/utils/paths.py` — paths for reusable population config and per-save assignments.
- `src/mewgenics/utils/cat_persistence.py` — expose/reuse atomic JSON writing without weakening existing callers.
- `src/mewgenics/main_window.py` — supply the active save path to Population Scoring and retain existing refresh wiring.
- `README.md` — describe Population Scoring and its non-destructive persistence.
- `CLAUDE.md` — document the new package and JSON ownership.

### Task 1: Domain model, trait normalization, and pure scoring

**Files:**

- Create: `src/mewgenics/populations/__init__.py`
- Create: `src/mewgenics/populations/models.py`
- Create: `src/mewgenics/populations/traits.py`
- Create: `src/mewgenics/populations/scoring.py`
- Create: `tests/test_population_scoring.py`

**Interfaces:**

- Produces: `TraitCategory(str, Enum)` with `ACTIVE_ABILITY`, `PASSIVE`, `MUTATION`, `DISORDER`, `BIRTH_DEFECT`.
- Produces: `TraitRef(category: TraitCategory, key: str, label: str)`.
- Produces: `Population(id: str, name: str, scores: dict[TraitCategory, dict[str, int]])`.
- Produces: `ScoreContribution(trait: TraitRef, value: int)`.
- Produces: `CatScoreResult(total: int, is_complete: bool, contributions: tuple[ScoreContribution, ...], unresolved: tuple[TraitRef, ...])`.
- Produces: `traits_for_cat(cat: Cat) -> tuple[TraitRef, ...]`.
- Produces: `score_cat(cat: Cat, population: Population) -> CatScoreResult`.

- [ ] **Step 1: Write failing domain tests**

Add tests named:

- `test_default_populations_are_fighter_and_ranged_with_empty_scores`
- `test_zero_is_configured_while_absent_key_is_unresolved`
- `test_all_five_trait_categories_sum_signed_whole_numbers`
- `test_duplicate_normalized_traits_are_counted_once`
- `test_trait_identity_ignores_display_label`
- `test_out_of_range_score_is_rejected`

Assert initial names exactly `["Fighter", "Ranged"]`, explicit zero yields complete total `0`, missing keys appear in `unresolved`, and scores outside `[-99, 99]` raise `ValueError`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `pytest tests/test_population_scoring.py -v --basetemp=tmp/pytest`  
Expected: FAIL because `mewgenics.populations` does not exist.

- [ ] **Step 3: Implement the domain interfaces**

Use stable raw parser identifiers for `TraitRef.key`; labels are presentation-only. Centralize category extraction and deduplication in `traits_for_cat()`. Validate population names are non-empty after trimming and validate score values at model boundaries.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_population_scoring.py -v --basetemp=tmp/pytest`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mewgenics/populations tests/test_population_scoring.py
git commit -m "feat: add population scoring domain"
```

### Task 2: Reusable configuration and per-save assignment repositories

**Files:**

- Create: `src/mewgenics/populations/repository.py`
- Create: `tests/test_population_repository.py`
- Modify: `src/mewgenics/utils/paths.py`
- Modify: `src/mewgenics/utils/cat_persistence.py`

**Interfaces:**

- Consumes: `Population`, `TraitCategory`.
- Produces: `PopulationRepository(path: str)` with `load() -> list[Population]` and `save(populations: Sequence[Population]) -> None`.
- Produces: `AssignmentState(assignments: dict[str, str], known_cats: dict[str, KnownCat])`.
- Produces: `AssignmentRepository(path: str)` with `load() -> AssignmentState` and `save(state: AssignmentState) -> None`.
- Produces: `population_config_path() -> str`.
- Produces: `population_assignments_path(save_path: str) -> str`.
- Produces: `atomic_write_json(path: str, data: Mapping) -> None`.

- [ ] **Step 1: Write failing repository tests**

Cover:

- Global population config round-trip with all categories.
- Per-save assignment round-trip keyed by `Cat.unique_id`.
- Explicit zero survives JSON round-trip.
- Missing global file creates Fighter/Ranged defaults.
- Unknown JSON fields are ignored.
- Unsupported `schemaVersion` raises a descriptive repository error.
- `test_corrupt_json_is_backed_up_before_defaults` asserts the malformed source is renamed to a timestamp-free deterministic `.corrupt` sibling for testability and is not overwritten.
- Failed atomic replacement leaves the previous valid file intact.

- [ ] **Step 2: Run repository tests and verify failure**

Run: `pytest tests/test_population_repository.py -v --basetemp=tmp/pytest`  
Expected: FAIL because repository interfaces do not exist.

- [ ] **Step 3: Implement paths and repositories**

Store reusable configuration under the existing application configuration directory. Store assignments beside the selected save with a distinct `.populations.json` suffix. Refactor existing private atomic text writing only as needed so existing blacklist/tag behavior remains unchanged.

- [ ] **Step 4: Run repository and existing persistence tests**

Run: `pytest tests/test_population_repository.py tests/test_manager_persistence.py tests/test_config.py -v --basetemp=tmp/pytest`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mewgenics/populations/repository.py src/mewgenics/utils/paths.py src/mewgenics/utils/cat_persistence.py tests/test_population_repository.py
git commit -m "feat: persist populations and cat assignments"
```

### Task 3: Manual room fill and automatic newborn assignment

**Files:**

- Create: `src/mewgenics/populations/assignment.py`
- Create: `tests/test_population_assignment.py`

**Interfaces:**

- Consumes: `AssignmentState` and parsed `Cat` objects.
- Produces: `unassigned_room_peers(selected: Cat, cats: Sequence[Cat], assignments: Mapping[str, str]) -> tuple[Cat, ...]`.
- Produces: `assign_cat_and_peers(selected: Cat, population_id: str, peers: Sequence[Cat], state: AssignmentState) -> AssignmentState`.
- Produces: `apply_newborn_assignments(previous_known_ids: set[str], cats: Sequence[Cat], state: AssignmentState) -> AssignmentState`.

- [ ] **Step 1: Write failing assignment tests**

Cover:

- Only unassigned living cats in the selected room are returned as peers.
- Existing assignments are never overwritten.
- Moving an assigned cat does not alter assignment.
- Generation-zero/no-parent new cat remains unassigned.
- Newborn inherits from a fully assigned homogeneous room.
- Mixed, partially unassigned, and empty rooms do not assign.
- `test_siblings_use_only_preexisting_residents` introduces two unseen generation-one cats together and verifies neither can establish the other's population.
- Gone/dead cats do not influence room homogeneity.
- Newborn automation runs only for IDs absent from `previous_known_ids`.

- [ ] **Step 2: Run assignment tests and verify failure**

Run: `pytest tests/test_population_assignment.py -v --basetemp=tmp/pytest`  
Expected: FAIL because assignment functions do not exist.

- [ ] **Step 3: Implement assignment functions**

Use `Cat.unique_id` as assignment identity. Determine newborn status from resolvable parent lineage/generation already computed by the parser. Snapshot pre-existing room residents before processing any new cats.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_population_assignment.py tests/test_parser.py -v --basetemp=tmp/pytest`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mewgenics/populations/assignment.py tests/test_population_assignment.py
git commit -m "feat: assign populations by room and lineage"
```

### Task 4: Score-copying service

**Files:**

- Create: `src/mewgenics/populations/copying.py`
- Create: `tests/test_population_copying.py`

**Interfaces:**

- Consumes: source/destination `Population`, selected `set[TraitCategory]`.
- Produces: `CopyMode(str, Enum)` with `FILL_UNSET` and `OVERWRITE`.
- Produces: `CopyPreview(copied: int, preserved: int, overwritten: int)`.
- Produces: `preview_copy_scores(source: Population, destination: Population, categories: set[TraitCategory], mode: CopyMode) -> CopyPreview`.
- Produces: `copy_scores(...) -> Population` using the same arguments and returning a new destination value.

- [ ] **Step 1: Write failing copy tests**

Cover all-category and selected-category copies, fill-unset preservation, explicit-zero preservation, overwrite counts, and immutability of the source/destination inputs.

- [ ] **Step 2: Run copy tests and verify failure**

Run: `pytest tests/test_population_copying.py -v --basetemp=tmp/pytest`  
Expected: FAIL because copying interfaces do not exist.

- [ ] **Step 3: Implement preview and copy operations**

Make `preview_copy_scores()` and `copy_scores()` share one internal decision path so displayed counts cannot diverge from applied changes.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_population_copying.py -v --basetemp=tmp/pytest`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mewgenics/populations/copying.py tests/test_population_copying.py
git commit -m "feat: copy scores between populations"
```

### Task 5: Population configuration widgets

**Files:**

- Create: `src/mewgenics/views/population_widgets.py`
- Create: `tests/test_population_scoring_ui.py`

**Interfaces:**

- Consumes: repositories, `Population`, `TraitRef`, and copy service.
- Produces: `NullableScoreEditor(QWidget)` with `scoreChanged = Signal(object)`, `score() -> int | None`, and `set_score(value: int | None) -> None`.
- Produces: `TraitScoreTable(QWidget)` with `set_population(population: Population, encountered: Sequence[TraitRef], affected_counts: Mapping[str, int])`.
- Produces: `PopulationEditor(QWidget)` with add/rename/delete signals and active-population selection.
- Produces: `CopyScoresDialog(QDialog)` returning source, categories, and `CopyMode`.

- [ ] **Step 1: Write failing widget tests**

With an offscreen `QApplication`, test:

- Nullable editor starts blank, distinguishes blank from zero, clamps/rejects outside `[-99, 99]`, and emits `None` when cleared.
- Trait table groups all five categories and Needs review hides configured zero.
- Only encountered traits appear.
- Population editor initially displays Fighter/Ranged and validates duplicate/blank names.
- Copy dialog defaults to all categories plus `FILL_UNSET` and displays preview counts.

- [ ] **Step 2: Run widget tests and verify failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_population_scoring_ui.py -v --basetemp=tmp/pytest`  
Expected: FAIL because widget classes do not exist.

- [ ] **Step 3: Implement focused widgets**

Use a line-edit-backed nullable integer control or a custom spin-box wrapper that can truly represent `None`. Follow existing project styling, tooltips, and `blockSignals()` conventions.

- [ ] **Step 4: Run widget tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_population_scoring_ui.py -v --basetemp=tmp/pytest`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mewgenics/views/population_widgets.py tests/test_population_scoring_ui.py
git commit -m "feat: add population scoring widgets"
```

### Task 6: Integrate population scoring into Simple Scoring

**Files:**

- Modify: `src/mewgenics/views/manual_scoring.py`
- Modify: `src/mewgenics/main_window.py`
- Modify: `tests/test_population_scoring_ui.py`

**Interfaces:**

- Consumes: all Tasks 1–5 interfaces.
- Produces: `ManualScoringView.set_save_path(save_path: str) -> None`.
- Produces: `ManualScoringView.set_cats(cats: list[Cat]) -> None` that runs new-cat assignment, builds encountered traits, and recomputes population results.
- Produces: existing `save_session_state()` while population domain data is saved through repositories.

- [ ] **Step 1: Add failing integration tests**

Cover:

- Roster columns include Population, Score, and Review.
- Unassigned cat shows `?`.
- Assigned cat with unset present trait shows `!` and partial score state.
- Explicit-zero traits remove the warning.
- Selecting a cat exposes grouped unresolved traits and score breakdown.
- Editing one trait recomputes all affected cats in the same population.
- Assignment prompt count excludes already assigned room residents.
- Declining room fill assigns only the selected cat; accepting includes eligible peers.
- `test_refresh_preserves_unset_editor_state` calls `set_cats()` during a blank edit and verifies it remains `None`.
- MainWindow supplies the active save path before cats.

- [ ] **Step 2: Run integration tests and verify failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_population_scoring_ui.py -v --basetemp=tmp/pytest`  
Expected: FAIL on missing integration behavior.

- [ ] **Step 3: Replace Simple Scoring orchestration**

Retain the navigation identity and `ManualScoringView` public class to minimize MainWindow changes. Remove the old formula UI from the visible workflow without deleting or rewriting `TraitRatings` data. Route scoring, assignment, and persistence through the new services.

- [ ] **Step 4: Run UI, persistence, and scoring regressions**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_population_scoring_ui.py tests/test_trait_ratings.py tests/test_scoring_engine.py tests/test_manager_persistence.py -v --basetemp=tmp/pytest`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mewgenics/views/manual_scoring.py src/mewgenics/main_window.py tests/test_population_scoring_ui.py
git commit -m "feat: integrate population cat ranking"
```

### Task 7: Population deletion undo and recovery behavior

**Files:**

- Modify: `src/mewgenics/populations/repository.py`
- Modify: `src/mewgenics/views/manual_scoring.py`
- Modify: `tests/test_population_repository.py`
- Modify: `tests/test_population_scoring_ui.py`

**Interfaces:**

- Produces: `DeletedPopulation(population: Population, affected_assignments: dict[str, str])`.
- Produces: `delete_population(population_id: str) -> DeletedPopulation` in view orchestration.
- Produces: `undo_delete(deleted: DeletedPopulation) -> None`, restoring only cats still unassigned from that deletion.

- [ ] **Step 1: Write failing deletion/recovery tests**

Cover confirmation cancellation, unassigning affected cats, in-session undo, unknown population IDs loading as unassigned, save failure leaving edits in memory with retry available, and `test_delete_undo_preserves_newer_reassignment`.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_population_repository.py tests/test_population_scoring_ui.py -v --basetemp=tmp/pytest`  
Expected: FAIL on missing delete/undo behavior.

- [ ] **Step 3: Implement deletion transaction and UI notification**

Keep one recoverable deletion snapshot in memory until another deletion or application close. Do not persist tombstones. Report persistence failures without reverting valid in-memory edits.

- [ ] **Step 4: Run focused tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_population_repository.py tests/test_population_scoring_ui.py -v --basetemp=tmp/pytest`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mewgenics/populations/repository.py src/mewgenics/views/manual_scoring.py tests/test_population_repository.py tests/test_population_scoring_ui.py
git commit -m "feat: support safe population deletion"
```

### Task 8: Documentation, full regression, and Windows smoke test

**Files:**

- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: release-facing files only if creating an actual numbered release in this task.

**Interfaces:**

- Consumes: completed population feature.
- Produces: documented user workflow, JSON ownership, and C++-companion contract.

- [ ] **Step 1: Update documentation**

Document Fighter/Ranged defaults, assignments, newborn behavior, `?`/`!`, nullable whole-number values, copying, reusable versus per-save files, and that the game save is read-only. Add the new package/files to `CLAUDE.md`.

- [ ] **Step 2: Run the complete suite**

Run: `pytest tests/ --basetemp=tmp/pytest`  
Expected: all tests PASS with no new warnings attributable to population scoring.

- [ ] **Step 3: Run the application smoke test on Windows**

Run: `python src/mewgenics_manager.py`  
Verify: load a save, open Population Scoring, assign a cat, configure zero/positive/negative values, refresh the save, and restart the app. Confirm config/assignments persist and the `.sav` modification time changes only when Mewgenics writes it.

- [ ] **Step 4: Build the standalone executable**

Run: `build.bat`  
Expected: PyInstaller completes and the generated executable opens Population Scoring successfully.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document population scoring"
```
