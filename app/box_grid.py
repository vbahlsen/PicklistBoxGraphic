"""
BoxGridWidget: Renders a graphical grid of tube positions for a single box.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QFrame, QSizePolicy,
)

from .data_manager import (
    STATUS_PICKLIST, STATUS_SCANNED, STATUS_WARNING,
    STATUS_PLAIN, STATUS_EMPTY, ROW_LETTERS,
)


# ── Colour palette ─────────────────────────────────────────────────────────────
# (text_color, background_color) — all non-empty cells use black text for max contrast
_COLORS = {
    STATUS_PICKLIST: ("#000000", "#4CAF50"),   # black on bright green
    STATUS_SCANNED:  ("#000000", "#BDBDBD"),   # black on mid-grey
    STATUS_WARNING:  ("#000000", "#FFC107"),   # black on amber
    STATUS_PLAIN:    ("#000000", "#FFFFFF"),   # black on white
    STATUS_EMPTY:    ("#888888", "#F0F0F0"),   # grey on off-white
}

_HEADER_BG   = "#37474F"   # dark blue-grey header row/col
_HEADER_FG   = "#FFFFFF"


class _CellLabel(QLabel):
    """A single tube-well cell in the grid."""

    def __init__(self, pos: str, tube_id: str, status: str, parent=None):
        super().__init__(parent)
        self.pos     = pos
        self.tube_id = tube_id
        self._status = status
        self._apply_style()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(92, 62)
        self.setWordWrap(True)

        font = QFont("Segoe UI", 9)
        self.setFont(font)

        self._update_text()

    def _apply_style(self):
        fg, bg = _COLORS.get(self._status, _COLORS[STATUS_PLAIN])
        border_color = "#90A4AE" if self._status == STATUS_EMPTY else fg
        self.setStyleSheet(
            f"background-color: {bg};"
            f"color: {fg};"
            f"border: 1px solid {border_color};"
            f"border-radius: 4px;"
            f"padding: 2px;"
        )

    def _update_text(self):
        fg, _ = _COLORS.get(self._status, _COLORS[STATUS_PLAIN])
        if self._status == STATUS_EMPTY:
            self.setText(
                f"<span style='font-size:8pt;color:#888888'>{self.pos}</span>"
            )
        else:
            # Show position in small text + tube_id on next line (truncated)
            tid = self.tube_id
            if len(tid) > 14:
                tid = tid[:13] + "\u2026"
            self.setText(
                f"<div style='font-size:8pt;color:{fg}'>{self.pos}</div>"
                f"<div style='font-size:9pt;font-weight:bold;color:{fg}'>{tid}</div>"
            )

    def set_status(self, status: str):
        self._status = status
        self._apply_style()
        self._update_text()
        self.update()


def _make_header_label(text: str, fixed_w: int = 82, fixed_h: int = 28) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setFixedSize(fixed_w, fixed_h)
    lbl.setStyleSheet(
        f"background-color: {_HEADER_BG};"
        f"color: {_HEADER_FG};"
        f"font-weight: bold;"
        f"font-size: 9pt;"
        f"border-radius: 3px;"
    )
    return lbl


# ── BoxGridWidget ──────────────────────────────────────────────────────────────

class BoxGridWidget(QWidget):
    """
    Displays a grid of cells for a single lab box.
    Row headers: A, B, … | Column headers: 1, 2, …
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cells: dict[str, _CellLabel] = {}   # pos_str → cell
        self._rows = 0
        self._cols = 0
        self._read_only = False

        outer = QGridLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        # Scroll-container so large grids don't overflow
        self._inner_widget = QWidget()
        self._grid = QGridLayout(self._inner_widget)
        self._grid.setSpacing(3)
        self._grid.setContentsMargins(4, 4, 4, 4)

        outer.addWidget(self._inner_widget, 0, 0)
        self.clear_grid()

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_box(
        self,
        box_id: str,
        grid_data: dict[str, dict],
        rows: int,
        cols: int,
        read_only: bool = False,
    ):
        """
        Populate the grid from DataManager.get_box_grid() output.
        grid_data: {pos_str: {"tube_id": str, "status": str}}
        """
        self._rows     = rows
        self._cols     = cols
        self._read_only = read_only
        self._cells.clear()

        # Remove all widgets from existing layout
        self._clear_layout(self._grid)

        # Corner spacer
        corner = QLabel()
        corner.setFixedSize(28, 28)
        self._grid.addWidget(corner, 0, 0)

        # Column headers  (row 0, col 1..)
        for ci in range(1, cols + 1):
            lbl = _make_header_label(str(ci), fixed_w=82, fixed_h=28)
            self._grid.addWidget(lbl, 0, ci)

        # Row headers + cells
        for ri in range(rows):
            row_letter = ROW_LETTERS[ri]

            # Row header (col 0)
            rh = _make_header_label(row_letter, fixed_w=28, fixed_h=56)
            self._grid.addWidget(rh, ri + 1, 0)

            for ci in range(1, cols + 1):
                pos = f"{row_letter}{ci}"
                cell_data = grid_data.get(pos, {"tube_id": "", "status": STATUS_EMPTY})
                cell = _CellLabel(pos, cell_data["tube_id"], cell_data["status"])
                self._cells[pos] = cell
                self._grid.addWidget(cell, ri + 1, ci)

        self._inner_widget.adjustSize()
        self.adjustSize()

    def mark_scanned(self, position: str, status: str):
        """Update the status colour of a single cell."""
        cell = self._cells.get(position)
        if cell:
            cell.set_status(status)

    def clear_grid(self):
        """Remove all cells and reset to blank state."""
        self._cells.clear()
        self._rows = 0
        self._cols = 0
        self._clear_layout(self._grid)
        placeholder = QLabel("No box loaded")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #9E9E9E; font-size: 14pt;")
        placeholder.setFixedSize(400, 200)
        self._grid.addWidget(placeholder, 0, 0)
        self._inner_widget.adjustSize()
        self.adjustSize()

    def highlight_cell(self, position: str):
        """Briefly flash a cell (noop placeholder for future animation)."""
        pass

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _clear_layout(layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
