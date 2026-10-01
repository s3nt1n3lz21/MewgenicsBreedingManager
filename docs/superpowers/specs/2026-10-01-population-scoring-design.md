# Population-Based Cat Scoring Design

**Date:** 2026-10-01  
**Status:** Proposed for implementation  
**Repository:** `s3nt1n3lz21/MewgenicsBreedingManager`

## Purpose

Extend Mewgenics Breeding Manager with a population-based ranking workflow. A player assigns cats to user-defined populations, such as Fighter or Ranged, and independently scores each encountered trait for each population. The application highlights cats that are unassigned or whose traits have not yet been reviewed.

The feature is deliberately configuration-driven. Version one does not encode a particular ranking formula, infer recommended values, or expose class names beyond the two initial population names.

## Goals

- Start with editable Fighter and Ranged populations without revealing later game classes.
- Let users create, rename, and delete populations.
- Assign one population to each cat, with room-based bulk assignment for unassigned cats.
- Automatically assign eligible newborns when their room has one unambiguous population.
- Configure signed whole-number values independently for each population and trait.
- Treat unset values differently from an explicitly configured zero.
- Show clear unassigned and incomplete-review indicators.
- Reuse population scoring definitions across saves while keeping cat assignments save-specific.
- Preserve a data format that a later C++ in-game companion can consume.

## Non-goals

Version one will not:

- Implement Neil's spreadsheet rules or any other built-in scoring formula.
- Infer suggested trait scores.
- Modify Mewgenics save files.
- Add an in-game overlay or DLL integration.
- Automatically assign strays.
- Change a cat's population when it moves rooms.
- Expose every trait in the game before the player encounters it.
- Copy population names, colours, or presentation settings between populations.

## Terminology

- **Population:** A named scoring context, such as Fighter or Ranged.
- **Trait:** An active ability, passive, mutation, disorder, or birth defect.
- **Unset value:** The user has not reviewed the trait for the selected population.
- **Explicit zero:** The user reviewed the trait and decided it contributes no points.
- **Unassigned cat:** A cat without a population.
- **Unresolved cat:** A cat with a population and at least one encountered trait whose value is unset for that population.

## User experience

### Initial state

On first use, the reusable population configuration contains:

- Fighter
- Ranged

Both names are editable. All trait values are unset. No additional class-derived population names are created.

Existing cats initially have no assignment. The roster displays a `?` indicator for them.

### Roster

The population scoring roster adds:

- Population
- Total score
- Review state

Review state uses:

- `?` — no population assigned
- `!` — assigned population has one or more unset trait values present on this cat
- Blank — assigned and every present trait has been reviewed

The table remains sortable and filterable. A score may be shown for an unresolved cat, but it is explicitly marked as partial and must not appear complete.

Selecting a cat displays:

- Population selector
- Total or partial score
- Configured score breakdown
- Unresolved trait list grouped by category
- Inline whole-number editors that update the shared population configuration

Changing a trait value from the cat panel affects every cat in the same population that has that trait.

### Population configuration

The population configuration area supports:

- Add population
- Rename population
- Delete population
- Select active population
- Copy scores from another population

For the selected population, five searchable trait groups are available:

1. Active abilities
2. Passives
3. Mutations
4. Disorders
5. Birth defects

Only traits encountered in loaded save data need to be listed. Each row contains the trait name, optional description, number of cats currently affected, and a nullable whole-number editor.

The editor semantics are:

- Empty: unset
- `0`: reviewed and neutral
- Positive integer: positive contribution
- Negative integer: negative contribution
- Range: `-99` through `99`

A **Needs review** filter shows only unset traits currently possessed by at least one cat assigned to that population.

Disorders and birth defects are not intrinsically negative. They use the same configurable scoring model as all other trait categories.

### Manual assignment

When the user assigns a population to an unassigned cat, the application offers:

> Assign <population> to this cat and N other unassigned cats in <room>?

Rules:

- The selected cat receives the population.
- If accepted, every other unassigned cat currently in that room receives it.
- Cats with an existing assignment are never changed by the room operation.
- Reassigning an already assigned cat changes only that cat unless a separate future bulk action is introduced.
- Moving a cat later does not change its population.

### Automatic newborn assignment

On save refresh, newly encountered cats are classified using parsed lineage:

- Generation `0` or no resolvable parents means stray; leave unassigned.
- Generation `1+` or resolvable parents means newborn candidate.

A newborn is automatically assigned only when all pre-existing, living resident cats in its room:

- Have a population assignment, and
- Share the same population

If the room is empty, mixed, or contains any unassigned resident, the newborn remains unassigned.

When multiple siblings first appear in the same refresh, determine the room population from cats that existed before that refresh. The siblings must not establish or validate one another's population.

Automatic assignment runs only when a cat first appears. Later movement between rooms does not trigger reassignment.

### Population deletion

Deleting a population requires confirmation and immediately leaves its assigned cats unassigned. The deleted population definition and its scores remain recoverable through an in-session undo action until the application closes. Undo restores both the population and affected assignments where the cats have not subsequently been reassigned.

