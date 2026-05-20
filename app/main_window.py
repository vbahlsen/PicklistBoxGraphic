"""
MainWindow: Top-level application window.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QGroupBox, QScrollArea, QFrame, QSplitter, QSizePolicy,
    QMessageBox, QApplication,
)

from .data_manager import (
    DataManager,
    STATUS_SCANNED, STATUS_WARNING, STATUS_PICKLIST,
)
from .box_grid import BoxGridWidget
from .import_dialogs import ScanFileImportDialog, PicklistImportDialog
from .styles import MAIN_QSS


_MODE_BOX  = "BOX"
_MODE_TUBE = "TUBE"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dm = DataManager()
        self._mode        = _MODE_BOX
        self._current_box: str | None = None
        self._box_history: list[str] = []   # ordered list of visited boxes

        self.setWindowTitle("Picklist Box Scanner")
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(MAIN_QSS)

        self._build_ui()
        self._update_scan_input_state()

    # ══════════════════════════════════════════════════════════════════════════
    # UI Construction
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ── Top toolbar ────────────────────────────────────────────────────────
        toolbar = self._build_toolbar()
        root.addLayout(toolbar)

        # ── Status bar (scan files / picklist loaded) ──────────────────────────
        self._lbl_status = QLabel("No files loaded.")
        self._lbl_status.setStyleSheet("color: #607D8B; font-size: 8pt;")
        root.addWidget(self._lbl_status)

        # ── Main splitter: sidebar | right panel ───────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)

        # Left: box history sidebar
        sidebar = self._build_sidebar()
        splitter.addWidget(sidebar)

        # Right: grid + scan + metadata
        right = self._build_right_panel()
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 880])

        root.addWidget(splitter, 1)

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        btn_scan = QPushButton("⬛  Scan New Box")
        btn_scan.setObjectName("btn_scan_box")
        btn_scan.setToolTip("Start scanning a new box (shortcut: F2)")
        btn_scan.clicked.connect(self._on_scan_new_box)
        self._btn_scan_new_box = btn_scan

        btn_import_scan = QPushButton("📂  Import Scan Files")
        btn_import_scan.setObjectName("btn_import")
        btn_import_scan.clicked.connect(self._on_import_scan_files)

        btn_import_pick = QPushButton("📋  Import Picklist")
        btn_import_pick.setObjectName("btn_import")
        btn_import_pick.clicked.connect(self._on_import_picklist)

        btn_reset = QPushButton("✖  Reset All")
        btn_reset.setObjectName("btn_reset")
        btn_reset.setToolTip("Clear all loaded data and scan history")
        btn_reset.clicked.connect(self._on_reset)

        row.addWidget(btn_import_scan)
        row.addWidget(btn_import_pick)
        row.addStretch()
        row.addWidget(btn_scan)
        row.addWidget(btn_reset)
        return row

    def _build_sidebar(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(220)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(4)

        lbl = QLabel("Box History")
        lbl.setStyleSheet(
            "font-weight: bold; font-size: 10pt; color: #37474F; padding: 4px 0;"
        )
        lay.addWidget(lbl)

        self._history_list = QListWidget()
        self._history_list.currentRowChanged.connect(self._on_history_selected)
        lay.addWidget(self._history_list, 1)

        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # ── Box info label ─────────────────────────────────────────────────────
        self._lbl_box_title = QLabel("No box loaded")
        self._lbl_box_title.setStyleSheet(
            "font-size: 14pt; font-weight: bold; color: #37474F;"
        )
        self._lbl_progress = QLabel("")
        self._lbl_progress.setStyleSheet("font-size: 9pt; color: #607D8B;")

        info_row = QHBoxLayout()
        info_row.addWidget(self._lbl_box_title)
        info_row.addSpacing(20)
        info_row.addWidget(self._lbl_progress)
        info_row.addStretch()
        lay.addLayout(info_row)

        # ── Banner ─────────────────────────────────────────────────────────────
        self._banner = QLabel("")
        self._banner.setObjectName("banner_label")
        self._banner.setProperty("severity", "info")
        self._banner.setVisible(False)
        self._banner.setWordWrap(True)
        lay.addWidget(self._banner)

        # ── Grid scroll area ───────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._grid_widget = BoxGridWidget()
        scroll.setWidget(self._grid_widget)
        lay.addWidget(scroll, 1)

        # ── Scan input panel ───────────────────────────────────────────────────
        scan_grp = QGroupBox()
        scan_grp.setTitle("Scan Input")
        scan_lay = QHBoxLayout(scan_grp)
        scan_lay.setSpacing(8)

        self._lbl_mode = QLabel("Scan Box ID:")
        self._lbl_mode.setObjectName("mode_label")
        self._lbl_mode.setFixedWidth(130)

        self._scan_input = QLineEdit()
        self._scan_input.setPlaceholderText("Scan or type here, then press Enter…")
        self._scan_input.returnPressed.connect(self._on_scan_submitted)

        btn_submit = QPushButton("Submit")
        btn_submit.setFixedWidth(80)
        btn_submit.clicked.connect(self._on_scan_submitted)

        scan_lay.addWidget(self._lbl_mode)
        scan_lay.addWidget(self._scan_input, 1)
        scan_lay.addWidget(btn_submit)
        lay.addWidget(scan_grp)

        # ── Metadata panel ─────────────────────────────────────────────────────
        meta_grp = QGroupBox("Last Scanned Tube")
        self._meta_layout = QVBoxLayout(meta_grp)
        self._meta_layout.setSpacing(2)
        self._lbl_meta_empty = QLabel("No tube scanned yet.")
        self._lbl_meta_empty.setStyleSheet("color: #9E9E9E; font-style: italic;")
        self._meta_layout.addWidget(self._lbl_meta_empty)
        self._meta_widgets: list[QWidget] = []
        lay.addWidget(meta_grp)

        return w

    # ══════════════════════════════════════════════════════════════════════════
    # Toolbar actions
    # ══════════════════════════════════════════════════════════════════════════

    def _on_import_scan_files(self):
        dlg = ScanFileImportDialog(self.dm, self)
        if dlg.exec():
            self._update_status_bar()

    def _on_import_picklist(self):
        dlg = PicklistImportDialog(self.dm, self)
        if dlg.exec():
            self._update_status_bar()

    def _on_scan_new_box(self):
        """Switch to BOX scanning mode and focus the input field."""
        self._set_mode(_MODE_BOX)
        self._scan_input.clear()
        self._scan_input.setFocus()

    def _on_reset(self):
        reply = QMessageBox.question(
            self,
            "Reset All",
            "This will clear all loaded files and scan history.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.dm.reset()
            self._current_box = None
            self._box_history.clear()
            self._history_list.clear()
            self._grid_widget.clear_grid()
            self._lbl_box_title.setText("No box loaded")
            self._lbl_progress.setText("")
            self._clear_metadata()
            self._hide_banner()
            self._update_status_bar()
            self._set_mode(_MODE_BOX)

    # ══════════════════════════════════════════════════════════════════════════
    # Scan input handler
    # ══════════════════════════════════════════════════════════════════════════

    def _on_scan_submitted(self):
        value = self._scan_input.text().strip()
        if not value:
            return
        self._scan_input.clear()

        if self._mode == _MODE_BOX:
            self._load_box(value)
        else:
            self._scan_tube(value)

    def _load_box(self, box_id: str):
        if not self.dm.box_inventory:
            self._show_banner("No scan files loaded. Import scan files first.", "error")
            return

        if box_id not in self.dm.box_inventory:
            self._show_banner(
                f"Box '{box_id}' not found in scan files.", "error"
            )
            return

        self._current_box = box_id
        self._hide_banner()

        # Add to history if not already there
        if box_id not in self._box_history:
            self._box_history.append(box_id)
            self._history_list.addItem(box_id)

        # Render grid
        grid_data = self.dm.get_box_grid(box_id)
        rows, cols = self.dm.get_box_layout(box_id)
        self._grid_widget.load_box(box_id, grid_data, rows, cols, read_only=False)

        self._lbl_box_title.setText(f"Box: {box_id}")
        self._update_progress()
        self._set_mode(_MODE_TUBE)
        self._scan_input.setFocus()

        # Sync history selection
        items = self._history_list.findItems(box_id, Qt.MatchFlag.MatchExactly)
        if items:
            self._history_list.blockSignals(True)
            self._history_list.setCurrentItem(items[0])
            self._history_list.blockSignals(False)

    def _scan_tube(self, tube_id: str):
        if self._current_box is None:
            self._show_banner("No box loaded. Scan a box ID first.", "error")
            return

        result = self.dm.record_scan(self._current_box, tube_id)
        status = result.get("status", "")

        if status == "not_in_box":
            self._show_banner(
                f"⚠  Tube '{tube_id}' is not in box {self._current_box}.", "error"
            )
            return

        pos = result.get("position", "")
        if status == STATUS_SCANNED:
            self._grid_widget.mark_scanned(pos, STATUS_SCANNED)
            self._show_metadata(result)
            self._hide_banner()
        elif status == STATUS_WARNING:
            self._grid_widget.mark_scanned(pos, STATUS_WARNING)
            self._show_banner(
                f"⚠  Tube '{tube_id}' was scanned but is NOT on the picklist.", "warning"
            )

        self._update_progress()
        self._update_history_item(self._current_box)
        self._scan_input.setFocus()

        # Check box completion
        if self.dm.is_box_complete(self._current_box):
            self._on_box_complete(self._current_box)

    # ══════════════════════════════════════════════════════════════════════════
    # History sidebar
    # ══════════════════════════════════════════════════════════════════════════

    def _on_history_selected(self, row: int):
        if row < 0 or row >= len(self._box_history):
            return
        box_id = self._box_history[row]
        if box_id == self._current_box:
            return  # already loaded, do nothing

        # Show in read-only review mode
        grid_data = self.dm.get_box_grid(box_id)
        rows, cols = self.dm.get_box_layout(box_id)
        self._grid_widget.load_box(box_id, grid_data, rows, cols, read_only=True)

        scanned, total = self.dm.picklist_count_for_box(box_id)
        self._lbl_box_title.setText(f"Box: {box_id}  (review)")
        self._lbl_progress.setText(f"{scanned}/{total} picklist tubes scanned")
        self._hide_banner()

    def _update_history_item(self, box_id: str):
        """Refresh the label of a history list entry."""
        items = self._history_list.findItems(box_id, Qt.MatchFlag.MatchExactly)
        for item in items:
            scanned, total = self.dm.picklist_count_for_box(box_id)
            done = scanned >= total > 0
            marker = " ✓" if done else f"  {scanned}/{total}"
            item.setText(f"{box_id}{marker}")

    # ══════════════════════════════════════════════════════════════════════════
    # Box completion
    # ══════════════════════════════════════════════════════════════════════════

    def _on_box_complete(self, box_id: str):
        scanned, total = self.dm.picklist_count_for_box(box_id)
        self._update_history_item(box_id)
        self._show_banner(
            f"✅  All {total} picklist tube(s) in box '{box_id}' have been scanned!  "
            "Click 'Scan New Box' or scan the next box ID.",
            "success",
        )
        self._set_mode(_MODE_BOX)
        self._scan_input.setFocus()

    # ══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _set_mode(self, mode: str):
        self._mode = mode
        if mode == _MODE_BOX:
            self._lbl_mode.setText("Scan Box ID:")
            self._lbl_mode.setProperty("mode", "BOX")
        else:
            self._lbl_mode.setText("Scan Tube ID:")
            self._lbl_mode.setProperty("mode", "TUBE")
        # Force style refresh for dynamic property
        self._lbl_mode.style().unpolish(self._lbl_mode)
        self._lbl_mode.style().polish(self._lbl_mode)
        self._update_scan_input_state()

    def _update_scan_input_state(self):
        has_scan_data = bool(self.dm.box_inventory)
        self._scan_input.setEnabled(True)  # always allow scanning

    def _update_progress(self):
        if self._current_box is None:
            return
        scanned, total = self.dm.picklist_count_for_box(self._current_box)
        if total == 0:
            self._lbl_progress.setText("No picklist tubes in this box")
        else:
            self._lbl_progress.setText(f"{scanned}/{total} picklist tubes scanned")

    def _update_status_bar(self):
        boxes   = len(self.dm.box_inventory)
        tubes   = sum(len(v) for v in self.dm.box_inventory.values())
        pick    = len(self.dm.picklist)
        parts   = []
        if boxes:
            parts.append(f"Scan files: {boxes} box(es), {tubes} tube(s)")
        else:
            parts.append("No scan files loaded")
        if pick:
            parts.append(f"Picklist: {pick} tube(s)")
        else:
            parts.append("No picklist loaded")
        self._lbl_status.setText("  |  ".join(parts))

    def _show_banner(self, message: str, severity: str):
        self._banner.setText(message)
        self._banner.setProperty("severity", severity)
        self._banner.style().unpolish(self._banner)
        self._banner.style().polish(self._banner)
        self._banner.setVisible(True)

    def _hide_banner(self):
        self._banner.setVisible(False)

    def _show_metadata(self, result: dict):
        self._clear_metadata()
        self._lbl_meta_empty.setVisible(False)

        def _add_row(key: str, value: str, is_title: bool = False):
            if is_title:
                lbl = QLabel(value)
                lbl.setObjectName("meta_title")
                lbl.setWordWrap(True)
            else:
                lbl_k = QLabel(f"{key}:")
                lbl_k.setObjectName("meta_key")
                lbl_v = QLabel(value or "—")
                lbl_v.setObjectName("meta_value")
                lbl_v.setWordWrap(True)
                row_w = QWidget()
                row_lay = QHBoxLayout(row_w)
                row_lay.setContentsMargins(0, 0, 0, 0)
                row_lay.setSpacing(8)
                row_lay.addWidget(lbl_k, 0)
                row_lay.addWidget(lbl_v, 1)
                self._meta_layout.addWidget(row_w)
                self._meta_widgets.append(row_w)
                return
            self._meta_layout.addWidget(lbl)
            self._meta_widgets.append(lbl)

        # Case ID gets top billing
        case_id = result.get("case_id", "")
        if case_id:
            _add_row("", f"Case: {case_id}", is_title=True)

        _add_row("Tube ID", result.get("tube_id", ""))
        _add_row("Position", result.get("position", ""))

        for key, val in result.get("metadata", {}).items():
            _add_row(key, val)

    def _clear_metadata(self):
        for w in self._meta_widgets:
            self._meta_layout.removeWidget(w)
            w.deleteLater()
        self._meta_widgets.clear()
        self._lbl_meta_empty.setVisible(True)

    # ══════════════════════════════════════════════════════════════════════════
    # Keyboard shortcut
    # ══════════════════════════════════════════════════════════════════════════

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F2:
            self._on_scan_new_box()
        else:
            super().keyPressEvent(event)
