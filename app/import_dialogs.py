"""
Import dialogs:
  - ScanFileImportDialog  : upload one or more CSV/TXT scan files
  - PicklistImportDialog  : upload a single picklist file
"""

from __future__ import annotations
from typing import Any

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QCheckBox, QComboBox, QListWidget,
    QListWidgetItem, QFileDialog, QTableWidget, QTableWidgetItem,
    QGroupBox, QScrollArea, QWidget, QAbstractItemView,
    QDialogButtonBox, QMessageBox, QFrame, QSizePolicy,
)

from .data_manager import DataManager, ScanFileOptions, PicklistOptions


PREVIEW_ROWS = 6
_NONE_LABEL = "— none —"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _detect_delimiter(filepath: str) -> str:
    """Simple heuristic: count commas vs tabs in the first line."""
    try:
        with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
            first = f.readline()
        tabs   = first.count("\t")
        commas = first.count(",")
        semis  = first.count(";")
        pipes  = first.count("|")
        best = max(tabs, commas, semis, pipes)
        if best == 0:
            return ","
        return {tabs: "\t", commas: ",", semis: ";", pipes: "|"}[best]
    except Exception:
        return ","


def _load_preview(filepath: str, delimiter: str, has_headers: bool) -> pd.DataFrame:
    try:
        df = pd.read_csv(
            filepath,
            sep=delimiter,
            header=0 if has_headers else None,
            dtype=str,
            keep_default_na=False,
            nrows=PREVIEW_ROWS,
            engine="python",
        )
        if not has_headers:
            df.columns = [str(i) for i in range(len(df.columns))]
        return df
    except Exception:
        return pd.DataFrame()


def _populate_preview_table(table: QTableWidget, df: pd.DataFrame):
    table.clear()
    if df.empty:
        table.setRowCount(0)
        table.setColumnCount(0)
        return
    table.setRowCount(len(df))
    table.setColumnCount(len(df.columns))
    table.setHorizontalHeaderLabels([str(c) for c in df.columns])
    for r, (_, row) in enumerate(df.iterrows()):
        for c, val in enumerate(row):
            item = QTableWidgetItem(str(val))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()


def _col_choices(df: pd.DataFrame) -> list[str]:
    return [str(c) for c in df.columns]


def _guess_col(cols: list[str], *prefixes: str) -> str | None:
    """Return the first column name starting with any prefix (case-insensitive)."""
    for prefix in prefixes:
        pfx_l = prefix.lower()
        for col in cols:
            if col.lower().startswith(pfx_l):
                return col
    return None


# ── ScanFileImportDialog ───────────────────────────────────────────────────────

