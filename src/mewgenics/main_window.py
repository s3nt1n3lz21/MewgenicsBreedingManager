Warning: truncated output (original token count: 57019)
Total output lines: 4599

"""MainWindow: primary application window for Mewgenics Breeding Manager."""
import re
import csv
import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QPushButton, QLabel, QFileDialog, QHeaderView,
    QAbstractItemView, QSplitter, QDialog, QScrollArea,
    QLineEdit,
    QMessageBox, QProgressBar, QMenu,
)
from PySide6.QtCore import (
    Qt, QEvent, QModelIndex, QItemSelection, QItemSelectionModel,
    QFileSystemWatcher, QThread, QTimer, QSize, QByteArray, Signal,
)
from PySide6.QtGui import (
    QColor, QBrush, QAction, QActionGroup, QFont, QKeySequence,
    QPainter, QPixmap, QIcon,
)

from save_parser import (
    Cat, FurnitureDefinition, FurnitureRoomSummary,
    build_furniture_room_summaries,
    STAT_NAMES, _is_hater_pair, ROOM_KEYS,
)

from mewgenics.constants import (
    COL_NAME, COL_TAGS, COL_AGE, COL_GEN, COL_ROOM, COL_STAT, COL_ADV, COL_BL, COL_MB, COL_PIN,
    STAT_COLS, COL_SUM, COL_AGG, COL_LIB, COL_INBRD, COL_SEXUALITY,
    COL_RELNS, COL_REL, COL_ABIL, COL_MUTS, COL_GEN_DEPTH, COL_SRC,
    _W_STATUS, _W_STAT, _W_GEN, _W_RELNS, _W_REL, _W_TRAIT, _W_TRAIT_NARROW,
    _ZOOM_MIN, _ZOOM_MAX, _ZOOM_STEP,
    _NAME_STYLE, _META_STYLE,
)
from mewgenics.utils.paths import (
    APPDATA_SAVE_DIR, APPDATA_CONFIG_DIR, APP_VERSION, _breeding_cache_path,
)
from mewgenics.utils.config import (
    _save_root_dir, _saved_default_save, _set_default_save,
    _save_current_view, _load_current_view,
    _set_save_dir, find_save_files,
    _saved_room_optimizer_auto_recalc, _set_room_optimizer_auto_recalc,
    _saved_manual_scoring_auto_calc, _set_manual_scoring_auto_calc,
    _save_splitter_state, _bind_splitter_persistence,
    _saved_zoom_percent, _set_zoom_percent,
    _saved_font_size_offset, _set_font_size_offset_config,
    _saved_last_seen_version, _set_last_seen_version,
    _saved_show_getting_started_prompt, _set_show_getting_started_prompt,
    _saved_accessibility_preset, _set_accessibility_preset,
    _saved_total_stats_display, _set_total_stats_display,
    _saved_stat_icon_mode, _set_stat_icon_mode,
    _saved_roster_visual_mode, _set_roster_visual_mode,
    _gpak_search_start_dir,
    _candidate_gpak_paths,
    _set_last_save,
    _save_window_geometry, _load_window_geometry,
)
from mewgenics.utils.localization import (
    _SUPPORTED_LANGUAGES, ROOM_DISPLAY, COLUMNS,
    _saved_language, _set_saved_language,
    _set_current_language, _current_language, _tr,
    _language_label, _font_size_offset_label,
    _refresh_localized_constants,
)
from mewgenics.utils.tags import (
    _TAG_DEFS, _TAG_ICON_CACHE, _TAG_PIX_CACHE, _cat_tags,
    _make_tag_icon,
)
from mewgenics.utils.thresholds import (
    _load_threshold_preferences, _save_threshold_preferences,
    _apply_threshold_preferences, _current_threshold_summary,
    _set_donation_planner_traits,
)
from mewgenics.utils.optimizer_settings import (
    _OPTIMIZER_SEARCH_DEFAULTS,
    _load_optimizer_search_settings, _save_optimizer_search_settings,
    _save_room_priority_config,
)
from mewgenics.utils.calibration import (
    _trait_label_from_value, _apply_calibration,
)
from mewgenics.utils.cat_persistence import (
    _save_blacklist, _save_must_breed, _save_pinned, _save_tags,
    _save_not_adventured,
)
from mewgenics.utils.planner_state import _planner_import_traits_summary
from mewgenics.utils.cat_analysis import (
    _is_exceptional_breeder, _is_donation_candidate,
)
from mewgenics.utils.game_data import (
    _set_gpak_path, _GPAK_PATH, _FURNITURE_DATA,
)
from mewgenics.utils.styling import (
    _ACCESSIBILITY_MIN_FONT_PX, _ACCESSIBILITY_MIN_FONT_PT,
    _enforce_min_font_in_widget_tree, _apply_font_offset_to_tree,
    _hsep, _sidebar_btn, _high_contrast_stylesheet,
)
from mewgenics.models.breeding_cache import (
    BreedingCache, BreedingCacheWorker,
    _breeding_cache_fingerprint, _breeding_save_signature,
)
from mewgenics.models.cat_table_model import (
    TagStripDelegate, CatTableModel, VisualIconDelegate,
    clear_cat_sprite_cache, clear_mutation_part_cache,
)
from mewgenics.models.room_filter_model import RoomFilterModel
from mewgenics.workers.save_loader import SaveLoadWorker
from mewgenics.workers.room_refresh import QuickRoomRefreshWorker

from mewgenics.dialogs import (
    TagManagerDialog,
    ThresholdPreferencesDialog,
    SharedOptimizerSearchSettingsDialog,
    SaveSelectorDialog,
    AboutDialog,
    GettingStartedPromptDialog,
    OnboardingDialog,
    WhatsNewDialog,
)
from mewgenics.panels.cat_detail import CatDetailPanel

from mewgenics.views.family_tree import FamilyTreeBrowserView
from mewgenics.views.safe_breeding import SafeBreedingView
from mewgenics.views.breeding_partners import BreedingPartnersView
from mewgenics.views.room_optimizer import RoomOptimizerView
from mewgenics.views.perfect_planner import PerfectCatPlannerView
from mewgenics.views.calibration import CalibrationView
from mewgenics.views.mutation_planner import MutationDisorderPlannerView
from mewgenics.views.furniture import FurnitureView
from mewgenics.views.population_scoring import PopulationScoringView as ManualScoringView
from mewgenics.utils.trait_ratings import TraitRatings

from breed_priority import BreedPriorityView
from mewgenics.utils.abilities import _mutation_display_name, _ability_tip
from mewgenics.utils.paths import _scoring_path


