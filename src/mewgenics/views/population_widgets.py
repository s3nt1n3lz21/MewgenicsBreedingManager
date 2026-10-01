from __future__ import annotations

from typing import Mapping, Sequence

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mewgenics.populations import Population, TraitCategory, TraitRef
from mewgenics.populations.copying import CopyMode, preview_copy_scores


class NullableScoreEditor(QWidget):
    scoreChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Unset")
        self.line_edit.setMaximumWidth(70)
        self.line_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"-?(?:[0-9]|[1-8][0-9]|9[0-9])?")))
        self.line_edit.textChanged.connect(lambda _text: self.scoreChanged.emit(self.score()))
        layout.addWidget(self.line_edit)

    def score(self) -> int | None:
        text = self.line_edit.text().strip()
        return None if not text or text == "-" else int(text)

    def set_score(self, value: int | None) -> None:
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not -99 <= value <= 99):
            raise ValueError("score must be a whole number between -99 and 99")
        self.line_edit.setText("" if value is None else str(value))


class TraitScoreTable(QWidget):
    scoreChanged = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter traits…")
        self.needs_review = QCheckBox("Needs review")
        self.search.textChanged.connect(self._apply_filter)
        self.needs_review.toggled.connect(self._apply_filter)
        controls.addWidget(self.search)
        controls.addWidget(self.needs_review)
        layout.addLayout(controls)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Category", "Trait", "Cats", "Score"])
        layout.addWidget(self.table)
        self._population = None
        self._traits: list[TraitRef] = []

    def set_population(
        self,
        population: Population,
        encountered: Sequence[TraitRef],
        affected_counts: Mapping[str, int],
    ) -> None:
        self._population = population
        self._traits = list(encountered)
        self.table.setRowCount(len(self._traits))
        for row, trait in enumerate(self._traits):
            self.table.setItem(row, 0, QTableWidgetItem(trait.category.value))
            self.table.setItem(row, 1, QTableWidgetItem(trait.label))
            self.table.setItem(row, 2, QTableWidgetItem(str(affected_counts.get(trait.key, 0))))
            editor = NullableScoreEditor()
            editor.set_score(population.scores[trait.category].get(trait.identity[1]))
            editor.scoreChanged.connect(
                lambda value, current=trait: self.scoreChanged.emit(current, value)
            )
            self.table.setCellWidget(row, 3, editor)
        self._apply_filter()

    def set_needs_review_only(self, enabled: bool) -> None:
        self.needs_review.setChecked(enabled)

    def visible_trait_keys(self) -> list[str]:
        return [
            trait.key for row, trait in enumerate(self._traits)
            if not self.table.isRowHidden(row)
        ]

    def _apply_filter(self, *_args) -> None:
        query = self.search.text().strip().lower()
        for row, trait in enumerate(self._traits):
            configured = self._population is not None and trait.identity[1] in self._population.scores[trait.category]
            matches = query in trait.label.lower() or query in trait.key.lower()
            self.table.setRowHidden(row, not matches or (self.needs_review.isChecked() and configured))


class PopulationEditor(QWidget):
    populationSelected = Signal(str)
    addRequested = Signal()
    renameRequested = Signal(str)
    deleteRequested = Signal(str)
    copyRequested = Signal(str)

    def __init__(self, populations: Sequence[Population], parent=None):
        super().__init__(parent)
        self._populations = list(populations)
        layout = QHBoxLayout(self)
        self.combo = QComboBox()
        for population in self._populations:
            self.combo.addItem(population.name, population.id)
        self.combo.currentIndexChanged.connect(
            lambda _index: self.populationSelected.emit(self.combo.currentData() or "")
        )
        layout.addWidget(QLabel("Population:"))
        layout.addWidget(self.combo, 1)
        self.add_button = QPushButton("Add")
        self.rename_button = QPushButton("Rename")
        self.delete_button = QPushButton("Delete")
        self.copy_button = QPushButton("Copy scores")
        self.add_button.clicked.connect(self.addRequested.emit)
        self.rename_button.clicked.connect(
            lambda: self.renameRequested.emit(self.combo.currentData() or "")
        )
        self.delete_button.clicked.connect(
            lambda: self.deleteRequested.emit(self.combo.currentData() or "")
        )
        self.copy_button.clicked.connect(
            lambda: self.copyRequested.emit(self.combo.currentData() or "")
        )
        layout.addWidget(self.add_button)
        layout.addWidget(self.rename_button)
        layout.addWidget(self.delete_button)
        layout.addWidget(self.copy_button)

    def set_populations(self, populations: Sequence[Population], selected_id: str = "") -> None:
        self._populations = list(populations)
        self.combo.blockSignals(True)
        self.combo.clear()
        for population in self._populations:
            self.combo.addItem(population.name, population.id)
        selected_index = self.combo.findData(selected_id)
        self.combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.combo.blockSignals(False)
        self.populationSelected.emit(self.combo.currentData() or "")

    def population_names(self) -> list[str]:
        return [self.combo.itemText(i) for i in range(self.combo.count())]

    def validate_new_name(self, name: str) -> str:
        clean = name.strip()
        if not clean:
            raise ValueError("population name cannot be blank")
        if clean.casefold() in {existing.casefold() for existing in self.population_names()}:
            raise ValueError("population name must be unique")
        return clean


class CopyScoresDialog(QDialog):
    def __init__(self, populations: Sequence[Population], destination_id: str, parent=None):
        super().__init__(parent)
        self._populations = {population.id: population for population in populations}
        self._destination_id = destination_id
        self.setWindowTitle("Copy scores")
        layout = QVBoxLayout(self)
        self.source_combo = QComboBox()
        for population in populations:
            if population.id != destination_id:
                self.source_combo.addItem(population.name, population.id)
        self.source_combo.currentIndexChanged.connect(self._update_preview)
        layout.addWidget(self.source_combo)
        self.category_checks = {}
        for category in TraitCategory:
            checkbox = QCheckBox(category.value)
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._update_preview)
            self.category_checks[category] = checkbox
            layout.addWidget(checkbox)
        self.fill_unset = QRadioButton("Fill unset values only")
        self.overwrite = QRadioButton("Overwrite existing values")
        self.fill_unset.setChecked(True)
        self.fill_unset.toggled.connect(self._update_preview)
        self.overwrite.toggled.connect(self._update_preview)
        layout.addWidget(self.fill_unset)
        layout.addWidget(self.overwrite)
        self.preview_label = QLabel()
        layout.addWidget(self.preview_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_preview()

    def source_population_id(self) -> str:
        return self.source_combo.currentData() or ""

    def selected_categories(self) -> set[TraitCategory]:
        return {category for category, checkbox in self.category_checks.items() if checkbox.isChecked()}

    def copy_mode(self) -> CopyMode:
        return CopyMode.FILL_UNSET if self.fill_unset.isChecked() else CopyMode.OVERWRITE

    def preview(self):
        source = self._populations.get(self.source_population_id())
        destination = self._populations[self._destination_id]
        if source is None:
            return None
        return preview_copy_scores(source, destination, self.selected_categories(), self.copy_mode())

    def _update_preview(self, *_args) -> None:
        if not hasattr(self, "preview_label"):
            return
        preview = self.preview()
        if preview is None:
            self.preview_label.setText("No source population available.")
            return
        self.preview_label.setText(
            f"Copy: {preview.copied}   Preserve: {preview.preserved}   "
            f"Overwrite: {preview.overwritten}"
        )