class ScanFileImportDialog(QDialog):
    """Dialog for importing one or more scan (inventory) files."""

    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.dm = data_manager
        self.setWindowTitle("Import Scan Files")
        self.setMinimumWidth(760)
        self.setMinimumHeight(560)

        self._files: list[str] = []
        self._current_df: pd.DataFrame = pd.DataFrame()
        self._delimiter: str = ","

        self._build_ui()

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── File picker row ────────────────────────────────────────────────────
        file_row = QHBoxLayout()
        self._file_label = QLabel("No files selected")
        self._file_label.setWordWrap(True)
        btn_browse = QPushButton("Browse…")
        btn_browse.setFixedWidth(90)
        btn_browse.clicked.connect(self._browse_files)
        file_row.addWidget(self._file_label, 1)
        file_row.addWidget(btn_browse)
        root.addLayout(file_row)

        # ── Options row ────────────────────────────────────────────────────────
        opts_row = QHBoxLayout()
        self._chk_headers = QCheckBox("File has headers")
        self._chk_headers.setChecked(True)
        self._chk_headers.toggled.connect(self._refresh_preview)

        self._chk_split = QCheckBox("Row and column in separate columns")
        self._chk_split.toggled.connect(self._toggle_split)

        opts_row.addWidget(self._chk_headers)
        opts_row.addSpacing(20)
        opts_row.addWidget(self._chk_split)
        opts_row.addStretch()
        root.addLayout(opts_row)

        # ── Preview table ──────────────────────────────────────────────────────
        grp_prev = QGroupBox("File preview (first rows)")
        prev_lay = QVBoxLayout(grp_prev)
        self._preview_table = QTableWidget()
        self._preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._preview_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._preview_table.setFixedHeight(140)
        prev_lay.addWidget(self._preview_table)
        root.addWidget(grp_prev)

        # ── Column mapping ─────────────────────────────────────────────────────
        grp_map = QGroupBox("Column mapping")
        form = QFormLayout(grp_map)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # combined position
        self._cmb_position = QComboBox()
        self._lbl_position = QLabel("Position column  (e.g. A1):")
        form.addRow(self._lbl_position, self._cmb_position)

        # split row col
        self._cmb_row_col = QComboBox()
        self._lbl_row_col = QLabel("Row column  (e.g. A):")
        self._cmb_col_col = QComboBox()
        self._lbl_col_col = QLabel("Column number col  (e.g. 1):")
        form.addRow(self._lbl_row_col, self._cmb_row_col)
        form.addRow(self._lbl_col_col, self._cmb_col_col)

        self._cmb_tube_id = QComboBox()
        form.addRow("Tube ID column:", self._cmb_tube_id)

        self._cmb_box_id = QComboBox()
        form.addRow("Box ID column:", self._cmb_box_id)

        root.addWidget(grp_map)

        # ── File list (multiple files loaded) ──────────────────────────────────
        self._file_list = QListWidget()
        self._file_list.setFixedHeight(60)
        self._file_list.currentRowChanged.connect(self._file_selected)
        root.addWidget(QLabel("Loaded files (click to preview):"))
        root.addWidget(self._file_list)

        # ── Buttons ────────────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

        self._toggle_split(False)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _browse_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select scan files",
            "",
            "Data files (*.csv *.txt *.tsv *.dat);;All files (*)",
        )
        if not paths:
            return
        for p in paths:
            if p not in self._files:
                self._files.append(p)
                short = p.split("\\")[-1].split("/")[-1]
                self._file_list.addItem(short)

        label_text = f"{len(self._files)} file(s) selected"
        self._file_label.setText(label_text)

        # Auto-select last added
        self._file_list.setCurrentRow(len(self._files) - 1)

    def _file_selected(self, idx: int):
        if idx < 0 or idx >= len(self._files):
            return
        self._delimiter = _detect_delimiter(self._files[idx])
        self._refresh_preview()

    def _refresh_preview(self):
        idx = self._file_list.currentRow()
        if idx < 0 or idx >= len(self._files):
            return
        has_hdrs = self._chk_headers.isChecked()
        self._current_df = _load_preview(
            self._files[idx], self._delimiter, has_hdrs
        )
        _populate_preview_table(self._preview_table, self._current_df)
        self._populate_column_dropdowns()

    def _populate_column_dropdowns(self):
        choices = _col_choices(self._current_df)
        none_choices = [_NONE_LABEL] + choices
        for cmb in (
            self._cmb_position, self._cmb_row_col,
            self._cmb_col_col, self._cmb_tube_id, self._cmb_box_id,
        ):
            current = cmb.currentText()
            cmb.blockSignals(True)
            cmb.clear()
            cmb.addItems(none_choices)
            if current in none_choices:
                cmb.setCurrentText(current)
            cmb.blockSignals(False)

        # Auto-guess from column headers (only fills blanks, never overwrites user choice)
        def _try_guess(cmb, *prefixes):
            if cmb.currentText() == _NONE_LABEL:
                guess = _guess_col(choices, *prefixes)
                if guess:
                    cmb.setCurrentText(guess)

        _try_guess(self._cmb_row_col,  "row", "rad")
        _try_guess(self._cmb_col_col,  "col")
        _try_guess(self._cmb_tube_id,  "tube")
        _try_guess(self._cmb_box_id,   "rack", "orient")

    def _toggle_split(self, checked: bool):
        split = checked if isinstance(checked, bool) else self._chk_split.isChecked()
        self._lbl_position.setVisible(not split)
        self._cmb_position.setVisible(not split)
        self._lbl_row_col.setVisible(split)
        self._cmb_row_col.setVisible(split)
        self._lbl_col_col.setVisible(split)
        self._cmb_col_col.setVisible(split)

    def _accept(self):
        if not self._files:
            QMessageBox.warning(self, "No files", "Please select at least one file.")
            return

        df = self._current_df
        if df.empty:
            QMessageBox.warning(self, "No preview", "Could not read any data from the selected file.")
            return

        split = self._chk_split.isChecked()

        # Validate required column mappings
        if self._cmb_tube_id.currentText() == _NONE_LABEL:
            QMessageBox.warning(self, "Missing Mapping", "Please select a Tube ID column.")
            return
        if self._cmb_box_id.currentText() == _NONE_LABEL:
            QMessageBox.warning(self, "Missing Mapping", "Please select a Box ID column.")
            return
        if split:
            if (self._cmb_row_col.currentText() == _NONE_LABEL
                    or self._cmb_col_col.currentText() == _NONE_LABEL):
                QMessageBox.warning(self, "Missing Mapping",
                                    "Please select both Row and Column columns.")
                return
        else:
            if self._cmb_position.currentText() == _NONE_LABEL:
                QMessageBox.warning(self, "Missing Mapping", "Please select a Position column.")
                return

        opts = ScanFileOptions(
            files=self._files,
            has_headers=self._chk_headers.isChecked(),
            split_position=split,
            col_position=self._cmb_position.currentText() if not split else None,
            col_row=self._cmb_row_col.currentText() if split else None,
            col_col=self._cmb_col_col.currentText() if split else None,
            col_tube_id=self._cmb_tube_id.currentText(),
            col_box_id=self._cmb_box_id.currentText(),
            delimiter=self._delimiter,
        )

        rows, warnings = self.dm.load_scan_files(opts)
        if warnings:
            warn_text = "\n".join(warnings[:20])
            if len(warnings) > 20:
                warn_text += f"\n…and {len(warnings) - 20} more."
            QMessageBox.warning(self, "Import warnings", warn_text)

        if rows == 0 and not warnings:
            QMessageBox.warning(self, "Empty result", "No valid rows were loaded. Check column mappings.")
            return

        QMessageBox.information(
            self, "Import complete",
            f"Loaded {rows} tube entries across "
            f"{len(self.dm.box_inventory)} box(es)."
        )
        self.accept()