class MainWindow(QMainWindow):
    # Max consecutive self-heal retries after a transient save-load failure.
    # After this, we stop and wait for a fresh fileChanged event (or manual
    # reload) rather than spinning on a permanently-broken save.
    _SAVE_LOAD_RETRY_CAP = 3
    startup_save_load_finished = Signal()

    @staticmethod
    def _set_bulk_toggle_label(btn: QPushButton, label: str, enabled: bool):
        btn.setText(_tr("bulk.label_template", label=label, state=_tr("common.on" if enabled else "common.off")))

    @staticmethod
    def _style_room_action_button(btn: QPushButton, background: str, border: str, hover_background: str, width: int = 110):
        btn.setCheckable(False)
        btn.setMinimumWidth(width)
        btn.setStyleSheet(
            "QPushButton { "
            f"background:{background}; color:#f1f1f1; border:1px solid {border}; "
            "border-radius:4px; padding:4px 10px; font-size:11px; font-weight:bold; }"
            f"QPushButton:hover {{ background:{hover_background}; }}"
            "QPushButton:pressed { background:#1a1a1a; }"
        )

    def _set_room_action_button_texts(self):
        self._room_must_breed_btn.setText(_tr("bulk.toggle_must_breed"))
        self._room_must_breed_btn.setToolTip(_tr("bulk.toggle_must_breed.tooltip"))
        self._room_breeding_block_btn.setText(_tr("bulk.toggle_breeding_block"))
        self._room_breeding_block_btn.setToolTip(_tr("bulk.toggle_breeding_block.tooltip"))
        self._room_pin_btn.setText(_tr("bulk.toggle_pin", default="Toggle Pin"))
        self._room_pin_btn.setToolTip(_tr("bulk.toggle_pin.tooltip", default="Toggle pin for selected cats"))

    def _room_view_target_cats(self, room_key=None) -> list[Cat]:
        if room_key in (None, "__all__"):
            return self._selected_cats()
        return self._visible_filtered_cats()

    def _active_room_key(self):
        if self._active_btn is not None:
            for key, btn in self._room_btns.items():
                if btn is self._active_btn:
                    return key
        return None

    def _toggle_room_view_boolean(self, attr: str, room_key=None) -> int:
        cats = self._room_view_target_cats(room_key)
        mw_status = self.statusBar()
        if not cats:
            if room_key in (None, "__all__"):
                mw_status.showMessage("Select cats first, then click a room action.")
            else:
                mw_status.showMessage("No cats in the current room view needed a change.")
            return 0

        current = [bool(getattr(cat, attr, False)) for cat in cats]
        target_state = not all(current)
        changed = 0
        for cat in cats:
            if attr == "is_pinned":
                if cat.is_pinned == target_state:
                    continue
                cat.is_pinned = target_state
                changed += 1
                continue
            if attr == "must_breed":
                if cat.must_breed == target_state:
                    continue
                cat.must_breed = target_state
                if target_state:
                    cat.is_blacklisted = False
                changed += 1
                continue
            if attr == "is_blacklisted":
                if cat.is_blacklisted == target_state and (not target_state or not cat.must_breed):
                    continue
                cat.is_blacklisted = target_state
                if target_state:
                    cat.must_breed = False
                changed += 1

        if changed == 0:
            mw_status.showMessage("No cats in view needed a change.")
            return 0
        self._emit_bulk_toggle_refresh()
        return changed

    def _toggle_room_must_breed(self, room_key=None):
        changed = self._toggle_room_view_boolean("must_breed", room_key)
        if changed:
            self.statusBar().showMessage(_tr("bulk.status.toggled_must_breed", default="Toggled must breed for {count} selected cats", count=changed))

    def _toggle_room_breeding_block(self, room_key=None):
        changed = self._toggle_room_view_boolean("is_blacklisted", room_key)
        if changed:
            self.statusBar().showMessage(_tr("bulk.status.toggled_breeding_block", default="Toggled breeding block for {count} selected cats", count=changed))

    def _toggle_room_pin(self, room_key=None):
        changed = self._toggle_room_view_boolean("is_pinned", room_key)
        if changed:
            self.statusBar().showMessage(_tr("bulk.status.toggled_pin", default="Toggled pin for {count} selected cats", count=changed))

    def __init__(self, initial_save: Optional[str] = None, use_saved_default: bool = True):
        super().__init__()
        _set_current_language(_saved_language())
        _refresh_localized_constants()
        self.setWindowTitle(_tr("app.title"))
        self.resize(1440, 900)
        saved_geometry = _load_window_geometry()
        if saved_geometry:
            try:
                self.restoreGeometry(QByteArray.fromBase64(saved_geometry.encode("ascii")))
            except Exception:
                pass

        self._current_save = None
        self._cats: list[Cat] = []
        self._furniture = []
        self._furniture_by_room = {}
        self._room_summaries: dict[str, FurnitureRoomSummary] = {}
        self._available_house_rooms: list[str] = list(ROOM_KEYS)
        self._furniture_data: dict[str, FurnitureDefinition] = dict(_FURNITURE_DATA)
        self._room_btns: dict = {}
        self._active_btn = None
        # Navigation history for mouse back/forward buttons. Each entry is
        # a dict describing the view (+ table filter + selection). `_back_stack`
        # holds snapshots taken BEFORE a navigation action; `_forward_stack`
        # is rebuilt when the user navigates anywhere new. `_nav_suppress`
        # blocks recursive pushes while we restore a state.
        self._nav_back_stack: list[dict] = []
        self._nav_forward_stack: list[dict] = []
        self._nav_suppress: bool = False
        self._show_lineage: bool = False
        self._pair_detail_override: bool = False
        self._pedigree_coi_memos: dict[tuple[int, int], float] = {}
        self._tree_view: Optional[FamilyTreeBrowserView] = None
        self._safe_breeding_view: Optional[SafeBreedingView] = None
        self._breeding_partners_view: Optional[BreedingPartnersView] = None
        self._room_optimizer_view: Optional[RoomOptimizerView] = None
        self._perfect_planner_view: Optional[PerfectCatPlannerView] = None
        self._calibration_view: Optional[CalibrationView] = None
        self._mutation_planner_view: Optional['MutationDisorderPlannerView'] = None
        self._furniture_view: Optional[FurnitureView] = None
        self._manual_scoring_view: Optional[ManualScoringView] = None
        self._breed_priority_view: Optional[BreedPriorityView] = None
        self._trait_ratings: Optional[TraitRatings] = None
        self._cats_generation: int = 0
        self._view_generation: dict[str, int] = {}
        self._breeding_cache: Optional[BreedingCache] = None
        self._cache_worker: Optional[BreedingCacheWorker] = None
        self._save_load_worker: Optional[SaveLoadWorker] = None
        # Consecutive self-heal attempts triggered by `_on_save_load_failed`.
        # Capped so a permanently broken save can't loop forever.
        self._save_load_retries: int = 0
        self._quick_refresh_worker: Optional[QuickRoomRefreshWorker] = None
        # Stale-signal discriminator for `_on_room_patch`.  See
        # `_start_quick_room_refresh` for why `quit()/wait()` alone
        # cannot prevent a previous worker's queued signal from
        # clobbering freshly-loaded state.
        self._quick_refresh_generation: int = 0
        self._prev_parent_keys: dict[int, tuple] = {}
        self._accessible_cat_keys: set[int] = set()
        self._fight_club_layout_active: bool = False
        self._fight_club_prev_total_stats: bool = _saved_total_stats_display()
        self._fight_club_hidden_state: dict[int, bool] = {}
        self._zoom_percent: int = _saved_zoom_percent()
        self._font_size_offset: int = _saved_font_size_offset()   # pt offset applied on top of zoom
        self._accessibility_preset: str = _saved_accessibility_preset()
        self._safe_breeding_quality_mode: bool = True
        self._startup_dialogs_shown: bool = False
        self._default_app_stylesheet: str = QApplication.instance().styleSheet()
        self._base_font: QFont = QApplication.instance().font()
        self._base_sidebar_width = 190
        self._base_header_height = 46
        self._base_search_width = 180
        self._base_col_widths = {
            COL_TAGS: 122,
            COL_NAME: 160,
            COL_GEN: _W_GEN,
            COL_STAT: _W_STATUS,
            COL_ADV: 72,
            COL_BL: 34,
            COL_MB: 34,
            COL_PIN: 34,
            COL_SUM: 38,
            COL_ABIL: 180,
            COL_MUTS: 155,
            COL_RELNS: _W_RELNS,
            COL_REL: _W_REL,
            COL_AGE: 34,
            COL_AGG: _W_TRAIT_NARROW,
            COL_LIB: _W_TRAIT_NARROW,
            COL_INBRD: _W_TRAIT_NARROW,
            COL_SEXUALITY: _W_TRAIT,
            **{c: _W_STAT for c in STAT_COLS},
        }

        self._build_ui()
        self._build_menu()
        # Route mouse back/forward button presses through our navigation
        # history. Installed at app level so it catches clicks on any
        # child widget regardless of focus.
        QApplication.instance().installEventFilter(self)
        self._source_model.set_show_total_stats(_saved_total_stats_display())
        self._source_model.set_show_stat_icons(_saved_stat_icon_mode())
        self._apply_accessibility_style(self._accessibility_preset)
        self._apply_zoom()
        # Restore roster visual-mode choice. Must happen after the table
        # has been built and delegates installed.
        self._apply_roster_visual_mode(_saved_roster_visual_mode())

        # Progress bar for breeding cache computation
        self._cache_progress = QProgressBar()
        self._cache_progress.setFixedWidth(200)
        self._cache_progress.setFixedHeight(16)
        self._cache_progress.setTextVisible(True)
        self._cache_progress.setFormat(_tr("loading.cache.computing"))
        self._cache_progress.setStyleSheet(
            "QProgressBar { background:#1a1a32; border:1px solid #2a2a4a; border-radius:4px; color:#aaa; font-size:10px; }"
            "QProgressBar::chunk { background:#3f8f72; border-radius:3px; }"
        )
        self._cache_progress.hide()
        self.statusBar().addPermanentWidget(self._cache_progress)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed_raw)
        # Debounce file-watcher events.  The game often writes the save
        # in a burst (multiple fileChanged events within a few ms), and
        # each one used to start its own QuickRoomRefreshWorker, racing
        # with the previous one still running — a major contributor to
        # the ~10% crash rate reported against v5.4.8.  Coalesce bursts
        # into a single refresh 250 ms after the last event.
        self._file_change_timer = QTimer(self)
        self._file_change_timer.setSingleShot(True)
        self._file_change_timer.setInterval(250)
        self._file_change_timer.timeout.connect(self._on_file_changed_debounced)
        self._pending_changed_path: Optional[str] = None

        # Use initial_save if provided; otherwise only auto-load the saved default when allowed.
        save_to_load = initial_save if initial_save else (_saved_default_save() if use_saved_default else None)
        if save_to_load:
            # Defer load_save to after the window is shown so the UI appears instantly.
            QTimer.singleShot(0, lambda: self.load_save(save_to_load))

    # ── Menu ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        self.menuBar().clear()
        fm = self.menuBar().addMenu(_tr("menu.file"))

        oa = QAction(_tr("menu.file.open_save"), self)
        oa.setShortcut("Ctrl+O")
        oa.triggered.connect(self._open_file)
        fm.addAction(oa)

        # Recent Saves submenu
        self._recent_saves_menu = fm.addMenu(_tr("menu.file.recent_saves"))
        self._recent_save_actions: list[QAction] = []
        self._refresh_recent_save_actions()

        fm.addSeparator()

        # Default Save submenu
        self._default_save_menu = fm.addMenu(_tr("menu.file.default_save"))
        self._set_default_save_action = QAction(_tr("menu.file.default_save.set_current"), self)
        self._set_default_save_action.triggered.connect(self._set_current_as_default)
        self._set_default_save_action.setEnabled(False)
        self._default_save_menu.addAction(self._set_default_save_action)

        self._clear_default_save_action = QAction(_tr("menu.file.default_save.clear"), self)
        self._clear_default_save_action.triggered.connect(self._clear_default_save)
        self._clear_default_save_action.setEnabled(False)
        self._default_save_menu.addAction(self._clear_default_save_action)

        fm.addSeparator()

        ra = QAction(_tr("menu.file.reload"), self)
        ra.setShortcut("F5")
        ra.triggered.connect(self._reload)
        fm.addAction(ra)

        recalc = QAction(_tr("menu.file.recalculate_breeding_data"), self)
        recalc.setShortcut("Ctrl+F5")
        recalc.setToolTip(_tr("menu.file.recalculate_breeding_data.tooltip"))
        recalc.triggered.connect(lambda: self._start_breeding_cache(self._cats, force_full=True) if self._cats else None)
        fm.addAction(recalc)

        clear_cache = QAction(_tr("menu.file.clear_breeding_cache"), self)
        clear_cache.setToolTip(_tr("menu.file.clear_breeding_cache.tooltip"))
        clear_cache.triggered.connect(self._clear_breeding_cache)
        fm.addAction(clear_cache)

        fm.addSeparator()

        export_action = QAction(_tr("menu.file.export_cats", default="Export Cats…"), self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_cats)
        fm.addAction(export_action)

        fm.addSeparator()

        exit_action = QAction(_tr("menu.file.exit"), self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        fm.addAction(exit_action)

        # ── View menu ─────────────────────────────────────────────────────
        vm = self.menuBar().addMenu(_tr("menu.view", default="View"))

        self._lineage_action = QAction(_tr("menu.settings.show_lineage"), self)
        self._lineage_action.setCheckable(True)
        self._lineage_action.setChecked(self._show_lineage)
        self._lineage_action.triggered.connect(self._toggle_lineage)
        vm.addAction(self._lineage_action)

        self._room_optimizer_auto_recalc_action = QAction(_tr("menu.settings.room_optimizer_auto_recalc", default="Auto Recalculate Room Optimizer"), self)
        self._room_optimizer_auto_recalc_action.setCheckable(True)
        self._room_optimizer_auto_recalc_action.setChecked(_saved_room_optimizer_auto_recalc())
        self._room_optimizer_auto_recalc_action.toggled.connect(self._toggle_room_optimizer_auto_recalc)
        vm.addAction(self._room_optimizer_auto_recalc_action)

        self._manual_scoring_auto_calc_action = QAction(_tr("menu.settings.manual_scoring_auto_calc", default="Auto Recalculate Manual Scoring"), self)
        self._manual_scoring_auto_calc_action.setCheckable(True)
        self._manual_scoring_auto_calc_action.setChecked(_saved_manual_scoring_auto_calc())
        self._manual_scoring_auto_calc_action.toggled.connect(self._toggle_manual_scoring_auto_calc)
        vm.addAction(self._manual_scoring_auto_calc_action)

        vm.addSeparator()

        self._roster_display_menu = vm.addMenu(_tr("menu.settings.roster_display", default="Roster Display"))
        self._total_stats_action = QAction(_tr("menu.settings.show_total_stats", default="Show Total Stats"), self)
        self._total_stats_action.setCheckable(True)
        self._total_stats_action.setShortcut("Ctrl+T")
        self._total_stats_action.setChecked(_saved_total_stats_display())
        self._total_stats_action.triggered.connect(self._toggle_total_stats_display)
        self._roster_display_menu.addAction(self._total_stats_action)

        self._stat_icons_action = QAction(_tr("menu.settings.show_stat_icons", default="Stat Icons"), self)
        self._stat_icons_action.setCheckable(True)
        self._stat_icons_action.setChecked(_saved_stat_icon_mode())
        self._stat_icons_action.triggered.connect(self._toggle_stat_icon_mode)
        self._roster_display_menu.addAction(self._stat_icons_action)

        self._visual_mode_action = QAction(
            _tr("menu.settings.roster_visual_mode", default="Visual Mode (larger rows, sprites & icons)"),
            self,
        )
        self._visual_mode_action.setCheckable(True)
        self._visual_mode_action.setChecked(_saved_roster_visual_mode())
        self._visual_mode_action.triggered.connect(self._toggle_roster_visual_mode)
        self._roster_display_menu.addAction(self._visual_mode_action)

        vm.addSeparator()

        zoom_in = QAction(_tr("menu.settings.zoom_in"), self)
        zoom_in_keys = QKeySequence.keyBindings(QKeySequence.StandardKey.ZoomIn)
        if not zoom_in_keys:
            zoom_in_keys = []
        for seq in (QKeySequence("Ctrl+="), QKeySequence("Ctrl++")):
            if seq not in zoom_in_keys:
                zoom_in_keys.append(seq)
        zoom_in.setShortcuts(zoom_in_keys)
        zoom_in.triggered.connect(lambda: self._change_zoom(+1))
        vm.addAction(zoom_in)

        zoom_out = QAction(_tr("menu.settings.zoom_out"), self)
        zoom_out_keys = QKeySequence.keyBindings(QKeySequence.StandardKey.ZoomOut)
        if not zoom_out_keys:
            zoom_out_keys = []
        if QKeySequence("Ctrl+-") not in zoom_out_keys:
            zoom_out_keys.append(QKeySequence("Ctrl+-"))
        zoom_out.setShortcuts(zoom_out_keys)
        zoom_out.triggered.connect(lambda: self._change_zoom(-1))
        vm.addAction(zoom_out)

        zoom_reset = QAction(_tr("menu.settings.reset_zoom"), self)
        zoom_reset.setShortcut("Ctrl+0")
        zoom_reset.triggered.connect(self._reset_zoom)
        vm.addAction(zoom_reset)

        self._zoom_info_action = QAction("", self)
        self._zoom_info_action.setEnabled(False)
        vm.addAction(self._zoom_info_action)
        self._update_zoom_info_action()

        vm.addSeparator()

        fs_in = QAction(_tr("menu.settings.increase_font_size"), self)
        fs_in.setShortcut("Ctrl+]")
        fs_in.triggered.connect(lambda: self._change_font_size(+1))
        vm.addAction(fs_in)

        fs_out = QAction(_tr("menu.settings.decrease_font_size"), self)
        fs_out.setShortcut("Ctrl+[")
        fs_out.triggered.connect(lambda: self._change_font_size(-1))
        vm.addAction(fs_out)

        fs_reset = QAction(_tr("menu.settings.reset_font_size"), self)
        fs_reset.setShortcut("Ctrl+\\")
        fs_reset.triggered.connect(lambda: self._set_font_size_offset(0))
        vm.addAction(fs_reset)

        self._font_size_info_action = QAction("", self)
        self._font_size_info_action.setEnabled(False)
        vm.addAction(self._font_size_info_action)
        self._update_font_size_info_action()

        vm.addSeparator()

        self._accessibility_menu = vm.addMenu(_tr("menu.settings.accessibility", default="Accessibility"))
        self._accessibility_group = QActionGroup(self)
        self._accessibility_group.setExclusive(True)
        self._accessibility_actions: dict[str, QAction] = {}
        for preset in ("Default", "Comfort", "High Contrast", "Large Table"):
            action = QAction(preset, self)
            action.setCheckable(True)
            action.setChecked(preset == self._accessibility_preset)
            action.triggered.connect(lambda checked=False, name=preset: self._apply_accessibility_preset(name))
            self._accessibility_group.addAction(action)
            self._accessibility_menu.addAction(action)
            self._accessibility_actions[preset] = action

        vm.addSeparator()

        self._reset_ui_settings_action = QAction(_tr("menu.settings.reset_ui_defaults"), self)
        self._reset_ui_settings_action.triggered.connect(self._reset_ui_settings_to_defaults)
        vm.addAction(self._reset_ui_settings_action)

        # ── Settings menu ────────────────────────────────────────────────
        sm = self.menuBar().addMenu(_tr("menu.settings"))

        locations_action = QAction(_tr("menu.settings.locations"), self)
        locations_action.triggered.connect(self._open_locations_dialog)
        sm.addAction(locations_action)

        self._thresholds_action = QAction(_tr("menu.settings.thresholds", default="Donation / Exceptional Thresholds…"), self)
        self._thresholds_action.triggered.connect(self._open_threshold_preferences_dialog)
        sm.addAction(self._thresholds_action)

        self._optimizer_search_settings_action = QAction(
            _tr("menu.settings.optimizer_search_settings", default="Optimizer Search Settings…"),
            self,
        )
        self._optimizer_search_settings_action.triggered.connect(self._open_optimizer_search_settings_dialog)
        sm.addAction(self._optimizer_search_settings_action)

        sm.addSeparator()

        self._language_menu = sm.addMenu(_tr("language.menu"))
        self._language_group = QActionGroup(self)
        self._language_group.setExclusive(True)
        for language in _SUPPORTED_LANGUAGES:
            action = QAction(_language_label(language), self)
            action.setCheckable(True)
            action.setChecked(language == _current_language())
            action.triggered.connect(lambda checked=False, lang=language: self._change_language(lang))
            self._language_group.addAction(action)
            self._language_menu.addAction(action)

        hm = self.menuBar().addMenu(_tr("menu.help", default="Help"))
        self._getting_started_action = QAction(_tr("menu.help.getting_started", default="Getting Started"), self)
        self._getting_started_action.triggered.connect(self._show_onboarding_dialog)
        hm.addAction(self._getting_started_action)

        self._whats_new_action = QAction(_tr("menu.help.whats_new", default="What's New"), self)
        self._whats_new_action.triggered.connect(self._show_whats_new_dialog)
        hm.addAction(self._whats_new_action)

        hm.addSeparator()
        self._about_action = QAction(_tr("menu.help.about", default="About"), self)
        self._about_action.triggered.connect(self._show_about_dialog)
        hm.addAction(self._about_action)

    def _refresh_recent_save_actions(self):
        if not hasattr(self, "_recent_saves_menu"):
            return
        self._recent_saves_menu.clear()
        self._recent_save_actions = []

        saves = find_save_files()
        if not saves:
            action = QAction(_tr("menu.file.no_saves_found", path=_save_root_dir()), self)
            action.setEnabled(False)
            self._recent_saves_menu.addAction(action)
            self._recent_save_actions.append(action)
            return

        for path in saves[:10]:
            action = QAction(os.path.basename(path), self)
            action.setToolTip(path)
            action.triggered.connect(lambda _, p=path: self.load_save(p))
            self._recent_saves_menu.addAction(action)
            self._recent_save_actions.append(action)

    def _open_locations_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(_tr("dialog.locations.title"))
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        game_title = QLabel(_tr("dialog.locations.game_install"))
        game_title.setStyleSheet(_NAME_STYLE)
        game_path_label = QLabel()
        game_path_label.setWordWrap(True)
        game_path_label.setStyleSheet(_META_STYLE)

        save_title = QLabel(_tr("dialog.locations.save_root"))
        save_title.setStyleSheet(_NAME_STYLE)
        save_path_label = QLabel()
        save_path_label.setWordWrap(True)
        save_path_label.setStyleSheet(_META_STYLE)

        note_label = QLabel(_tr("dialog.locations.note", path=APPDATA_SAVE_DIR))
        note_label.setWordWrap(True)
        note_label.setStyleSheet(_META_STYLE)

        def _refresh_labels():
            game_path_label.setText(_GPAK_PATH or _tr("common.not_found"))
            save_path_label.setText(_save_root_dir())

        def _choose_game_dir():
            start_dir = os.path.dirname(_GPAK_PATH) if _GPAK_PATH else _gpak_search_start_dir()
            chosen_dir = QFileDialog.getExistingDirectory(
                dlg,
                _tr("dialog.locations.select_game_folder"),
                start_dir,
            )
            if not chosen_dir:
                return
            gpak_path = os.path.join(chosen_dir, "resources.gpak")
            if not os.path.exists(gpak_path):
                QMessageBox.warning(
                    dlg,
                    _tr("dialog.locations.resources_not_found.title"),
                    _tr("dialog.locations.resources_not_found.body"),
                )
                return
            _set_gpak_path(gpak_path)
            _refresh_labels()
            if self._current_save:
                self.load_save(self._current_save)
            self.statusBar().showMessage(_tr("status.using_game_data", path=gpak_path))

        def _choose_save_dir():
            chosen_dir = QFileDialog.getExistingDirectory(
                dlg,
                _tr("dialog.locations.select_save_root"),
                _save_root_dir(),
            )
            if not chosen_dir:
                return
            _set_save_dir(chosen_dir)
            _refresh_labels()
            self._refresh_recent_save_actions()
            self.statusBar().showMessage(_tr("status.using_save_root", path=chosen_dir))

        game_btn = QPushButton(_tr("dialog.locations.change_game_folder"))
        game_btn.clicked.connect(_choose_game_dir)
        save_btn = QPushButton(_tr("dialog.locations.change_save_root"))
        save_btn.clicked.connect(_choose_save_dir)

        layout.addWidget(game_title)
        layout.addWidget(game_path_label)
        layout.addWidget(game_btn)
        layout.addSpacing(8)
        layout.addWidget(save_title)
        layout.addWidget(save_path_label)
        layout.addWidget(save_btn)
        layout.addSpacing(8)
        layout.addWidget(note_label)

        close_btn = QPushButton(_tr("common.close"))
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

        _refresh_labels()
        dlg.resize(640, 260)
        dlg.exec()

    def _open_threshold_preferences_dialog(self):
        dlg = ThresholdPreferencesDialog(self, _load_threshold_preferences(), self._cats)
        if dlg.exec() != QDialog.Accepted:
            return
        prefs = dlg.preferences()
        _save_threshold_preferences(prefs)
        self._refresh_threshold_runtime(self._cats)
        room_key = None
        if self._active_btn is not None:
            for key, btn in self._room_btns.items():
                if btn is self._active_btn:
                    room_key = key
                    break
        self._refresh_threshold_sensitive_ui(room_key)
        self.statusBar().showMessage(
            _tr("status.thresholds_saved", default="Threshold preferences saved")
        )

    def _open_optimizer_search_settings_dialog(self):
        dlg = SharedOptimizerSearchSettingsDialog(self, _load_optimizer_search_settings())
        if dlg.exec() != QDialog.Accepted:
            return
        settings = dlg.preferences()
        _save_optimizer_search_settings(settings)
        self.statusBar().showMessage(
            _tr("status.optimizer_search_settings_saved", default="Optimizer search settings saved")
        )

    def _show_about_dialog(self):
        AboutDialog(self).exec()

    def _show_whats_new_dialog(self, mark_seen: bool = True):
        dlg = WhatsNewDialog(self, APP_VERSION)
        dlg.exec()
        if mark_seen:
            _set_last_seen_version(APP_VERSION)

    def _show_onboarding_dialog(self, mark_seen: bool = False):
        OnboardingDialog(self).exec()
        if mark_seen:
            _set_last_seen_version(APP_VERSION)

    def _show_getting_started_prompt(self):
        dlg = GettingStartedPromptDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.choice == GettingStartedPromptDialog.ALWAYS_SKIP:
            _set_show_getting_started_prompt(False)
            return
        if dlg.choice == GettingStartedPromptDialog.OPEN_GUIDE:
            self._show_onboarding_dialog(mark_seen=True)

    def _maybe_show_startup_dialogs(self):
        if self._startup_dialogs_shown:
            return
        self._startup_dialogs_shown = True
        last_seen = _saved_last_seen_version()
        if last_seen != APP_VERSION:
            self._show_whats_new_dialog(mark_seen=True)
        if _saved_show_getting_started_prompt(True):
            self._show_getting_started_prompt()

    def _on_startup_save_load_finished_for_dialogs(self):
        # Run once on the next idle tick so the splash close + window paint
        # both finish before the modal prompt blocks the event loop.
        try:
            self.startup_save_load_finished.disconnect(
                self._on_startup_save_load_finished_for_dialogs
            )
        except (TypeError, RuntimeError):
            pass
        QTimer.singleShot(0, self._maybe_show_startup_dialogs)

    def _apply_accessibility_style(self, preset: str):
        app = QApplication.instance()
        if preset == "High Contrast":
            app.setStyleSheet(_high_contrast_stylesheet())
        else:
            app.setStyleSheet(self._default_app_stylesheet)

    def _refresh_accessibility_action_checks(self):
        for name, action in getattr(self, "_accessibility_actions", {}).items():
            action.blockSignals(True)
            try:
                action.setChecked(name == self._accessibility_preset)
            finally:
                action.blockSignals(False)

    def _apply_accessibility_preset(self, preset_name: str, persist: bool = True):
        presets = {
            "Default": {"zoom": 100, "font": 0},
            "Comfort": {"zoom": 110, "font": 2},
            "High Contrast": {"zoom": 100, "font": 1},
            "Large Table": {"zoom": 100, "font": 3},
        }
        preset_name = preset_name if preset_name in presets else "Default"
        self._accessibility_preset = preset_name
        self._apply_accessibility_style(preset_name)
        preset = presets[preset_name]
        if persist:
            _set_accessibility_preset(preset_name)
            self._set_zoom(preset["zoom"])
            self._set_font_size_offset(preset["font"])
        self._refresh_accessibility_action_checks()

    def _toggle_total_stats_display(self, checked: bool):
        enabled = bool(checked)
        _set_total_stats_display(enabled)
        if hasattr(self, "_source_model"):
            self._source_model.set_show_total_stats(enabled)
        self._update_header(self._current_room_key())
        self.statusBar().showMessage(
            _tr("status.total_stats_display", default="Roster total-stat display {state}", state=_tr("common.on", default="on") if enabled else _tr("common.off", default="off"))
        )

    def _toggle_stat_icon_mode(self, checked: bool):
        enabled = bool(checked)
        _set_stat_icon_mode(enabled)
        if hasattr(self, "_source_model"):
            self._source_model.set_show_stat_icons(enabled)
        if self._detail and self._detail.current_cats:
            self._detail.show_cats(self._detail.current_cats)
        self.statusBar().showMessage(
            _tr("status.stat_icons_display", default="Roster stat icons {state}", state=_tr("common.on", default="on") if enabled else _tr("common.off", default="off"))
        )

    # Row height (px) used when roster visual mode is on. Chosen to be
    # roughly 2.25x the default compact row height so sprites and ability
    # icons are large enough to read at a glance.
    _VISUAL_ROW_HEIGHT = 70
    _VISUAL_SPRITE_SIZE = 62
    _VISUAL_ABIL_COL_WIDTH = 360
    _VISUAL_MUTS_COL_WIDTH = 300
    _VISUAL_NAME_COL_WIDTH = 240

    def _toggle_roster_visual_mode(self, checked: bool):
        enabled = bool(checked)
        _set_roster_visual_mode(enabled)
        self._apply_roster_visual_mode(enabled)
        self.statusBar().showMessage(
            _tr(
                "status.roster_visual_mode",
                default="Roster visual mode {state}",
                state=_tr("common.on", default="on") if enabled else _tr("common.off", default="off"),
            )
        )

    def _apply_roster_visual_mode(self, enabled: bool):
        """Push visual-mode state into the model, row height, and columns."""
        if not hasattr(self, "_source_model"):
            return
        self._source_model.set_visual_mode(enabled, sprite_size=self._VISUAL_SPRITE_SIZE)
        if hasattr(self, "_table"):
            vh = self._table.verticalHeader()
            if enabled:
                vh.setDefaultSectionSize(self._scaled(self._VISUAL_ROW_HEIGHT))
                self._table.setIconSize(QSize(self._VISUAL_SPRITE_SIZE, self._VISUAL_SPRITE_SIZE))
                # Widen name / abilities / mutations so icons have room.
                self._table.setColumnWidth(COL_NAME, max(self._table.columnWidth(COL_NAME), self._VISUAL_NAME_COL_WIDTH))
                self._table.setColumnWidth(COL_ABIL, max(self._table.columnWidth(COL_ABIL), self._VISUAL_ABIL_COL_WIDTH))
                self._table.setColumnWidth(COL_MUTS, max(self._table.columnWidth(COL_MUTS), self._VISUAL_MUTS_COL_WIDTH))
            else:
                vh.setDefaultSectionSize(self._scaled(24))
                self._table.setIconSize(QSize(16, 16))
                # Restore column widths to their base defaults.
                if hasattr(self, "_base_col_widths"):
                    for col in (COL_NAME, COL_ABIL, COL_MUTS):
                        if col in self._base_col_widths:
                            self._table.setColumnWidth(col, self._base_col_widths[col])
            self._table.viewport().update()
        clear_cat_sprite_cache()
        clear_mutation_part_cache()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        rl = QHBoxLayout(central)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        hs = QSplitter(Qt.Horizontal)
        hs.setObjectName("main_window_sidebar_splitter")
        self._sidebar_splitter = hs
        rl.addWidget(hs)
        hs.addWidget(self._build_sidebar())
        hs.addWidget(self._build_content())
        hs.setStretchFactor(0, 0)
        hs.setStretchFactor(1, 1)
        hs.setSizes([190, 1250])
        _enforce_min_font_in_widget_tree(central)
        # Snapshot all stylesheet font sizes before any offset is applied,
        # so _apply_font_offset_to_tree always scales from the true originals.
        _apply_font_offset_to_tree(central, 0)
        _bind_splitter_persistence(self)
        self._restore_roster_table_defaults()

    def _restore_roster_table_defaults(self):
        if not hasattr(self, "_table") or self._table is None or self._table.model() is None:
            return
        col_count = self._table.model().columnCount()
        for col in range(col_count):
            self._table.setColumnHidden(col, col in (COL_GEN_DEPTH, COL_SRC))
        self._pin_roster_special_columns()

    def _pin_roster_special_columns(self):
        if not hasattr(self, "_table") or self._table is None or self._table.model() is None:
            return
        header = self._table.horizontalHeader()
        col_count = self._table.model().columnCount()
        if COL_TAGS < col_count:
            try:
                tags_visual = header.visualIndex(COL_TAGS)
                if tags_visual >= 0 and tags_visual != 0:
                    header.moveSection(tags_visual, 0)
            except Exception:
                pass
        if COL_ADV < col_count:
            try:
                adv_visual = header.visualIndex(COL_ADV)
                if adv_visual >= 0 and adv_visual != header.count() - 1:
                    header.moveSection(adv_visual, header.count() - 1)
            except Exception:
                pass

    # ── Sidebar ────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setFixedWidth(self._base_sidebar_width)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { background:#14142a; border:none; }"
            "QScrollBar:vertical { background:#14142a; width:6px; }"
            "QScrollBar::handle:vertical { background:#2a2a4a; border-radius:3px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
        )
        w = QWidget()
        self._sidebar = w
        w.setStyleSheet("background:#14142a;")
        vb = QVBoxLayout(w)
        vb.setContentsMargins(8, 14, 8, 12)
        vb.setSpacing(2)

        def sl(text):
            l = QLabel(text)
            # letter-spacing is not supported by Qt QSS — apply via QFont
            # to avoid "Could not parse stylesheet" warnings.
            l.setStyleSheet("color:#444; font-size:10px; font-weight:bold;"
                            " padding:8px 4px 4px 4px;")
            f = l.font()
            f.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
            l.setFont(f)
            return l

        self._filters_section_label = sl(_tr("sidebar.section.filters"))
        vb.addWidget(self._filters_section_label)
        self._btn_everyone = _sidebar_btn(_tr("sidebar.button.all_cats"))
        self._btn_everyone.clicked.connect(
            lambda: self._filter("__all__", self._btn_everyone))
        vb.addWidget(self._btn_everyone)
        self._room_btns["__all__"] = self._btn_everyone

        self._btn_all = _sidebar_btn(_tr("sidebar.button.alive_cats"))
        self._btn_all.setChecked(True)
        self._active_btn = self._btn_all
        self._btn_all.clicked.connect(lambda: self._filter(None, self._btn_all))
        vb.addWidget(self._btn_all)
        self._room_btns[None] = self._btn_all

        self._btn_exceptional = _sidebar_btn("")
        self._btn_exceptional.setToolTip("")
        self._btn_exceptional.clicked.connect(
            lambda: self._filter("__exceptional__", self._btn_exceptional)
        )
        vb.addWidget(self._btn_exceptional)
        self._room_btns["__exceptional__"] = self._btn_exceptional

        self._btn_donation = _sidebar_btn("")
        self._btn_donation.setToolTip("")
        self._btn_donation.clicked.connect(
            lambda: self._filter("__donation__", self._btn_donation)
        )
        vb.addWidget(self._btn_donation)
        self._room_btns["__donation__"] = self._btn_donation

        self._btn_fight_club = _sidebar_btn(_tr("sidebar.button.fight_club", default="Fight Club"))
        self._btn_fight_club.clicked.connect(lambda: self._filter("__fight_club__", self._btn_fight_club))
        vb.addWidget(self._btn_fight_club)
        self._room_btns["__fight_club__"] = self._btn_fight_club

        vb.addWidget(_hsep())
        self._sorting_section_label = sl(_tr("sidebar.section.cat_sorting", default="CAT SCORING"))
        vb.addWidget(self._sorting_section_label)
        self._btn_manual_scoring = _sidebar_btn(_tr("sidebar.button.manual_scoring", default="Simple Scoring"))
        self._btn_manual_scoring.clicked.connect(self._open_manual_scoring_view)
        vb.addWidget(self._btn_manual_scoring)
        self._btn_breed_priority = _sidebar_btn(_tr("sidebar.button.breed_priority", default="Detailed Scoring"))
        self._btn_breed_priority.clicked.connect(self._open_breed_priority_view)
        vb.addWidget(self._btn_breed_priority)

        vb.addWidget(_hsep())
        self._breeding_section_label = sl(_tr("sidebar.section.breeding"))
        vb.addWidget(self._breeding_section_label)
        self._btn_room_optimizer = _sidebar_btn(_tr("sidebar.button.room_optimizer"))
        self._btn_room_optimizer.clicked.connect(self._open_room_optimizer)
        vb.addWidget(self._btn_room_optimizer)
        self._btn_perfect_planner = _sidebar_btn(_tr("sidebar.button.perfect_7_planner"))
        self._btn_perfect_planner.clicked.connect(self._open_perfect_planner_view)
        vb.addWidget(self._btn_perfect_planner)
        self._btn_mutation_planner = _sidebar_btn(_tr("sidebar.button.mutation_planner"))
        self._btn_mutation_planner.clicked.connect(self._open_mutation_planner_view)
        vb.addWidget(self._btn_mutation_planner)
        self._btn_safe_breeding_view = _sidebar_btn(_tr("sidebar.button.mating_pair_search", default="Mating Pair Search"))
        self._btn_safe_breeding_view.clicked.connect(self._open_safe_breeding_view)
        vb.addWidget(self._btn_safe_breeding_view)
        self._btn_breeding_partners_view = _sidebar_btn(_tr("sidebar.button.breeding_partners"))
        self._btn_breeding_partners_view.clicked.connect(self._open_breeding_partners_view)
        vb.addWidget(self._btn_breeding_partners_view)

        vb.addWidget(_hsep())
        self._info_section_label = sl(_tr("sidebar.section.info"))
        vb.addWidget(self._info_section_label)
        self._btn_tree_view = _sidebar_btn(_tr("sidebar.button.family_tree_view"))
        self._btn_tree_view.clicked.connect(self._open_tree_browser)
        vb.addWidget(self._btn_tree_view)
        self._btn_furniture_view = _sidebar_btn(_tr("sidebar.button.furniture", default="Furniture"))
        self._btn_furniture_view.clicked.connect(self._open_furniture_view)
        vb.addWidget(self._btn_furniture_view)
        self._btn_calibration = _sidebar_btn(_tr("sidebar.button.calibration"))
        self._btn_calibration.clicked.connect(self._open_calibration_view)
        vb.addWidget(self._btn_calibration)

        vb.addWidget(_hsep())
        self._rooms_section_label = sl(_tr("sidebar.section.rooms"))
        vb.addWidget(self._rooms_section_label)
        self._rooms_vb = QVBoxLayout(); self._rooms_vb.setSpacing(2)
        vb.addLayout(self._rooms_vb)
        vb.addWidget(_hsep())

        self._other_section_label = sl(_tr("sidebar.section.other"))
        vb.addWidget(self._other_section_label)
        self._btn_adventure = _sidebar_btn(_tr("sidebar.button.on_adventure"))
        self._btn_gone      = _sidebar_btn(_tr("sidebar.button.gone"))
        self._btn_adventure.clicked.connect(
            lambda: self._filter("__adventure__", self._btn_adventure))
        self._btn_gone.clicked.connect(
            lambda: self._filter("__gone__", self._btn_gone))
        vb.addWidget(self._btn_adventure)
        vb.addWidget(self._btn_gone)
        self._room_btns["__adventure__"] = self._btn_adventure
        self._room_btns["__gone__"]      = self._btn_gone

        vb.addStretch()

        self._version_lbl = QLabel(f'<a href="whats-new://{APP_VERSION}">v{APP_VERSION}</a>')
        self._version_lbl.setTextFormat(Qt.RichText)
        self._version_lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self._version_lbl.setOpenExternalLinks(False)
        self._version_lbl.linkActivated.connect(lambda _link: self._show_whats_new_dialog())
        self._version_lbl.setStyleSheet("color:#666; font-size:10px; padding:0 4px 2px 4px;")
        self._version_lbl.setToolTip(f"Click to view release notes for {APP_VERSION}")
        vb.addWidget(self._version_lbl)

        self._save_lbl = QLabel(_tr("sidebar.no_save_loaded"))
        self._save_lbl.setStyleSheet("color:#444; font-size:10px;")
        self._save_lbl.setWordWrap(True)
        vb.addWidget(self._save_lbl)

        self._reload_btn = QPushButton(_tr("sidebar.button.reload"))
        self._reload_btn.setStyleSheet("QPushButton { color:#888; background:#1a1a32;"
                         " border:1px solid #2a2a4a; padding:7px;"
                         " border-radius:4px; font-size:11px; }"
                         "QPushButton:hover { background:#222244; }")
        self._reload_btn.clicked.connect(self._reload)
        vb.addWidget(self._reload_btn)
        self._refresh_filter_button_counts()
        scroll.setWidget(w)
        return scroll

    def _rebuild_room_buttons(self, cats: list[Cat]):
        # Capture the active room key BEFORE destroying buttons so we can
        # repoint `_active_btn` at the replacement for the same room. Without
        # this rescue, `_active_btn` keeps pointing at a deleted C++ widget,
        # and the next `_filter()` call raises RuntimeError on setChecked()
        # mid-handler — leaving the clicked room button highlighted but the
        # actual filter unchanged. See the "menu tab won't switch after an
        # in-game day" regression.
        active_room_key = self._active_room_key()
        while self._rooms_vb.count():
            item = self._rooms_vb.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Drop stale room entries — rooms that no longer exist (e.g., last
        # cat moved out of Attic) would otherwise leak deleted-widget
        # references in `_room_btns` forever.  Preserve permanent filter
        # entries (None, "__all__", "__exceptional__", …) so that
        # _active_room_key(), _current_room_key(), and nav restore keep
        # working after a rebuild.
        if active_room_key is not None and active_room_key in self._room_btns:
            # Null out first so `_active_btn` doesn't briefly point at a
            # dangling entry while we rebuild.
            self._active_btn = None
        _PERMANENT_KEYS = {
            None, "__all__", "__exceptional__", "__donation__",
            "__fight_club__", "__adventure__", "__gone__",
        }
        stale = [k for k in self._room_btns if k not in _PERMANENT_KEYS]
        for k in stale:
            del self._room_btns[k]
        _ROOM_ORDER = {
            "Attic": 0,
            "Floor2_Large": 1, "Floor2_Small": 2,
            "Floor1_Large": 3, "Floor1_Small": 4,
        }
        rooms = sorted(
            {c.room for c in cats if c.status == "In House" and c.room},
            key=lambda r: _ROOM_ORDER.get(r, 99),
        )
        for room in rooms:
            count = sum(1 for c in cats if c.room == room)
            display = ROOM_DISPLAY.get(room, room)
            btn = _sidebar_btn(f"{display}  ({count})")
            btn.clicked.connect(lambda _, r=room, b=btn: self._filter(r, b))
            self._rooms_vb.addWidget(btn)
            self._room_btns[room] = btn
        # Repoint `_active_btn` at the rebuilt button for the previously
        # active room (if that room still exists after the refresh).
        if active_room_key is not None and active_room_key in self._room_btns:
            self._active_btn = self._room_btns[active_room_key]
            self._active_btn.setChecked(True)

    def _refresh_filter_button_counts(self):
        total = len(self._cats)
        alive = sum(1 for c in self._cats if c.status != "Gone")
        exceptional = sum(1 for c in self._cats if c.status != "Gone" and _is_exceptional_breeder(c))
        donation = sum(1 for c in self._cats if c.status != "Gone" and _is_donation_candidate(c))
        fight_club = sum(
            1 for c in self._cats
            if c.status != "Gone"
            and not c.has_adventured
            and c.db_key in self._accessible_cat_keys
        )
        adv = sum(1 for c in self._cats if c.status == "Adventure")
        gone = sum(1 for c in self._cats if c.status == "Gone")

        self._btn_everyone.setText(f"{_tr('sidebar.button.all_cats')}  ({total})" if total else _tr("sidebar.button.all_cats"))
        self._btn_all.setText(f"{_tr('sidebar.button.alive_cats')}  ({alive})" if total else _tr("sidebar.button.alive_cats"))
        self._btn_exceptional.setText(f"{_tr('sidebar.button.exceptional')}  ({exceptional})")
        self._btn_donation.setText(f"{_tr('sidebar.button.donation_candidates')}  ({donation})")
        if hasattr(self, "_btn_fight_club"):
            self._btn_fight_club.setText(
                f"{_tr('sidebar.button.fight_club', default='Fight Club')}  ({fight_club})"
                if total else _tr("sidebar.button.fight_club", default="Fight Club")
            )
        self._btn_adventure.setText(f"{_tr('sidebar.button.on_adventure')}  ({adv})" if total else _tr("sidebar.button.on_adventure"))
        self._btn_gone.setText(f"{_tr('sidebar.button.gone')}  ({gone})" if total else _tr("sidebar.button.gone"))
        self._btn_room_optimizer.setText(_tr("sidebar.button.room_optimizer"))
        self._btn_perfect_planner.setText(_tr("sidebar.button.perfect_7_planner"))
        self._btn_mutation_planner.setText(_tr("sidebar.button.mutation_planner"))
        self._btn_safe_breeding_view.setText(_tr("sidebar.button.mating_pair_search", default="Mating Pair Search"))
        self._btn_breeding_partners_view.setText(_tr("sidebar.button.breeding_partners"))
        self._btn_tree_view.setText(_tr("sidebar.button.family_tree_view"))
        self._btn_calibration.setText(_tr("sidebar.button.calibration"))
        self._btn_furniture_view.setText(_tr("sidebar.button.furniture", default="Furniture"))
        self._update_threshold_button_copy()

    def _update_threshold_button_copy(self):
        if not hasattr(self, "_btn_exceptional") or not hasattr(self, "_btn_donation"):
            return
        summary = _current_threshold_summary(self._cats)
        exceptional = summary["exceptional"]
        donation = summary["donation"]
        top_stat = summary["top_stat"]
        avg_sum = summary["avg_sum"]
        base_exceptional = summary["base_exceptional"]
        base_donation = summary["base_donation"]
        adaptive = summary["adaptive_enabled"]
        planner_traits = self._mutation_planner_view.get_selected_traits() if self._mutation_planner_view is not None else []
        mutation_ability_traits = [t for t in planner_traits if t.get("category") in {"mutation", "ability"}]
        planner_note = ""
        if summary.get("donation_missing_planner_traits"):
            if mutation_ability_traits:
                planner_note = (
                    " Donation candidates are cats missing selected mutation/ability traits and still under the stat floor"
                    f" ({_planner_import_traits_summary(mutation_ability_traits)})."
                )
            else:
                planner_note = (
                    " Donation candidates are cats missing selected mutation/ability traits and still under the stat floor."
                )
        from mewgenics.utils.thresholds import (
            SCORE_SOURCE, DETAILED_EXCEPTIONAL_THRESHOLD, DETAILED_DONATION_THRESHOLD,
            _detailed_scores_ready,
        )
        if SCORE_SOURCE == "detailed" and _detailed_scores_ready():
            self._btn_exceptional.setToolTip(
                f"Exceptional breeders: Detailed Scoring total >= {DETAILED_EXCEPTIONAL_THRESHOLD:+.1f}."
            )
            self._btn_donation.setToolTip(
                "Donation candidates: Detailed Scoring total "
                f"<= {DETAILED_DONATION_THRESHOLD:+.1f}, and/or high aggression." + planner_note
            )
        elif adaptive:
            self._btn_exceptional.setToolTip(
                "Exceptional breeders follow the living-cat average curve: "
                f"base {base_exceptional}, reference avg {summary['adaptive_reference_avg_sum']:.1f}, "
                f"curve {summary['adaptive_curve_strength']:.2f}, current avg {avg_sum:.1f} -> {exceptional}."
            )
            self._btn_donation.setToolTip(
                "Donation candidates follow the living-cat average curve: "
                f"base {base_donation}, reference avg {summary['adaptive_reference_avg_sum']:.1f}, "
                f"curve {summary['adaptive_curve_strength']:.2f}, current avg {avg_sum:.1f} -> {donation}, "
                f"top stat cap {top_stat}." + planner_note
            )
        else:
            self._btn_exceptional.setToolTip(
                f"Exceptional breeders: base stat sum >= {exceptional}."
            )
            self._btn_donation.setToolTip(
                "Donation candidates use documented heuristics: "
                f"base stat sum <= {donation}, "
                f"top stat <= {top_stat}, and/or high aggression." + planner_note
            )

    def _refresh_threshold_runtime(self, cats: list[Cat] | None = None):
        _apply_threshold_preferences(_load_threshold_preferences(), cats if cats is not None else self._cats)

    def _sync_donation_planner_traits(self):
        traits = self._mutation_planner_view.get_selected_traits() if self._mutation_planner_view is not None else []
        _set_donation_planner_traits(traits)
        room_key = None
        if self._active_btn is not None:
            for key, btn in self._room_btns.items():
                if btn is self._active_btn:
                    room_key = key
                    break
        self._refresh_threshold…27019 tokens truncated…breeding_partners_view.set_cats(filtered)
            self._view_generation["breeding_partners"] = self._cats_generation
        if self._perfect_planner_view is not None and self._perfect_planner_view.isVisible():
            self._perfect_planner_view.set_cats(filtered)
            self._view_generation["perfect_planner"] = self._cats_generation
        if self._breed_priority_view is not None and self._breed_priority_view.isVisible():
            self._breed_priority_view.set_cats(filtered)
            self._view_generation["breed_priority"] = self._cats_generation

    def _clear_tag_filter(self):
        """Remove all tag filters."""
        self._proxy_model.set_tag_filter(set())
        self._update_count()
        self._refresh_views_for_tag_filter()
        self._tags_btn.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:3px 10px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
            "QPushButton::menu-indicator { image:none; }")

    def _open_tag_manager(self):
        dlg = TagManagerDialog(self)
        dlg.exec()
        _TAG_ICON_CACHE.clear()
        _TAG_PIX_CACHE.clear()
        if hasattr(self, "_source_model") and self._source_model is not None and self._source_model.rowCount() > 0:
            top_left = self._source_model.index(0, COL_TAGS)
            bottom_right = self._source_model.index(max(0, self._source_model.rowCount() - 1), COL_TAGS)
            self._source_model.dataChanged.emit(
                top_left,
                bottom_right,
                [Qt.DisplayRole, Qt.DecorationRole, Qt.ToolTipRole, Qt.UserRole],
            )
        if self._cats:
            self._bump_cats_generation()
            if self._tree_view is not None and self._tree_view.isVisible():
                self._set_view_cats_if_needed("tree", self._tree_view, self._cats)
            if self._safe_breeding_view is not None and self._safe_breeding_view.isVisible():
                self._set_view_cats_if_needed("safe_breeding", self._safe_breeding_view, self._cats)
            if self._breeding_partners_view is not None and self._breeding_partners_view.isVisible():
                self._set_view_cats_if_needed("breeding_partners", self._breeding_partners_view, self._cats)
            if self._room_optimizer_view is not None and self._room_optimizer_view.isVisible():
                self._set_view_cats_if_needed("room_optimizer", self._room_optimizer_view, self._cats)
            if self._perfect_planner_view is not None and self._perfect_planner_view.isVisible():
                self._set_view_cats_if_needed("perfect_planner", self._perfect_planner_view, self._cats)
            if self._calibration_view is not None and self._calibration_view.isVisible():
                self._calibration_view.set_context(self._current_save, self._cats)
                self._view_generation["calibration"] = self._cats_generation
        # Repaint table without invalidating selection
        self._table.viewport().update()
        if self._detail and self._detail.current_cats:
            self._detail.show_cats(self._detail.current_cats)
        if self._current_save:
            _save_tags(self._current_save, self._cats)

    def _on_blacklist_changed(self):
        if self._current_save:
            _save_blacklist(self._current_save, self._cats)
            _save_must_breed(self._current_save, self._cats)
            _save_pinned(self._current_save, self._cats)
            _save_tags(self._current_save, self._cats)
            _save_not_adventured(self._current_save, self._cats)
        self._refresh_bulk_view_buttons()
        self._bump_cats_generation()
        if self._safe_breeding_view is not None and self._safe_breeding_view.isVisible():
            self._set_view_cats_if_needed("safe_breeding", self._safe_breeding_view, self._cats)
        if self._breeding_partners_view is not None and self._breeding_partners_view.isVisible():
            self._set_view_cats_if_needed("breeding_partners", self._breeding_partners_view, self._cats)
        if self._room_optimizer_view is not None and self._room_optimizer_view.isVisible():
            self._set_view_cats_if_needed("room_optimizer", self._room_optimizer_view, self._cats)
        if self._perfect_planner_view is not None and self._perfect_planner_view.isVisible():
            self._set_view_cats_if_needed("perfect_planner", self._perfect_planner_view, self._cats)

    def _on_calibration_changed(self):
        if not self._current_save:
            return
        cal_explicit, cal_token, cal_rows = _apply_calibration(self._current_save, self._cats)
        self._source_model.load(self._cats)
        self._refresh_filter_button_counts()
        self._bump_cats_generation()
        if self._safe_breeding_view is not None and self._safe_breeding_view.isVisible():
            self._set_view_cats_if_needed("safe_breeding", self._safe_breeding_view, self._cats)
        if self._breeding_partners_view is not None and self._breeding_partners_view.isVisible():
            self._set_view_cats_if_needed("breeding_partners", self._breeding_partners_view, self._cats)
        if self._room_optimizer_view is not None and self._room_optimizer_view.isVisible():
            self._set_view_cats_if_needed("room_optimizer", self._room_optimizer_view, self._cats)
        if self._perfect_planner_view is not None and self._perfect_planner_view.isVisible():
            self._set_view_cats_if_needed("perfect_planner", self._perfect_planner_view, self._cats)
        if self._calibration_view is not None and self._calibration_view.isVisible():
            self._calibration_view.set_context(self._current_save, self._cats)
            self._view_generation["calibration"] = self._cats_generation
        self._update_count()
        self.statusBar().showMessage(
            _tr("status.calibration_applied", default="Calibration applied ({explicit} explicit, {token} token from {rows} rows)", explicit=cal_explicit, token=cal_token, rows=cal_rows)
        )

    # ── Breeding cache ──────────────────────────────────────────────────

    @staticmethod
    def _cache_cat_fingerprint(cat: 'Cat') -> tuple:
        """Tuple of every field that affects cache computation (not room/display)."""
        return _breeding_cache_fingerprint(cat)

    def _only_display_changed(self, new_cats: list['Cat']) -> bool:
        """Return True if self._cats and new_cats differ only in display fields (e.g. room)."""
        if not self._cats:
            return False
        old_fps = {c.db_key: self._cache_cat_fingerprint(c) for c in self._cats}
        new_fps = {c.db_key: self._cache_cat_fingerprint(c) for c in new_cats}
        return old_fps == new_fps

    def _start_breeding_cache(self, cats: list[Cat], force_full: bool = False):
        """Kick off background computation of the breeding cache."""
        # Fast path: skip rebuild when only display fields (e.g. room) changed
        if (not force_full
                and self._breeding_cache is not None
                and self._breeding_cache.ready
                and self._only_display_changed(cats)):
            # Refresh cat object references so views see updated rooms
            self._breeding_cache.refresh_cat_index(cats)
            # Keep _prev_parent_keys current for the next reload's incremental check
            self._prev_parent_keys = {
                c.db_key: (
                    c.parent_a.db_key if c.parent_a is not None else None,
                    c.parent_b.db_key if c.parent_b is not None else None,
                )
                for c in cats
            }
            return

        # Retire any in-progress cache worker so it cleans up properly.
        # The stale worker's phase1_ready / finished_cache slots drop
        # the result by identity check (`is self._cache_worker`).
        self._retire_worker(self._cache_worker)
        self._cache_worker = None

        # Snapshot parent keys before clearing old cache (for incremental update)
        prev_cache = self._breeding_cache if not force_full else None
        prev_parent_keys = dict(self._prev_parent_keys) if hasattr(self, "_prev_parent_keys") and not force_full else {}

        # Record current parent keys for next reload
        self._prev_parent_keys = {
            c.db_key: (
                c.parent_a.db_key if c.parent_a is not None else None,
                c.parent_b.db_key if c.parent_b is not None else None,
            )
            for c in cats
        }

        self._breeding_cache = None
        self._cache_progress.setValue(0)
        self._cache_progress.show()

        # Try loading pairwise data from disk (skip if force_full)
        existing = None
        save_path = self._current_save or ""
        save_signature = _breeding_save_signature(cats)
        pedigree_coi_memos = getattr(self, "_pedigree_coi_memos", {})
        if not force_full and save_path:
            existing = BreedingCache.load_from_disk(save_path, save_signature)
            if existing is not None:
                self._cache_progress.setFormat(_tr("loading.cache.loading_cached"))
            elif prev_cache is not None:
                self._cache_progress.setFormat(_tr("loading.cache.updating"))
            else:
                self._cache_progress.setFormat(_tr("loading.cache.computing"))
        else:
            self._cache_progress.setFormat(_tr("loading.cache.computing"))

        worker = BreedingCacheWorker(
            cats, save_path=save_path, existing_pairwise=existing,
            prev_cache=prev_cache, prev_parent_keys=prev_parent_keys,
            save_signature=save_signature,
            pedigree_coi_memos=pedigree_coi_memos,
            parent=self,
        )
        worker.progress.connect(
            lambda cur, tot, w=worker: self._on_cache_progress(cur, tot, w)
        )
        worker.phase1_ready.connect(
            lambda cache, w=worker: self._on_phase1_ready(cache, source_worker=w)
        )
        worker.finished_cache.connect(
            lambda cache, w=worker: self._on_cache_ready(cache, source_worker=w)
        )
        worker.finished.connect(lambda w=worker: self._cache_progress.hide() if w is self._cache_worker else None)
        self._cache_worker = worker
        worker.start()

    def _on_cache_progress(self, current: int, total: int,
                           source_worker: Optional[BreedingCacheWorker] = None):
        if source_worker is not None and source_worker is not self._cache_worker:
            return  # stale worker — ignore
        self._cache_progress.setMaximum(total)
        self._cache_progress.setValue(current)

    def _clear_breeding_cache(self):
        """Delete the on-disk breeding cache for the current save file."""
        if not self._current_save:
            self.statusBar().showMessage(_tr("status.no_save_loaded_clear"))
            return
        cp = _breeding_cache_path(self._current_save)
        if os.path.exists(cp):
            try:
                os.remove(cp)
                self.statusBar().showMessage(_tr("status.cache_cleared"))
            except OSError as e:
                self.statusBar().showMessage(_tr("status.cache_delete_failed", default="Could not delete cache: {error}", error=e))
        else:
            self.statusBar().showMessage(_tr("status.cache_missing"))

    def _on_phase1_ready(self, cache: BreedingCache, source_worker: Optional[BreedingCacheWorker] = None):
        """Ancestry computed — push to table and Mating Pair Search so they're usable immediately."""
        # Drop results from superseded workers (a newer load_save has
        # started).  Without this check, a stale cache would overwrite
        # the fresh one currently being computed.
        if source_worker is not None and source_worker is not self._cache_worker:
            return
        self._breeding_cache = cache
        self._source_model.set_breeding_cache(cache)
        if self._safe_breeding_view is not None:
            self._safe_breeding_view.set_cache(cache)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_cache(cache)
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.set_cache(cache)
        self._cache_progress.setFormat(_tr("loading.cache.pair_risks"))

    def _on_cache_ready(self, cache: BreedingCache, source_worker: Optional[BreedingCacheWorker] = None):
        if source_worker is not None and source_worker is not self._cache_worker:
            return  # superseded — drop stale result
        self._breeding_cache = cache
        self._cache_worker = None
        self._cache_progress.hide()
        # Push completed cache (now includes pairwise risk) to all views
        self._source_model.set_breeding_cache(cache)
        if self._safe_breeding_view is not None:
            self._safe_breeding_view.set_cache(cache)
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.set_cache(cache)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_cache(cache)
        self.statusBar().showMessage(
            self.statusBar().currentMessage() + _tr("status.cache_ready_suffix", default="  |  Breeding cache ready")
        )

    def _on_save_load_failed(self, msg: str, is_transient: bool = True,
                              source_worker: Optional[SaveLoadWorker] = None):
        """Handle a SaveLoadWorker that raised during parsing.

        Only schedule a self-heal reload for transient I/O errors — a
        permanently broken save (corrupt file, parser bug, KeyError, etc.)
        must not spin the retry timer forever.  The next `fileChanged`
        event will re-trigger a load naturally if the game fixes the
        condition by writing a fresh save.
        """
        if source_worker is not None and source_worker is not self._save_load_worker:
            return  # superseded — a newer load is already running
        self._save_load_worker = None
        self._loading_overlay.hide()
        self.startup_save_load_finished.emit()
        if is_transient and self._save_load_retries < self._SAVE_LOAD_RETRY_CAP:
            self._save_load_retries += 1
            self.statusBar().showMessage(
                _tr("status.save_load_failed",
                    default="Save load failed ({error}) — retrying in 500 ms.",
                    error=msg)
            )
            QTimer.singleShot(500, self._reload)
        else:
            # Permanent failure or retry budget exhausted.  Leave the
            # error visible and let a fresh fileChanged event (or a
            # manual reload) reset the counter on success.
            self.statusBar().showMessage(
                _tr("status.save_load_failed_permanent",
                    default="Save load failed ({error}). Open a different save or fix the file.",
                    error=msg)
            )

    # ── Worker lifecycle ─────────────────────────────────────────────────

    @staticmethod
    def _retire_worker(worker: Optional[QThread]) -> None:
        """Gracefully retire a superseded QThread worker.

        Requests cancellation so the worker can exit its loop early,
        then schedules deleteLater on its finished signal so the C++
        QThread is cleaned up once it actually stops — without blocking
        the main thread.  This prevents zombie QThread accumulation that
        was causing the ~1-minute crash cycle when the game rewrites its
        save while MBM is open.
        """
        if worker is None:
            return
        # Guard against double-retirement: if we already wired up
        # deleteLater, don't connect it again.
        if getattr(worker, '_retired', False):
            return
        worker._retired = True
        worker.requestInterruption()
        # deleteLater must run after the thread's event loop exits.
        # Connecting to `finished` is safe even if the thread already
        # finished — Qt queues the call and it becomes a no-op.
        try:
            worker.finished.connect(worker.deleteLater)
        except RuntimeError:
            pass  # C++ object already destroyed

    # ── Loading ────────────────────────────────────────────────────────────

    def load_save(self, path: str, force_full_breeding_cache: bool = False):
        previous_save = self._current_save
        fresh_save = True
        if previous_save:
            fresh_save = os.path.normcase(os.path.abspath(previous_save)) != os.path.normcase(os.path.abspath(path))
        if fresh_save:
            self._breeding_cache = None
            self._prev_parent_keys = {}
        self._current_save = path
        _set_last_save(path)
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.set_save_path(path, refresh_existing=False)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_save_path(path, refresh_existing=False)
        if self._mutation_planner_view is not None:
            self._mutation_planner_view.set_save_path(path, refresh_existing=False, notify=False)
            if self._room_optimizer_view is not None:
                self._room_optimizer_view.on_planner_traits_changed()
            if self._perfect_planner_view is not None:
                self._perfect_planner_view.sync_mutation_traits()
                self._perfect_planner_view.sync_mutation_import_button_state()
        if self._watcher.files():
            self._watcher.removePaths(self._watcher.files())
        self._watcher.addPath(path)

        # Retire in-progress workers so they clean up properly instead
        # of accumulating as zombie QThreads.  requestInterruption lets
        # the worker exit early at its next check point, and finished
        # triggers deleteLater.  Identity checks in finished_load /
        # failed / phase1_ready / finished_cache slots discard any
        # stale results that slip through.
        self._retire_worker(self._save_load_worker)
        self._save_load_worker = None
        self._retire_worker(self._cache_worker)
        self._cache_worker = None

        # Show overlay while parsing (background thread — main thread stays responsive for repaint)
        name = os.path.basename(path)
        self._loading_label.setText(_tr("loading.save_named", name=name))
        overlay = self._loading_overlay
        parent = overlay.parentWidget()
        if parent:
            overlay.setGeometry(0, 0, parent.width(), parent.height())
        overlay.raise_()
        overlay.show()

        worker = SaveLoadWorker(path, parent=self)
        worker.finished_load.connect(
            lambda result, w=worker, force=force_full_breeding_cache:
                self._on_save_loaded(result, force, source_worker=w)
        )
        worker.failed.connect(
            lambda msg, transient, w=worker:
                self._on_save_load_failed(msg, transient, source_worker=w)
        )
        self._save_load_worker = worker
        worker.start()

    def _on_save_loaded(self, result: dict, force_full_breeding_cache: bool = False,
                        source_worker: Optional[SaveLoadWorker] = None):
        # Drop results from superseded workers — a newer load_save has
        # already started and points `_save_load_worker` at a different
        # instance.  Processing this result would overwrite fresh state
        # with stale data (or worse, if the stale worker managed to
        # complete during a crash-repro reload storm).
        if source_worker is not None and source_worker is not self._save_load_worker:
            return
        self._save_load_worker = None
        self._save_load_retries = 0  # success resets the self-heal counter
        # Dismiss overlay immediately — UI work below is fast (model.load is O(n), no ancestry)
        self._loading_overlay.hide()
        self.startup_save_load_finished.emit()
        self._save_view_disabled = True
        try:
            cats = result["cats"]
            errors = result["errors"]
            unlocked_house_rooms = result.get("unlocked_house_rooms", [])
            accessible_cats = result.get("accessible_cats", set())
            self._accessible_cat_keys = set(accessible_cats)
            self._proxy_model.set_accessible_cats(accessible_cats)
            furniture = result.get("furniture", [])
            furniture_by_room = result.get("furniture_by_room", {})
            applied_overrides = result["applied_overrides"]
            override_rows = result["override_rows"]
            cal_explicit = result["cal_explicit"]
            cal_token = result["cal_token"]
            cal_rows = result["cal_rows"]
            self._pedigree_coi_memos = dict(result.get("pedigree_coi_memos", {}))

            self._cats = cats
            self._bump_cats_generation()
            # Stale detailed-score cache is keyed by id(cat) from the previous
            # save — clear it so we fall back to base-sum until Detailed Scoring
            # reruns against the new objects.
            from mewgenics.utils.thresholds import _set_detailed_scores
            _set_detailed_scores({})
            self._furniture = furniture
            self._furniture_by_room = furniture_by_room
            self._furniture_data = dict(_FURNITURE_DATA)
            self._available_house_rooms = [room for room in ROOM_KEYS if room in set(unlocked_house_rooms)] or list(ROOM_KEYS)
            self._room_summaries = {
                summary.room: summary
                for summary in build_furniture_room_summaries(
                    self._furniture_by_room,
                    self._furniture_data,
                    self._cats,
                    room_order=self._available_house_rooms,
                )
                if summary.room in self._available_house_rooms or not summary.room
            }
            self._source_model.set_breeding_cache(None)
            if self._safe_breeding_view is not None:
                self._safe_breeding_view.set_cache(None)
            if self._breeding_partners_view is not None:
                self._breeding_partners_view.set_cache(None)
            if self._room_optimizer_view is not None:
                self._room_optimizer_view.set_cache(None)
            if self._perfect_planner_view is not None:
                self._perfect_planner_view.set_cache(None)
            self._refresh_threshold_runtime(cats)
            self._source_model.load(cats, accessible_cats=accessible_cats)
            self._rebuild_room_buttons(cats)
            self._refresh_filter_button_counts()
            self._filter(None, self._btn_all)
            if self._room_optimizer_view is not None:
                self._room_optimizer_view.set_available_rooms(self._available_house_rooms)
                self._room_optimizer_view.set_room_summaries(self._room_summaries)
            if self._furniture_view is not None:
                self._furniture_view.set_context(self._cats, self._furniture, self._furniture_data, available_rooms=self._available_house_rooms)
                self._view_generation["furniture"] = self._cats_generation
            # Cats are pushed to views on-demand when they become visible
            # (each _show_*_view calls _set_view_cats_if_needed).
            # _restore_current_view() in the finally block shows the active
            # view, which triggers the push for just that one view.

            # Initialize shared trait ratings
            if self._current_save:
                scoring_path = _scoring_path(self._current_save)
                self._trait_ratings = TraitRatings(scoring_path)
                if self._manual_scoring_view is not None:
                    self._manual_scoring_view.set_save_path(self._current_save)
                    self._manual_scoring_view.set_trait_ratings(self._trait_ratings)

            if self._calibration_view is not None:
                self._calibration_view.set_context(self._current_save, cats)
                self._view_generation["calibration"] = self._cats_generation
            self._sync_donation_planner_traits()
            name = os.path.basename(self._current_save)
            self._save_lbl.setText(name)
            self.setWindowTitle(_tr("app.title_with_save", name=name))

            msg = _tr("status.save_loaded", default="Loaded {count} cats from {name}", count=len(cats), name=name)
            if errors:
                msg += _tr("status.save_loaded.parse_errors_suffix", default="  ({count} parse errors)", count=len(errors))
            if applied_overrides:
                msg += _tr("status.save_loaded.gender_overrides_suffix", default="  ({applied}/{rows} gender overrides)", applied=applied_overrides, rows=override_rows)
            if cal_rows:
                msg += _tr("status.save_loaded.calibration_suffix", default="  (calibration: {explicit} explicit, {token} token)", explicit=cal_explicit, token=cal_token)
            self.statusBar().showMessage(msg)

            # Start background breeding cache computation
            self._start_breeding_cache(cats, force_full=force_full_breeding_cache)

            # Update default save menu items
            self._update_default_save_menu()
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            self.statusBar().showMessage(_tr("status.save_load_failed", default="Error loading save: {error}", error=e))
        finally:
            self._save_view_disabled = False
            self._restore_current_view()

    def _update_default_save_menu(self):
        """Update the enabled state of default save menu items."""
        has_save = self._current_save is not None
        default_save = _saved_default_save()
        is_current_default = has_save and default_save == self._current_save

        self._set_default_save_action.setEnabled(has_save and not is_current_default)
        self._clear_default_save_action.setEnabled(has_save and is_current_default)

    def _set_current_as_default(self):
        """Set the current save file as the default."""
        if self._current_save:
            _set_default_save(self._current_save)
            name = os.path.basename(self._current_save)
            self.statusBar().showMessage(_tr("status.default_save_set", default="Default save set to: {name}", name=name))
            self._update_default_save_menu()

    def _clear_default_save(self):
        """Clear the default save setting."""
        _set_default_save(None)
        self.statusBar().showMessage(_tr("status.default_save_cleared", default="Default save cleared"))
        self._update_default_save_menu()

    def _flush_persistent_view_state(self):
        """Persist planner-style view state before the app shuts down."""
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.save_session_state()
            _save_room_priority_config(self._room_optimizer_view.get_room_config(), self._room_optimizer_view.save_path)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.save_session_state()
        if self._mutation_planner_view is not None:
            self._mutation_planner_view.save_session_state()
        if self._furniture_view is not None:
            self._furniture_view.save_session_state()
        if self._manual_scoring_view is not None:
            self._manual_scoring_view.save_session_state()
        _bp_view = getattr(self, "_breed_priority_view", None)
        if _bp_view is not None:
            try:
                _bp_view.save_session_state()
            except Exception:
                pass
        if self._trait_ratings is not None:
            self._trait_ratings.save()

    def closeEvent(self, event):
        try:
            _save_window_geometry(self.saveGeometry().toBase64().data().decode("ascii"))
        except Exception:
            pass
        self._flush_persistent_view_state()
        # Stop background workers so they don't fire signals into a
        # half-destroyed widget tree during shutdown.
        self._retire_worker(self._save_load_worker)
        self._save_load_worker = None
        self._retire_worker(self._cache_worker)
        self._cache_worker = None
        self._retire_worker(self._quick_refresh_worker)
        self._quick_refresh_worker = None
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # The startup prompt + What's New dialog used to fire from showEvent,
        # but that runs while the save is still loading — the splash screen
        # stays parked behind the modal guide because startup_save_load_finished
        # hasn't fired yet.  Defer to after the save load signal so the splash
        # closes first, then the prompt appears over the fully populated app.
        if not self._startup_dialogs_shown:
            self.startup_save_load_finished.connect(
                self._on_startup_save_load_finished_for_dialogs,
                Qt.UniqueConnection,
            )

    def _reset_ui_settings_to_defaults(self):
        """Reset pane sizes and planner inputs without touching save-file data."""
        confirm = QMessageBox.question(
            self,
            _tr("menu.settings.reset_ui_defaults.title"),
            _tr("menu.settings.reset_ui_defaults.body"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        for view in (
            self._room_optimizer_view,
            self._perfect_planner_view,
            self._furniture_view,
            self._mutation_planner_view,
        ):
            if view is not None and hasattr(view, "reset_to_defaults"):
                view.reset_to_defaults()

        _set_room_optimizer_auto_recalc(False)
        _save_optimizer_search_settings(_OPTIMIZER_SEARCH_DEFAULTS)
        if hasattr(self, "_room_optimizer_auto_recalc_action"):
            self._room_optimizer_auto_recalc_action.blockSignals(True)
            self._room_optimizer_auto_recalc_action.setChecked(False)
            self._room_optimizer_auto_recalc_action.blockSignals(False)
        if self._room_optimizer_view is not None and hasattr(self._room_optimizer_view, "set_auto_recalculate"):
            self._room_optimizer_view.set_auto_recalculate(False)

        _set_manual_scoring_auto_calc(True)
        if hasattr(self, "_manual_scoring_auto_calc_action"):
            self._manual_scoring_auto_calc_action.blockSignals(True)
            self._manual_scoring_auto_calc_action.setChecked(True)
            self._manual_scoring_auto_calc_action.blockSignals(False)
        msv = getattr(self, "_manual_scoring_view", None)
        if msv is not None and hasattr(msv, "set_auto_recalculate"):
            msv.set_auto_recalculate(True)

        self._apply_accessibility_preset("Default")

        _set_total_stats_display(False)
        _set_stat_icon_mode(False)
        if hasattr(self, "_source_model"):
            self._source_model.set_show_total_stats(False)
            self._source_model.set_show_stat_icons(False)
        if hasattr(self, "_total_stats_action"):
            self._total_stats_action.blockSignals(True)
            try:
                self._total_stats_action.setChecked(False)
            finally:
                self._total_stats_action.blockSignals(False)
        if hasattr(self, "_stat_icons_action"):
            self._stat_icons_action.blockSignals(True)
            try:
                self._stat_icons_action.setChecked(False)
            finally:
                self._stat_icons_action.blockSignals(False)
        if getattr(self, "_fight_club_layout_active", False):
            if self._current_room_key() == "__fight_club__":
                self._fight_club_prev_total_stats = False
                self._apply_fight_club_layout(True, force=True)
            else:
                self._apply_fight_club_layout(False, force=True)

        if hasattr(self, "_detail_splitter") and self._detail_splitter is not None:
            total = max(20, self._detail_splitter.height())
            detail_h = min(240, max(10, total - 10))
            self._detail_splitter.setSizes([max(10, total - detail_h), detail_h])
            _save_splitter_state(self._detail_splitter)

        if hasattr(self, "_sidebar_splitter") and self._sidebar_splitter is not None:
            total = max(20, self._sidebar_splitter.width())
            sidebar_w = min(self._base_sidebar_width, max(10, total - 10))
            self._sidebar_splitter.setSizes([sidebar_w, max(10, total - sidebar_w)])
            _save_splitter_state(self._sidebar_splitter)

        self.statusBar().showMessage(
            _tr("status.ui_settings_reset", default="UI settings reset to defaults")
        )

    def _toggle_room_optimizer_auto_recalc(self, checked: bool):
        _set_room_optimizer_auto_recalc(bool(checked))
        if self._room_optimizer_view is not None and hasattr(self._room_optimizer_view, "set_auto_recalculate"):
            self._room_optimizer_view.set_auto_recalculate(bool(checked))

    def _toggle_manual_scoring_auto_calc(self, checked: bool):
        _set_manual_scoring_auto_calc(bool(checked))
        if self._manual_scoring_view is not None and hasattr(self._manual_scoring_view, "set_auto_recalculate"):
            self._manual_scoring_view.set_auto_recalculate(bool(checked))

    def _toggle_lineage(self, checked: bool):
        self._show_lineage = checked
        for col in (COL_GEN_DEPTH, COL_SRC):
            self._table.setColumnHidden(col, not checked)
        self._source_model.set_show_lineage(checked)
        self._detail.set_show_lineage(checked)
        self._on_selection()   # refresh detail panel with updated flag

    def _open_file(self):
        saves   = find_save_files()
        start   = os.path.dirname(saves[0]) if saves else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self,
            _tr("dialog.open_save.title"),
            start,
            _tr("dialog.open_save.filter"),
        )
        if path:
            self.load_save(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_loading_overlay") and self._loading_overlay.isVisible():
            parent = self._loading_overlay.parentWidget()
            if parent:
                self._loading_overlay.setGeometry(0, 0, parent.width(), parent.height())

    def _export_cats(self):
        if not self._cats:
            QMessageBox.information(self, _tr("export.title", default="Export"), _tr("export.no_save", default="No save loaded."))
            return

        base = os.path.splitext(self._current_save)[0] if self._current_save else "cats"
        path, _ = QFileDialog.getSaveFileName(
            self, _tr("export.dialog_title", default="Export Cats"),
            base,
            "CSV (*.csv);;Excel (*.xlsx)"
        )
        if not path:
            return

        base_stat_headers  = ["Base " + s for s in STAT_NAMES]
        actual_stat_headers = ["Actual " + s for s in STAT_NAMES]
        headers = (
            ["Name", "Status", "Room", "Age", "Gender", "Sexuality", "Generation", "Class"]
            + base_stat_headers + ["Base Sum"]
            + actual_stat_headers + ["Actual Sum"]
            + ["Abilities", "Passive Abilities", "Mutations", "Disorders", "Defects",
               "Aggression", "Libido", "Inbreeding",
               "Pinned", "Blacklisted", "Must Breed", "Tags",
               "Lovers", "Haters", "Parent A", "Parent B"]
        )

        def _trait(val, field):
            if val is None:
                return ""
            return _trait_label_from_value(field, val)

        def _names(cats):
            return "; ".join(c.name for c in (cats or []) if c is not None)

        rows = []
        for cat in self._cats:
            base_vals   = [cat.base_stats.get(s, 0) for s in STAT_NAMES]
            actual_vals = [cat.total_stats.get(s, 0) for s in STAT_NAMES]
            row = (
                [
                    cat.name,
                    cat.status or "",
                    cat.room_display,
                    str(cat.age) if cat.age is not None else "",
                    cat.gender or "",
                    cat.sexuality or "",
                    str(cat.generation),
                    getattr(cat, "cat_class", "") or "",
                ]
                + [str(v) for v in base_vals] + [str(sum(base_vals))]
                + [str(v) for v in actual_vals] + [str(sum(actual_vals))]
                + [
                    "; ".join(cat.abilities or []),
                    "; ".join(getattr(cat, "passive_abilities", []) or []),
                    "; ".join(cat.mutations or []),
                    "; ".join(getattr(cat, "disorders", []) or []),
                    "; ".join(getattr(cat, "defects", []) or []),
                    _trait(cat.aggression, "aggression"),
                    _trait(cat.libido, "libido"),
                    _trait(cat.inbredness, "inbredness"),
                    "Yes" if getattr(cat, "is_pinned", False) else "No",
                    "Yes" if getattr(cat, "is_blacklisted", False) else "No",
                    "Yes" if getattr(cat, "must_breed", False) else "No",
                    "; ".join(_cat_tags(cat) or []),
                    _names(getattr(cat, "lovers", [])),
                    _names(getattr(cat, "haters", [])),
                    cat.parent_a.name if cat.parent_a else "",
                    cat.parent_b.name if cat.parent_b else "",
                ]
            )
            rows.append(row)

        ext = os.path.splitext(path)[1].lower()

        if ext == ".xlsx":
            try:
                import openpyxl
                from openpyxl.styles import Font
            except ImportError:
                QMessageBox.critical(self, _tr("export.title", default="Export"), "openpyxl is not installed. Install it with: pip install openpyxl")
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Cats"
            ws.append(headers)
            for cell in ws[1]:
                cell.font = Font(bold=True)
            for row in rows:
                ws.append(row)
            wb.save(path)
        else:
            if not path.lower().endswith(".csv"):
                path += ".csv"
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)

        QMessageBox.information(self, _tr("export.title", default="Export"), f"Exported {len(rows)} cats to:\n{path}")

    def _reload(self):
        if self._current_save:
            self.load_save(self._current_save)

    def _on_file_changed_raw(self, path: str):
        """Queue a debounced refresh so bursts of fileChanged events
        (the game writes the save in rapid succession) collapse into a
        single quick-refresh instead of spawning racing workers."""
        if path != self._current_save:
            return
        # Qt's QFileSystemWatcher stops watching a file after it's deleted
        # or replaced — Mewgenics writes saves atomically by writing to a
        # temp file then renaming over the original, which fires exactly
        # one fileChanged event before the watcher drops the subscription.
        # Re-add the path so subsequent in-game days still trigger refreshes.
        if path not in self._watcher.files():
            # Defer slightly: Qt sometimes fires fileChanged before the new
            # inode is fully materialised on NTFS, so addPath() fails silently.
            QTimer.singleShot(100, lambda p=path: self._rewatch_save(p))
        self._pending_changed_path = path
        # Restart the timer on every event so the debounce window
        # resets after the latest burst write.
        self._file_change_timer.start()

    def _on_file_changed_debounced(self):
        path = self._pending_changed_path
        self._pending_changed_path = None
        if path is None or path != self._current_save:
            return
        # If cats are already loaded and no full reload is running, try the fast path.
        if self._cats and self._save_load_worker is None:
            self._start_quick_room_refresh()
        else:
            self._reload()

    def _rewatch_save(self, path: str):
        """Re-subscribe the file watcher to *path* after the game rewrites it."""
        if path != self._current_save:
            return
        if not os.path.isfile(path):
            # File not materialised yet — try again shortly.
            QTimer.singleShot(100, lambda p=path: self._rewatch_save(p))
            return
        if path in self._watcher.files():
            return
        self._watcher.addPath(path)

    def _start_quick_room_refresh(self):
        # Retire the previous worker so it doesn't accumulate as a
        # zombie QThread.  We also bump the generation token so the old
        # worker's queued room_patch signal is recognised as stale by
        # `_on_room_patch` and silently dropped.
        self._retire_worker(self._quick_refresh_worker)
        self._quick_refresh_worker = None
        self._quick_refresh_generation += 1
        gen = self._quick_refresh_generation
        expected = {c.db_key for c in self._cats}
        w = QuickRoomRefreshWorker(self._current_save, expected, generation=gen, parent=self)
        w.room_patch.connect(self._on_room_patch)
        w.needs_full_reload.connect(self._on_quick_refresh_needs_full_reload)
        self._quick_refresh_worker = w
        w.start()

    def _on_quick_refresh_needs_full_reload(self, generation: int):
        """Quick refresh fell back — do a full reload, but only if this
        signal came from the current worker (stale ones are ignored)."""
        if generation != self._quick_refresh_generation:
            return
        self._reload()

    def _on_room_patch(self, generation: int, patch: dict):
        # Drop signals from superseded workers.  Without this guard, a
        # stale worker's room_patch can fire after the next refresh has
        # already mutated `self._cats` or `_rebuild_room_buttons()` has
        # deleteLater()'d its widgets — either path risks a crash.
        if generation != self._quick_refresh_generation:
            return
        self._quick_refresh_worker = None
        # Wrap the whole body in try/except: unlike `_on_save_loaded`,
        # this slot used to run bare, so any Qt-object-lifetime or view
        # bookkeeping error propagated to the event loop and aborted the
        # app.  On failure, log to the status bar and fall back to a
        # full reload — the user-visible symptom is a brief flicker
        # instead of a crash.
        try:
            # Safe to mutate cat.room / cat.status here even if a
            # BreedingCacheWorker is running — the worker snapshots the
            # alive list at construction time and never reads cat.status
            # from the live objects.
            changed = self._source_model.apply_room_patch(patch)
            # Refresh the cache's cat-by-key index so it sees updated
            # rooms/statuses without a full rebuild.
            if changed and self._breeding_cache is not None:
                self._breeding_cache.refresh_cat_index(self._cats)
            self._rebuild_room_buttons(self._cats)
            self._refresh_filter_button_counts()
            self._bump_cats_generation()
            if self._furniture_view is not None:
                self._furniture_view.set_context(self._cats, self._furniture, self._furniture_data, available_rooms=self._available_house_rooms)
                self._view_generation["furniture"] = self._cats_generation
            if self._tree_view is not None and self._tree_view.isVisible():
                self._set_view_cats_if_needed("tree", self._tree_view, self._cats)
            if self._safe_breeding_view is not None and self._safe_breeding_view.isVisible():
                self._set_view_cats_if_needed("safe_breeding", self._safe_breeding_view, self._cats)
            if self._breeding_partners_view is not None and self._breeding_partners_view.isVisible():
                self._set_view_cats_if_needed("breeding_partners", self._breeding_partners_view, self._cats)
            if self._room_optimizer_view is not None and self._room_optimizer_view.isVisible():
                self._set_view_cats_if_needed("room_optimizer", self._room_optimizer_view, self._cats)
            if self._perfect_planner_view is not None and self._perfect_planner_view.isVisible():
                self._set_view_cats_if_needed("perfect_planner", self._perfect_planner_view, self._cats)
            if self._calibration_view is not None and self._calibration_view.isVisible():
                self._calibration_view.set_context(self._current_save, self._cats)
                self._view_generation["calibration"] = self._cats_generation
            self.statusBar().showMessage(_tr("status.rooms_refreshed", default="Room locations updated."))
        except Exception as exc:  # noqa: BLE001 — last line of defence before the event loop
            self.statusBar().showMessage(
                _tr("status.quick_refresh_failed",
                    default="Quick refresh failed ({error}) — reloading save.",
                    error=repr(exc))
            )
            # Full reload regenerates all widgets from scratch, clearing
            # any dangling references that caused the failure.
            QTimer.singleShot(0, self._reload)

    def _open_tree_browser(self):
        self._push_nav_history()
        _save_current_view("tree")
        self._show_tree_view()
        rows = list({
            self._proxy_model.mapToSource(idx).row()
            for idx in self._table.selectionModel().selectedRows()
        })
        cats = [c for r in rows[:1] if (c := self._source_model.cat_at(r)) is not None]
        if cats and self._tree_view is not None:
            self._tree_view.select_cat(cats[0])

    def _open_tree_for_cat(self, cat: Cat):
        if cat is None:
            return
        self._navigate_to_cat(cat.db_key)
        self._open_tree_browser()

    def _open_safe_breeding_view(self, quality: Optional[bool] = None):
        self._push_nav_history()
        if quality is not None:
            self._safe_breeding_quality_mode = bool(quality)
        _save_current_view("safe_breeding")
        self._show_safe_breeding_view()
        rows = list({
            self._proxy_model.mapToSource(idx).row()
            for idx in self._table.selectionModel().selectedRows()
        })
        cats = [c for r in rows[:1] if (c := self._source_model.cat_at(r)) is not None]
        if cats and self._safe_breeding_view is not None:
            self._safe_breeding_view.select_cat(cats[0])

    def _open_safe_breeding_for_cat(self, cat: Cat, quality: Optional[bool] = None):
        if cat is None:
            return
        self._navigate_to_cat(cat.db_key)
        self._open_safe_breeding_view(quality=quality)

    def _open_breeding_partners_view(self):
        self._push_nav_history()
        _save_current_view("breeding_partners")
        self._show_breeding_partners_view()

    def _open_perfect_planner_for_cat(self, cat: Cat):
        if cat is None:
            return
        self._navigate_to_cat(cat.db_key)
        self._open_perfect_planner_view()

    def _open_room_optimizer(self):
        self._push_nav_history()
        _save_current_view("room_optimizer")
        self._show_room_optimizer_view()

    def _open_perfect_planner_view(self):
        self._push_nav_history()
        _save_current_view("perfect_planner")
        self._show_perfect_planner_view()

    def _open_calibration_view(self):
        self._push_nav_history()
        _save_current_view("calibration")
        self._show_calibration_view()

    def _open_mutation_planner_view(self):
        self._push_nav_history()
        _save_current_view("mutation_planner")
        self._show_mutation_planner_view()

    def _open_furniture_view(self):
        self._push_nav_history()
        _save_current_view("furniture")
        self._show_furniture_view()

    def _open_manual_scoring_view(self):
        self._push_nav_history()
        _save_current_view("manual_scoring")
        self._show_manual_scoring_view()

    def _show_manual_scoring_view(self):
        self._ensure_manual_scoring_view()
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        if hasattr(self, "_tree_view") and self._tree_view is not None:
            self._tree_view.hide()
        if hasattr(self, "_safe_breeding_view") and self._safe_breeding_view is not None:
            self._safe_breeding_view.hide()
        if hasattr(self, "_breeding_partners_view") and self._breeding_partners_view is not None:
            self._breeding_partners_view.hide()
        if hasattr(self, "_room_optimizer_view") and self._room_optimizer_view is not None:
            self._room_optimizer_view.hide()
        if hasattr(self, "_perfect_planner_view") and self._perfect_planner_view is not None:
            self._perfect_planner_view.hide()
        if hasattr(self, "_calibration_view") and self._calibration_view is not None:
            self._calibration_view.hide()
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.hide()
        if hasattr(self, "_furniture_view") and self._furniture_view is not None:
            self._furniture_view.hide()
        if hasattr(self, "_breed_priority_view") and self._breed_priority_view is not None:
            self._breed_priority_view.hide()
        if self._manual_scoring_view is not None:
            self._set_view_cats_if_needed("manual_scoring", self._manual_scoring_view, self._cats)
            self._manual_scoring_view.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(False)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(False)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(False)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(False)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(False)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(False)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(False)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(False)
        if hasattr(self, "_btn_manual_scoring"):
            self._btn_manual_scoring.setChecked(True)
        if hasattr(self, "_btn_breed_priority"):
            self._btn_breed_priority.setChecked(False)

    def _open_breed_priority_view(self):
        self._push_nav_history()
        _save_current_view("breed_priority")
        self._show_breed_priority_view()

    def _show_breed_priority_view(self):
        self._ensure_breed_priority_view()
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        for view_attr in ("_tree_view", "_safe_breeding_view", "_breeding_partners_view",
                          "_room_optimizer_view", "_perfect_planner_view", "_calibration_view",
                          "_mutation_planner_view", "_furniture_view", "_manual_scoring_view"):
            v = getattr(self, view_attr, None)
            if v is not None:
                v.hide()
        if self._breed_priority_view is not None:
            self._set_view_cats_if_needed("breed_priority", self._breed_priority_view, self._cats)
            self._breed_priority_view.show()
        for btn_attr in ("_btn_tree_view", "_btn_safe_breeding_view", "_btn_breeding_partners_view",
                         "_btn_room_optimizer", "_btn_perfect_planner", "_btn_calibration",
                         "_btn_mutation_planner", "_btn_furniture_view", "_btn_manual_scoring"):
            btn = getattr(self, btn_attr, None)
            if btn is not None:
                btn.setChecked(False)
        if hasattr(self, "_btn_breed_priority"):
            self._btn_breed_priority.setChecked(True)

    def _restore_current_view(self):
        """Restore the last-used view after a save is loaded."""
        view = _load_current_view()
        _restore_map = {
            "tree":               self._show_tree_view,
            "fight_club":         (lambda: self._filter(None, self._btn_all) if hasattr(self, "_btn_all") else self._show_table_view()),
            "safe_breeding":      self._show_safe_breeding_view,
            "breeding_partners":  self._show_breeding_partners_view,
            "room_optimizer":     self._show_room_optimizer_view,
            "perfect_planner":    self._show_perfect_planner_view,
            "calibration":        self._show_calibration_view,
            "mutation_planner":   self._show_mutation_planner_view,
            "furniture":          self._show_furniture_view,
            "manual_scoring":     self._show_manual_scoring_view,
            "breed_priority":     self._show_breed_priority_view,
        }
        fn = _restore_map.get(view)
        if fn:
            fn()

    def _toggle_single_cat_pin(self, cat: Cat):
        if cat is None:
            return
        cat.is_pinned = not cat.is_pinned
        self._emit_bulk_toggle_refresh()
        self.statusBar().showMessage(_tr("bulk.status.toggled_pin", default="Toggled pin for 1 selected cat", count=1))

    def _toggle_single_cat_must_breed(self, cat: Cat):
        if cat is None:
            return
        cat.must_breed = not cat.must_breed
        if cat.must_breed:
            cat.is_blacklisted = False
        self._emit_bulk_toggle_refresh()
        self.statusBar().showMessage(_tr("bulk.status.toggled_must_breed", default="Toggled must breed for 1 selected cat", count=1))

    def _toggle_single_cat_blacklist(self, cat: Cat):
        if cat is None:
            return
        cat.is_blacklisted = not cat.is_blacklisted
        if cat.is_blacklisted:
            cat.must_breed = False
        self._emit_bulk_toggle_refresh()
        self.statusBar().showMessage(_tr("bulk.status.toggled_breeding_block", default="Toggled breeding block for 1 selected cat", count=1))

    # ── UI zoom ───────────────────────────────────────────────────────────

    def _scaled(self, value: int) -> int:
        return max(1, round(value * (self._zoom_percent / 100.0)))

    def _update_zoom_info_action(self):
        if hasattr(self, "_zoom_info_action"):
            self._zoom_info_action.setText(_tr("menu.settings.zoom_info", percent=self._zoom_percent))

    def _set_zoom(self, percent: int):
        clamped = max(_ZOOM_MIN, min(_ZOOM_MAX, int(percent)))
        if clamped == self._zoom_percent:
            return
        self._zoom_percent = clamped
        _set_zoom_percent(clamped)
        self._apply_zoom()
        self._update_zoom_info_action()
        self.statusBar().showMessage(_tr("status.zoom_changed", default="UI zoom set to {percent}%", percent=self._zoom_percent))

    def _change_zoom(self, direction: int):
        self._set_zoom(self._zoom_percent + (direction * _ZOOM_STEP))

    def _reset_zoom(self):
        self._set_zoom(100)

    def _change_font_size(self, direction: int):
        self._set_font_size_offset(self._font_size_offset + direction)

    def _set_font_size_offset(self, offset: int):
        clamped = max(-6, min(12, offset))
        if clamped == self._font_size_offset:
            return
        self._font_size_offset = clamped
        _set_font_size_offset_config(clamped)
        self._apply_zoom()
        self._update_font_size_info_action()
        label = _font_size_offset_label(clamped)
        self.statusBar().showMessage(_tr("status.font_size_offset", default="Font size offset: {label}", label=label))

    def _update_font_size_info_action(self):
        if hasattr(self, "_font_size_info_action"):
            off = self._font_size_offset
            label = _font_size_offset_label(off)
            self._font_size_info_action.setText(_tr("menu.settings.font_size_info", label=label))

    def _apply_zoom(self):
        app = QApplication.instance()
        font = QFont(self._base_font)
        base_pt = self._base_font.pointSizeF()
        if base_pt > 0:
            zoomed_pt = base_pt * (self._zoom_percent / 100.0) + self._font_size_offset
            font.setPointSizeF(max(_ACCESSIBILITY_MIN_FONT_PT, zoomed_pt))
        elif self._base_font.pixelSize() > 0:
            font.setPixelSize(max(_ACCESSIBILITY_MIN_FONT_PX, self._scaled(self._base_font.pixelSize()) + self._font_size_offset))
        app.setFont(font)

        if hasattr(self, "_sidebar"):
            self._sidebar.setFixedWidth(self._scaled(self._base_sidebar_width))
        if hasattr(self, "_header"):
            self._header.setFixedHeight(self._scaled(self._base_header_height))
        if hasattr(self, "_search"):
            self._search.setFixedWidth(self._scaled(self._base_search_width))
        if hasattr(self, "_table"):
            for col, width in self._base_col_widths.items():
                self._table.setColumnWidth(col, self._scaled(width))
            # Row height depends on visual vs compact mode. Re-apply the
            # mode so widths/height stay correct after a zoom change.
            if getattr(self, "_source_model", None) is not None and self._source_model.visual_mode():
                self._apply_roster_visual_mode(True)
            else:
                self._table.verticalHeader().setDefaultSectionSize(self._scaled(24))

        # Scale all hardcoded stylesheet font-size values across the whole window.
        # 1pt ≈ 1.33px; round to nearest integer pixel.
        offset_px = round(self._font_size_offset * 1.333)
        _apply_font_offset_to_tree(self, offset_px)



def _ensure_gpak_path_interactive(parent: Optional[QWidget] = None):
    if _GPAK_PATH:
        return

    start_dir = _gpak_search_start_dir()
    chosen_dir = QFileDialog.getExistingDirectory(
        parent,
        "Select Mewgenics Install Folder",
        start_dir,
    )
    if not chosen_dir:
        return

    gpak_path = os.path.join(chosen_dir, "resources.gpak")
    if os.path.exists(gpak_path):
        _set_gpak_path(gpak_path)
        return

    QMessageBox.warning(
        parent,
        "resources.gpak not found",
        "The selected folder does not contain resources.gpak. "
        "Choose the Mewgenics install directory that contains that file.",
    )
