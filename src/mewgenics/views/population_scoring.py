from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from save_parser import Cat

from mewgenics.populations import (
    AssignmentRepository,
    AssignmentState,
    CatScoreResult,
    Population,
    PopulationRepository,
    TraitCategory,
    TraitRef,
    apply_newborn_assignments,
    assign_cat_and_peers,
    copy_scores,
    preview_copy_scores,
    score_cat,
    traits_for_cat,
    unassigned_room_peers,
)
from mewgenics.utils.paths import population_assignments_path, population_config_path
from mewgenics.populations.copying import CopyMode
from mewgenics.views.population_widgets import CopyScoresDialog, PopulationEditor, TraitScoreTable


@dataclass(frozen=True)
class DeletedPopulation:
    population: Population
    affected_assignments: dict[str, str]
    index: int = 0


class PopulationScoringView(QWidget):
    """Population-specific trait scoring and cat assignment view."""

    def __init__(self, parent=None, population_path: str | None = None):
        super().__init__(parent)
        self._population_repository = PopulationRepository(population_path or population_config_path())
        self._populations = self._population_repository.load()
        self._assignment_repository: AssignmentRepository | None = None
        self._assignment_state = AssignmentState()
        self._unknown_assignments: dict[str, str] = {}
        self._cats: list[Cat] = []
        self._scores: dict[str, CatScoreResult] = {}
        self._encountered: list[TraitRef] = []
        self._suppress_assignment_signals = False
        self._deleted_population: DeletedPopulation | None = None
        self._pending_population_save = False
        self._pending_assignment_save = False
        self.last_persistence_error: str | None = None

        layout = QVBoxLayout(self)
        title = QLabel("Population Scoring")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        self._auto_calc_chk = QCheckBox("Auto Recalculate")
        self._auto_calc_chk.setChecked(True)
        self._auto_calc_chk.hide()
        layout.addWidget(self._auto_calc_chk)

        self.population_editor = PopulationEditor(self._populations)
        self.population_editor.populationSelected.connect(self._on_population_selected)
        self.population_editor.addRequested.connect(self._prompt_add_population)
        self.population_editor.renameRequested.connect(self._prompt_rename_population)
        self.population_editor.deleteRequested.connect(self._confirm_delete_population)
        self.population_editor.copyRequested.connect(self._prompt_copy_scores)
        layout.addWidget(self.population_editor)
        self.undo_delete_button = QPushButton("Undo population deletion")
        self.undo_delete_button.setEnabled(False)
        self.undo_delete_button.clicked.connect(lambda: self.undo_delete())
        layout.addWidget(self.undo_delete_button)
        self.persistence_error_label = QLabel()
        self.persistence_error_label.setWordWrap(True)
        self.persistence_error_label.hide()
        layout.addWidget(self.persistence_error_label)
        self.retry_save_button = QPushButton("Retry saving changes")
        self.retry_save_button.setEnabled(False)
        self.retry_save_button.clicked.connect(self.retry_persistence)
        layout.addWidget(self.retry_save_button)

        splitter = QSplitter(Qt.Horizontal)
        self.trait_table = TraitScoreTable()
        self.trait_table.scoreChanged.connect(self._on_trait_score_changed)
        splitter.addWidget(self.trait_table)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Room", "Population", "Score", "Review"])
        self.table.itemSelectionChanged.connect(self._show_selected_breakdown)
        right_layout.addWidget(self.table)
        self.breakdown_label = QLabel("Select a cat to see its score breakdown.")
        self.breakdown_label.setWordWrap(True)
        right_layout.addWidget(self.breakdown_label)
        splitter.addWidget(right)
        layout.addWidget(splitter, 1)
        self._refresh_trait_table()

    def set_save_path(self, save_path: str) -> None:
        self._assignment_repository = AssignmentRepository(population_assignments_path(save_path))
        self._assignment_state = self._assignment_repository.load()
        valid_ids = {population.id for population in self._populations}
        self._unknown_assignments = {
            cat_id: population_id
            for cat_id, population_id in self._assignment_state.assignments.items()
            if population_id not in valid_ids
        }
        valid_assignments = {
            cat_id: population_id
            for cat_id, population_id in self._assignment_state.assignments.items()
            if population_id in valid_ids
        }
        self._assignment_state = replace(self._assignment_state, assignments=valid_assignments)

    def set_cats(self, cats: list[Cat]) -> None:
        previous = set(self._assignment_state.known_cats)
        self._cats = list(cats or [])
        self._assignment_state = apply_newborn_assignments(previous, self._cats, self._assignment_state)
        self._save_assignments()
        encountered = {}
        for cat in self._cats:
            for trait in traits_for_cat(cat):
                encountered.setdefault(trait.identity, trait)
        self._encountered = list(encountered.values())
        self._recompute()

    def assign_population(self, cat_id: str, population_id: str, include_room_peers: bool) -> None:
        self._population_by_id(population_id)
        cat = self._cat_by_id(cat_id)
        peers = unassigned_room_peers(cat, self._cats, self._assignment_state.assignments)
        self._assignment_state = assign_cat_and_peers(
            cat, population_id, peers if include_room_peers else (), self._assignment_state
        )
        self._unknown_assignments.pop(cat_id, None)
        if include_room_peers:
            for peer in peers:
                self._unknown_assignments.pop(peer.unique_id, None)
        self._save_assignments()
        self._recompute()

    def assignment_for(self, cat_id: str) -> str | None:
        return self._assignment_state.assignments.get(cat_id)

    def unknown_assignment_for(self, cat_id: str) -> str | None:
        return self._unknown_assignments.get(cat_id)

    def score_for(self, cat_id: str) -> CatScoreResult:
        return self._scores[cat_id]

    def review_state_for(self, cat_id: str) -> str:
        if cat_id not in self._assignment_state.assignments or cat_id not in self._scores:
            return "?"
        return "!" if not self._scores[cat_id].is_complete else ""

    @property
    def has_pending_persistence(self) -> bool:
        return self._pending_population_save or self._pending_assignment_save

    def add_population(self, name: str) -> Population:
        clean = self.population_editor.validate_new_name(name)
        population = Population.create(clean)
        self._populations.append(population)
        self._save_populations()
        self._refresh_population_editor(population.id)
        self._recompute()
        return population

    def rename_population(self, population_id: str, name: str) -> None:
        current = self._population_by_id(population_id)
        clean = name.strip()
        if not clean:
            raise ValueError("population name cannot be blank")
        if clean.casefold() != current.name.casefold():
            clean = self.population_editor.validate_new_name(clean)
        index = self._populations.index(current)
        self._populations[index] = replace(current, name=clean)
        self._save_populations()
        self._refresh_population_editor(population_id)
        self._recompute()

    def copy_population_scores(
        self,
        source_id: str,
        destination_id: str,
        categories: set[TraitCategory],
        mode: CopyMode,
    ) -> None:
        source = self._population_by_id(source_id)
        destination = self._population_by_id(destination_id)
        index = self._populations.index(destination)
        self._populations[index] = copy_scores(source, destination, categories, mode)
        self._save_populations()
        self._refresh_population_editor(destination_id)
        self._recompute()

    def delete_population(self, population_id: str) -> DeletedPopulation:
        if len(self._populations) <= 1:
            raise ValueError("at least one population is required")
        population = self._population_by_id(population_id)
        index = self._populations.index(population)
        affected = {
            cat_id: assigned
            for cat_id, assigned in self._assignment_state.assignments.items()
            if assigned == population_id
        }
        assignments = {
            cat_id: assigned
            for cat_id, assigned in self._assignment_state.assignments.items()
            if assigned != population_id
        }
        deleted = DeletedPopulation(population, affected, index)
        self._populations.pop(index)
        self._assignment_state = replace(self._assignment_state, assignments=assignments)
        self._deleted_population = deleted
        self.undo_delete_button.setEnabled(True)
        self._save_populations()
        self._save_assignments()
        self._refresh_population_editor()
        self._recompute()
        return deleted

    def undo_delete(self, deleted: DeletedPopulation | None = None) -> None:
        deleted = deleted or self._deleted_population
        if deleted is None or any(item.id == deleted.population.id for item in self._populations):
            return
        self._populations.insert(min(deleted.index, len(self._populations)), deleted.population)
        assignments = dict(self._assignment_state.assignments)
        for cat_id, population_id in deleted.affected_assignments.items():
            if cat_id not in assignments:
                assignments[cat_id] = population_id
        self._assignment_state = replace(self._assignment_state, assignments=assignments)
        if deleted == self._deleted_population:
            self._deleted_population = None
            self.undo_delete_button.setEnabled(False)
        self._save_populations()
        self._save_assignments()
        self._refresh_population_editor(deleted.population.id)
        self._recompute()

    def retry_persistence(self) -> bool:
        self.last_persistence_error = None
        if self._pending_population_save:
            self._save_populations()
        if self._pending_assignment_save:
            self._save_assignments()
        self._update_persistence_status()
        return not self.has_pending_persistence

    def trait_score(self, population_id: str, category: TraitCategory, key: str) -> int | None:
        population = self._population_by_id(population_id)
        return population.scores[category].get(key.strip().lower())

    def set_trait_score(
        self, population_id: str, category: TraitCategory, key: str, value: int | None
    ) -> None:
        index = next(i for i, population in enumerate(self._populations) if population.id == population_id)
        self._populations[index] = self._populations[index].with_score(category, key, value)
        self._save_populations()
        self._recompute()

    def set_trait_ratings(self, _ratings) -> None:
        """Compatibility shim: legacy profile data remains untouched."""

    def save_session_state(self) -> None:
        self._save_populations()
        self._save_assignments()

    def set_auto_recalculate(self, enabled: bool) -> None:
        self._auto_calc_chk.setChecked(bool(enabled))

    def _recompute(self) -> None:
        self._scores = {}
        populations = {population.id: population for population in self._populations}
        for cat in self._cats:
            population = populations.get(self._assignment_state.assignments.get(cat.unique_id, ""))
            if population is not None:
                self._scores[cat.unique_id] = score_cat(cat, population)
        self._populate_roster()
        self._refresh_trait_table()

    def _populate_roster(self) -> None:
        active = [cat for cat in self._cats if cat.status != "Gone"]
        self._suppress_assignment_signals = True
        self.table.setRowCount(len(active))
        for row, cat in enumerate(active):
            name = QTableWidgetItem(cat.name)
            name.setData(Qt.UserRole, cat.unique_id)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(cat.room or "—"))
            combo = QComboBox()
            combo.addItem("Unassigned", "")
            for population in self._populations:
                combo.addItem(population.name, population.id)
            assigned = self.assignment_for(cat.unique_id) or ""
            index = combo.findData(assigned)
            combo.setCurrentIndex(max(0, index))
            combo.currentIndexChanged.connect(
                lambda _index, cat_id=cat.unique_id, widget=combo: self._assignment_changed(cat_id, widget)
            )
            self.table.setCellWidget(row, 2, combo)
            result = self._scores.get(cat.unique_id)
            self.table.setItem(row, 3, QTableWidgetItem("—" if result is None else str(result.total)))
            self.table.setItem(row, 4, QTableWidgetItem(self.review_state_for(cat.unique_id)))
        self._suppress_assignment_signals = False

    def _assignment_changed(self, cat_id: str, combo: QComboBox) -> None:
        if self._suppress_assignment_signals:
            return
        population_id = combo.currentData() or ""
        if not population_id:
            assignments = dict(self._assignment_state.assignments)
            assignments.pop(cat_id, None)
            self._unknown_assignments.pop(cat_id, None)
            self._assignment_state = replace(self._assignment_state, assignments=assignments)
            self._save_assignments()
            self._recompute()
            return
        cat = self._cat_by_id(cat_id)
        peers = unassigned_room_peers(cat, self._cats, self._assignment_state.assignments)
        include_peers = False
        if peers:
            include_peers = QMessageBox.question(
                self,
                "Assign room",
                f"Assign this population to this cat and {len(peers)} other unassigned cats in {cat.room}?",
            ) == QMessageBox.Yes
        self.assign_population(cat_id, population_id, include_peers)

    def _on_population_selected(self, _population_id: str) -> None:
        self._refresh_trait_table()

    def _on_trait_score_changed(self, trait: TraitRef, value: int | None) -> None:
        population_id = self.population_editor.combo.currentData()
        if population_id:
            self.set_trait_score(population_id, trait.category, trait.key, value)

    def _refresh_trait_table(self) -> None:
        population_id = self.population_editor.combo.currentData()
        if not population_id:
            self.trait_table.table.setRowCount(0)
            return
        population = self._population_by_id(population_id)
        assigned_cat_ids = {
            cat_id for cat_id, assigned in self._assignment_state.assignments.items()
            if assigned == population_id
        }
        counts = Counter(
            trait.key
            for cat in self._cats if cat.unique_id in assigned_cat_ids
            for trait in traits_for_cat(cat)
        )
        self.trait_table.set_population(population, self._encountered, counts)

    def _show_selected_breakdown(self) -> None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return
        cat_id = self.table.item(row, 0).data(Qt.UserRole)
        result = self._scores.get(cat_id)
        if result is None:
            self.breakdown_label.setText("Assign a population to score this cat.")
            return
        configured = ", ".join(f"{item.trait.label}: {item.value:+d}" for item in result.contributions) or "None"
        unresolved = ", ".join(item.label for item in result.unresolved) or "None"
        self.breakdown_label.setText(
            f"Configured: {configured}\nNeeds review: {unresolved}"
        )

    def _cat_by_id(self, cat_id: str) -> Cat:
        return next(cat for cat in self._cats if cat.unique_id == cat_id)

    def _population_by_id(self, population_id: str) -> Population:
        return next(population for population in self._populations if population.id == population_id)

    def _refresh_population_editor(self, selected_id: str = "") -> None:
        self.population_editor.set_populations(self._populations, selected_id)

    def _save_populations(self) -> None:
        try:
            self._population_repository.save(self._populations)
        except Exception as error:
            self._pending_population_save = True
            self.last_persistence_error = str(error)
        else:
            self._pending_population_save = False
        self._update_persistence_status()

    def _prompt_add_population(self) -> None:
        name, accepted = QInputDialog.getText(self, "Add population", "Population name:")
        if accepted:
            try:
                self.add_population(name)
            except ValueError as error:
                QMessageBox.warning(self, "Invalid population", str(error))

    def _prompt_rename_population(self, population_id: str) -> None:
        if not population_id:
            return
        population = self._population_by_id(population_id)
        name, accepted = QInputDialog.getText(
            self, "Rename population", "Population name:", text=population.name
        )
        if accepted:
            try:
                self.rename_population(population_id, name)
            except ValueError as error:
                QMessageBox.warning(self, "Invalid population", str(error))

    def _confirm_delete_population(self, population_id: str) -> None:
        if not population_id:
            return
        population = self._population_by_id(population_id)
        if QMessageBox.question(
            self,
            "Delete population",
            f"Delete {population.name}? Assigned cats will become unassigned.",
        ) == QMessageBox.Yes:
            try:
                self.delete_population(population_id)
            except ValueError as error:
                QMessageBox.warning(self, "Cannot delete population", str(error))

    def _prompt_copy_scores(self, destination_id: str) -> None:
        if not destination_id or len(self._populations) < 2:
            return
        dialog = CopyScoresDialog(self._populations, destination_id, self)
        if dialog.exec():
            source_id = dialog.source_population_id()
            categories = dialog.selected_categories()
            mode = dialog.copy_mode()
            if mode is CopyMode.OVERWRITE:
                preview = preview_copy_scores(
                    self._population_by_id(source_id),
                    self._population_by_id(destination_id),
                    categories,
                    mode,
                )
                if QMessageBox.question(
                    self,
                    "Confirm overwrite",
                    f"Overwrite {preview.overwritten} existing score values?",
                ) != QMessageBox.Yes:
                    return
            self.copy_population_scores(
                source_id,
                destination_id,
                categories,
                mode,
            )

    def _save_assignments(self) -> None:
        if self._assignment_repository is not None:
            try:
                persisted = replace(
                    self._assignment_state,
                    assignments={**self._unknown_assignments, **self._assignment_state.assignments},
                )
                self._assignment_repository.save(persisted)
            except Exception as error:
                self._pending_assignment_save = True
                self.last_persistence_error = str(error)
            else:
                self._pending_assignment_save = False
            self._update_persistence_status()

    def _update_persistence_status(self) -> None:
        if not hasattr(self, "retry_save_button"):
            return
        pending = self.has_pending_persistence
        self.retry_save_button.setEnabled(pending)
        self.persistence_error_label.setVisible(pending)
        if pending:
            self.persistence_error_label.setText(
                f"Changes are kept in memory but could not be saved: {self.last_persistence_error}"
            )