### Copy scores

A **Copy scores from population** dialog provides:

- Source population
- Destination population
- Category selection:
  - Active abilities
  - Passives
  - Mutations
  - Disorders
  - Birth defects
  - All
- Copy mode:
  - Fill unset destination values only (default)
  - Overwrite configured destination values

Before applying, show counts for values to copy, preserve, and overwrite. Overwrite mode requires explicit confirmation.

Only score assignments are copied.

## Scoring model

A cat score is the sum of configured values for every present trait across all five categories.

```text
score(cat, population) =
    sum(active ability values)
  + sum(passive values)
  + sum(mutation values)
  + sum(disorder values)
  + sum(birth defect values)
```

No category has a default weight. Missing entries contribute nothing to the partial numeric total but add to the unresolved list and cause the `!` indicator.

Each distinct trait instance is counted according to the manager's existing normalized trait representation. The scoring service must centralize deduplication so UI views do not independently decide whether two parsed entries represent the same trait.

The pure scoring result contains:

- `total: int`
- `is_complete: bool`
- Contributions grouped by category
- Unresolved trait keys grouped by category

## Persistence

### Reusable population file

Population definitions and scores are shared across save games. Store them in application configuration rather than beside one particular save.

Proposed schema:

```json
{
  "schemaVersion": 1,
  "populations": [
    {
      "id": "stable-generated-id",
      "name": "Fighter",
      "scores": {
        "activeAbilities": {},
        "passives": {},
        "mutations": {},
        "disorders": {},
        "birthDefects": {}
      }
    }
  ]
}
```

A score map contains only reviewed traits. Absence means unset; a stored `0` means explicitly neutral.

Trait keys use stable parsed game identifiers wherever available. Store a last-known display label alongside a separate trait catalogue or diagnostic metadata when useful, but never use the translated display label as identity.

### Save-specific assignment file

Cat assignments are stored per save using the application's existing sidecar conventions.

Proposed schema:

```json
{
  "schemaVersion": 1,
  "assignments": {
    "stable-cat-id": "population-id"
  },
  "knownCats": {
    "stable-cat-id": {
      "firstSeenRoom": "room-key",
      "firstSeenGeneration": 1
    }
  }
}
```

Use the most stable cat identifier exposed by the parser, preferring the existing database key or UID already used for selection and lineage. The implementation plan must verify which identifier survives normal save refreshes before choosing it.

All configuration and assignment writes use write-to-temporary-file followed by atomic replacement, consistent with existing persistence utilities. A malformed file is backed up and reported without modifying the game save.

## Architecture

### Pure domain modules

Add a focused package under `src/mewgenics/populations/`:

- `models.py`
  - Population
  - TraitCategory
  - TraitKey
  - PopulationScoreConfig
  - CatScoreResult
- `scoring.py`
  - Pure score calculation
  - Trait normalization and deduplication
  - Missing-value detection
- `assignment.py`
  - Manual room-fill selection
  - New-cat detection
  - Newborn-versus-stray classification
  - Homogeneous-room population resolution
- `repository.py`
  - Reusable population configuration persistence
  - Per-save cat assignment persistence
  - Schema validation and migration hooks
  - Atomic writes
- `copying.py`
  - Score copy preview
  - Fill-unset and overwrite operations

These modules have no Qt dependencies.

### Qt integration

Evolve `src/mewgenics/views/manual_scoring.py` into the population-oriented scoring surface rather than adding population logic to `MainWindow`.

The view owns presentation and delegates domain work to the package above. It receives parsed cats through the existing `set_cats()` flow and exposes explicit state-save methods consistent with other views.

Supporting UI components may be split into focused modules when `manual_scoring.py` would otherwise grow further:

- Population selector/editor
- Trait score table
- Copy scores dialog
- Cat assignment and unresolved-trait panel

The existing `MainWindow` should only wire the view into save loading and refresh events. It must not calculate scores or contain population business rules.

### Existing code reuse

Reuse:

- Existing `Cat` fields for database key/UID, room, generation, parents, active abilities, passives, mutations, disorders, and defects.
- Existing ability and mutation display-name/tooltip helpers.
- Existing live `set_cats()` refresh path.
- Existing atomic persistence patterns.
- Existing table state and styling conventions.
- Existing `QSpinBox` range conventions where a nullable editor wrapper can preserve unset separately from zero.

Do not force the nullable model into a normal `QSpinBox` whose default value is zero. The editor must explicitly support an empty state, for example through a nullable custom widget or a line-edit-backed integer delegate.

## Data flow

### Save load or refresh

1. Existing parser produces `Cat` objects.
2. View receives cats through `set_cats()`.
3. Assignment service compares current stable cat IDs with previously known IDs.
4. Eligible newborns are automatically assigned from homogeneous room context.
5. Trait catalogue is rebuilt from encountered cat data.
6. Population scorer calculates results for assigned cats.
7. Roster, indicators, breakdowns, and Needs review counts refresh.