# ── PicklistImportDialog ───────────────────────────────────────────────────────

class PicklistImportDialog(QDialog):
    """Dialog for importing the picklist file."""

    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.dm = data_manager
        self.setWindowTitle("Import Picklist")
        self.setMinimumWidth(700)
        self.setMinimumHeight(520)

        self._file: str = ""
        self._current_df: pd.DataFrame = pd.DataFrame()
        self._delimiter: str = ","

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── File picker ────────────────────────────────────────────────────────
        file_row = QHBoxLayout()
        self._file_label = QLabel("No file selected")
        btn_browse = QPushButton("Browse…")
        btn_browse.setFixedWidth(90)
        btn_browse.clicked.connect(self._browse_file)
        file_row.addWidget(self._file_label, 1)
        file_row.addWidget(btn_browse)
        root.addLayout(file_row)

        # ── Headers checkbox ───────────────────────────────────────────────────
        self._chk_headers = QCheckBox("File has headers")
        self._chk_headers.setChecked(True)
        self._chk_headers.toggled.connect(self._refresh_preview)
        root.addWidget(self._chk_headers)

        # ── Preview table ──────────────────────────────────────────────────────
        grp_prev = QGroupBox("File preview (first rows)")
        prev_lay = QVBoxLayout(grp_prev)
        self._preview_table = QTableWidget()
        self._preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._preview_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._preview_table.setFixedHeight(140)
        prev_lay.addWidget(self._preview_table)
        root.addWidget(grp_prev)

        # ── Column mapping ─────────────────────────────────────────────────────
        grp_map = QGroupBox("Column mapping")
        form = QFormLayout(grp_map)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._cmb_tube_id = QComboBox()
        form.addRow("Tube ID column  (required):", self._cmb_tube_id)

        self._cmb_case_id = QComboBox()
        form.addRow("Case ID column  (optional):", self._cmb_case_id)

        root.addWidget(grp_map)

        # ── Extra metadata columns ─────────────────────────────────────────────
        grp_extra = QGroupBox("Additional metadata columns  (optional, multi-select)")
        extra_lay = QVBoxLayout(grp_extra)
        self._list_extra = QListWidget()
        self._list_extra.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self._list_extra.setFixedHeight(90)
        extra_lay.addWidget(self._list_extra)
        root.addWidget(grp_extra)

        # ── Buttons ────────────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select picklist file",
            "",
            "Data files (*.csv *.txt *.tsv *.dat);;All files (*)",
        )
        if not path:
            return
        self._file = path
        short = path.split("\\")[-1].split("/")[-1]
        self._file_label.setText(short)
        self._delimiter = _detect_delimiter(path)
        self._refresh_preview()

    def _refresh_preview(self):
        if not self._file:
            return
        has_hdrs = self._chk_headers.isChecked()
        self._current_df = _load_preview(self._file, self._delimiter, has_hdrs)
        _populate_preview_table(self._preview_table, self._current_df)
        self._populate_dropdowns()

    def _populate_dropdowns(self):
        choices = _col_choices(self._current_df)
        none_choices = [_NONE_LABEL] + choices

        for cmb in (self._cmb_tube_id, self._cmb_case_id):
            current = cmb.currentText()
            cmb.blockSignals(True)
            cmb.clear()
            cmb.addItems(none_choices)
            if current in none_choices:
                cmb.setCurrentText(current)
            cmb.blockSignals(False)

        # Auto-guess from column headers (only fills blanks, never overwrites user choice)
        def _try_guess(cmb, *prefixes):
            if cmb.currentText() == _NONE_LABEL:
                guess = _guess_col(choices, *prefixes)
                if guess:
                    cmb.setCurrentText(guess)

        _try_guess(self._cmb_tube_id, "isolat_bplass")
        _try_guess(self._cmb_case_id, "sak", "case")

        # Extra metadata list
        self._list_extra.clear()
        for c in choices:
            item = QListWidgetItem(c)
            self._list_extra.addItem(item)

    def _accept(self):
        if not self._file:
            QMessageBox.warning(self, "No file", "Please select a picklist file.")
            return

        if self._current_df.empty:
            QMessageBox.warning(self, "No data", "Could not read any data from the file.")
            return

        if self._cmb_tube_id.currentText() == _NONE_LABEL:
            QMessageBox.warning(self, "Missing Mapping", "Please select a Tube ID column.")
            return

        col_case_raw = self._cmb_case_id.currentText()
        col_case = None if col_case_raw == _NONE_LABEL else col_case_raw

        extra = [
            item.text()
            for item in self._list_extra.selectedItems()
        ]

        opts = PicklistOptions(
            file=self._file,
            has_headers=self._chk_headers.isChecked(),
            col_tube_id=self._cmb_tube_id.currentText(),
            col_case_id=col_case,
            extra_cols=extra,
            delimiter=self._delimiter,
        )

        rows, warnings = self.dm.load_picklist(opts)
        if warnings:
            QMessageBox.warning(self, "Import warnings", "\n".join(warnings))

        if rows == 0:
            QMessageBox.warning(self, "Empty result", "No valid tube IDs were loaded.")
            return

        QMessageBox.information(
            self, "Import complete",
            f"Loaded {rows} tube(s) onto the picklist."
        )
        self.accept()