### User configures a trait

1. User enters a whole number or clears the editor.
2. View updates the selected population's score map.
3. Repository atomically persists reusable configuration.
4. All affected cat scores are recalculated.
5. Warning indicators and Needs review counts update immediately.

### User assigns a cat

1. User selects a population.
2. Assignment service identifies eligible unassigned room peers.
3. UI requests confirmation when peers exist.
4. Assignment repository persists the selected changes.
5. Scores and indicators refresh.

## Error handling

- Population configuration load failure: preserve the malformed file as a backup, show an actionable error, and start with a safe in-memory configuration without overwriting the backup.
- Assignment load failure: preserve the malformed file, leave cats unassigned, and explain that scoring definitions remain intact.
- Missing referenced population: treat affected cats as unassigned and retain the unknown ID for diagnostics.
- Unknown trait category or schema field: ignore safely and retain forward-compatible data where practical.
- Atomic save failure: keep in-memory edits visible, show that persistence failed, and allow retry.
- Save refresh while editing: preserve population configuration; rebuild cat-derived lists without converting unset fields to zero or discarding the active edit.
- Renamed traits: stable keys retain scores; display labels refresh from current game data.
- Deleted or gone cats: retain assignment data so a temporarily absent cat does not cause destructive churn; exclude non-living/gone cats from active ranking.

## Migration and compatibility

The population feature uses its own schema and does not silently reinterpret existing Simple Scoring profiles. Existing Simple and Detailed Scoring data must remain readable and untouched.

The first implementation may replace the visible Simple Scoring workflow with Population Scoring only after tests establish that existing saved profile data is not lost. If both views coexist during migration, navigation labels must clearly distinguish them.

Every JSON document includes `schemaVersion`. Migrations are explicit functions covered by tests so the later C++ reader can rely on a documented contract.

## Testing strategy

### Pure unit tests

- Default Fighter and Ranged populations are created with empty score maps.
- Empty score map entry is unset; stored zero is configured.
- Positive, zero, and negative values sum correctly.
- All five categories contribute independently.
- Score result lists unresolved traits and marks partial totals incomplete.
- Duplicate normalized traits are counted according to one centralized rule.
- Copy preview reports copied, preserved, and overwritten counts.
- Fill-unset copy does not change configured destination values.
- Overwrite copy replaces configured destination values.
- Manual room fill includes only unassigned cats in the selected room.
- Existing assignments are never overwritten.
- A newborn inherits from a homogeneous, fully assigned room.
- Newborn siblings do not establish one another's room population.
- Mixed, partially unassigned, and empty rooms do not auto-assign.
- Generation-zero/no-parent strays remain unassigned.
- Population deletion unassigns cats; undo restores eligible assignments.
- Global scoring configuration and per-save assignments remain separate.
- Persistence round-trips explicit zero without converting it to unset.
- Corrupt-file recovery does not overwrite the source.

### UI tests

- Roster displays `?`, `!`, and complete states correctly.
- Clearing a score editor restores unset rather than zero.
- Editing a trait updates every affected cat in the selected population.
- Needs review filter shows only relevant unresolved encountered traits.
- Room bulk-assignment confirmation reports the correct count.
- Copy dialog defaults to fill-unset mode.
- Population names are editable and only Fighter/Ranged are initially visible.
- Selection, filters, and sort state survive score recalculation and save refresh.

### Regression tests

Run the full existing suite:

```bash
pytest tests/ --basetemp=tmp/pytest
```

Add focused tests alongside existing scoring, persistence, and view tests. Existing Detailed Scoring, breeding, parser, room optimizer, and save refresh behaviour must remain unchanged.

## Implementation sequence

The subsequent implementation plan should divide work into independently testable increments:

1. Domain models and nullable scoring engine.
2. Reusable population repository and per-save assignment repository.
3. Assignment service and newborn detection.
4. Population/trait configuration UI.
5. Roster integration, indicators, and score breakdown.
6. Room bulk assignment.
7. Copy-scores workflow.
8. Population deletion/undo and error recovery.
9. Migration protection, regression testing, documentation, and packaging.

## Acceptance criteria

The feature is ready when:

- A fresh install shows editable Fighter and Ranged populations only.
- All trait scores begin unset.
- A user can assign cats manually and optionally fill unassigned room peers.
- Eligible newborns inherit a homogeneous room population; strays do not.
- Every encountered active ability, passive, mutation, disorder, and birth defect can be scored independently per population using whole numbers.
- Explicit zero is preserved and does not trigger a warning.
- Unassigned cats show `?`; assigned cats with unset present traits show `!`.
- Score copying supports category selection, fill-unset, overwrite, preview, and confirmation.
- Population scoring config is reusable across saves.
- Cat assignments remain isolated per save.
- The application never writes to a Mewgenics save.
- Existing tests pass and new behaviour is covered by automated tests.
- The JSON schema is documented well enough for a later C++ companion to consume.
