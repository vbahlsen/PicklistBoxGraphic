"""
DataManager: Responsible for loading scan files, loading picklists,
and maintaining all application state (inventory, picklist, scanned records).
"""

from __future__ import annotations
import re
from typing import Any
import pandas as pd


# ── Supported box layouts ──────────────────────────────────────────────────────
BOX_LAYOUTS = {
    24: (4, 6),   # A–D × 1–6
    48: (6, 8),   # A–F × 1–8
    96: (8, 12),  # A–H × 1–12
}

ROW_LETTERS = "ABCDEFGH"   # max 8 rows (96-well)


def _infer_layout(rows: int, cols: int) -> tuple[int, int]:
    """Return the smallest standard layout that can contain (rows, cols)."""
    for _slots, (r, c) in sorted(BOX_LAYOUTS.items()):
        if rows <= r and cols <= c:
            return r, c
    return rows, cols  # fallback: use data dimensions


def _parse_position(pos: Any) -> tuple[str, int] | None:
    """Parse 'A1', 'A01', 'B12' → ('A', 1). Returns None on failure."""
    s = str(pos).strip().upper()
    m = re.fullmatch(r"([A-H])0*([1-9][0-9]?)", s)
    if m:
        return m.group(1), int(m.group(2))
    return None


def _make_pos_str(row: str, col: int) -> str:
    return f"{row.upper()}{col}"


# ── ScanFile options dataclass ─────────────────────────────────────────────────

class ScanFileOptions:
    """Column mapping options for a scan file."""
    __slots__ = (
        "files", "has_headers", "split_position",
        "col_position", "col_row", "col_col",
        "col_tube_id", "col_box_id",
        "delimiter",
    )

    def __init__(
        self,
        files: list[str],
        has_headers: bool,
        split_position: bool,
        col_position: str | int | None,
        col_row: str | int | None,
        col_col: str | int | None,
        col_tube_id: str | int,
        col_box_id: str | int,
        delimiter: str = ",",
    ):
        self.files = files
        self.has_headers = has_headers
        self.split_position = split_position
        self.col_position = col_position
        self.col_row = col_row
        self.col_col = col_col
        self.col_tube_id = col_tube_id
        self.col_box_id = col_box_id
        self.delimiter = delimiter


class PicklistOptions:
    """Column mapping options for a picklist file."""
    __slots__ = (
        "file", "has_headers",
        "col_tube_id", "col_case_id", "extra_cols",
        "delimiter",
    )

    def __init__(
        self,
        file: str,
        has_headers: bool,
        col_tube_id: str | int,
        col_case_id: str | int | None,
        extra_cols: list[str | int],
        delimiter: str = ",",
    ):
        self.file = file
        self.has_headers = has_headers
        self.col_tube_id = col_tube_id
        self.col_case_id = col_case_id
        self.extra_cols = extra_cols
        self.delimiter = delimiter


# ── Cell status constants ──────────────────────────────────────────────────────
STATUS_PICKLIST   = "picklist"    # in picklist, not yet scanned
STATUS_SCANNED    = "scanned"     # in picklist, already scanned
STATUS_WARNING    = "warning"     # scanned but NOT in picklist
STATUS_PLAIN      = "plain"       # present in box, not in picklist
STATUS_EMPTY      = "empty"       # position exists in layout but no tube


# ── DataManager ───────────────────────────────────────────────────────────────

class DataManager:
    """
    Central data store for the application.

    box_inventory  : {box_id: {pos_str: tube_id}}
    box_sizes      : {box_id: (rows, cols)}  — layout dimensions
    picklist       : {tube_id: {"case_id": ..., "metadata": {...}}}
    scanned_per_box: {box_id: {tube_id: pos_str}}   tube_id → position scanned
    warning_per_box: {box_id: {tube_id: pos_str}}   non-picklist scans
    """

    def __init__(self):
        self.box_inventory: dict[str, dict[str, str]] = {}
        self.box_sizes: dict[str, tuple[int, int]] = {}
        self.picklist: dict[str, dict[str, Any]] = {}
        self.scanned_per_box: dict[str, dict[str, str]] = {}
        self.warning_per_box: dict[str, dict[str, str]] = {}

    # ── Loading ────────────────────────────────────────────────────────────────

    def load_scan_files(self, opts: ScanFileOptions) -> tuple[int, list[str]]:
        """
        Parse one or more scan CSV/TXT files and merge into box_inventory.
        Returns (rows_loaded, list_of_warnings).
        """
        rows_loaded = 0
        warnings: list[str] = []

        for filepath in opts.files:
            try:
                header_row = 0 if opts.has_headers else None
                df = pd.read_csv(
                    filepath,
                    sep=opts.delimiter,
                    header=header_row,
                    dtype=str,
                    keep_default_na=False,
                    engine="python",
                )

                # Normalise column references: header names stay as-is,
                # numeric indices (0-based) converted to actual column labels.
                if not opts.has_headers:
                    df.columns = list(range(len(df.columns)))

                def _col(ref):
                    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
                        return df.columns[int(ref)]
                    return ref

                col_tube = _col(opts.col_tube_id)
                col_box  = _col(opts.col_box_id)

                for _, row in df.iterrows():
                    tube_id = str(row[col_tube]).strip()
                    box_id  = str(row[col_box]).strip()

                    if not tube_id or not box_id:
                        continue

                    # Resolve position
                    if opts.split_position:
                        raw_row = str(row[_col(opts.col_row)]).strip().upper()
                        raw_col = str(row[_col(opts.col_col)]).strip()
                        # Allow numeric strings as col
                        try:
                            col_num = int(raw_col)
                        except ValueError:
                            warnings.append(
                                f"Skipping row – bad column value '{raw_col}'"
                            )
                            continue
                        pos_str = _make_pos_str(raw_row, col_num)
                        row_letter = raw_row
                        col_int    = col_num
                    else:
                        parsed = _parse_position(row[_col(opts.col_position)])
                        if parsed is None:
                            warnings.append(
                                f"Skipping row – bad position '{row[_col(opts.col_position)]}'"
                            )
                            continue
                        row_letter, col_int = parsed
                        pos_str = _make_pos_str(row_letter, col_int)

                    if box_id not in self.box_inventory:
                        self.box_inventory[box_id] = {}
                    self.box_inventory[box_id][pos_str] = tube_id

                    # Track max row/col to determine box size
                    cur_rows = ROW_LETTERS.index(row_letter) + 1
                    cur_cols = col_int
                    prev_r, prev_c = self.box_sizes.get(box_id, (0, 0))
                    self.box_sizes[box_id] = (
                        max(prev_r, cur_rows),
                        max(prev_c, cur_cols),
                    )

                    rows_loaded += 1

            except Exception as exc:
                warnings.append(f"Error reading '{filepath}': {exc}")

        # Round box sizes up to nearest standard layout
        for box_id, (r, c) in self.box_sizes.items():
            self.box_sizes[box_id] = _infer_layout(r, c)

        return rows_loaded, warnings

    def load_picklist(self, opts: PicklistOptions) -> tuple[int, list[str]]:
        """
        Parse the picklist file.
        Returns (rows_loaded, list_of_warnings).
        """
        warnings: list[str] = []
        try:
            header_row = 0 if opts.has_headers else None
            df = pd.read_csv(
                opts.file,
                sep=opts.delimiter,
                header=header_row,
                dtype=str,
                keep_default_na=False,
                engine="python",
            )

            if not opts.has_headers:
                df.columns = list(range(len(df.columns)))

            def _col(ref):
                if ref is None:
                    return None
                if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
                    return df.columns[int(ref)]
                return ref

            col_tube = _col(opts.col_tube_id)
            col_case = _col(opts.col_case_id)
            extra_resolved = [_col(c) for c in opts.extra_cols]

            rows_loaded = 0
            for _, row in df.iterrows():
                tube_id = str(row[col_tube]).strip()
                if not tube_id:
                    continue

                case_id = str(row[col_case]).strip() if col_case else ""
                metadata: dict[str, str] = {}
                for ec in extra_resolved:
                    metadata[str(ec)] = str(row[ec]).strip()

                self.picklist[tube_id] = {
                    "case_id": case_id,
                    "metadata": metadata,
                }
                rows_loaded += 1

            return rows_loaded, warnings

        except Exception as exc:
            return 0, [f"Error reading picklist: {exc}"]

    # ── Queries ────────────────────────────────────────────────────────────────

    def get_box_ids(self) -> list[str]:
        return sorted(self.box_inventory.keys())

    def get_box_layout(self, box_id: str) -> tuple[int, int]:
        """Returns (n_rows, n_cols) for this box."""
        return self.box_sizes.get(box_id, (8, 12))

    def get_box_grid(self, box_id: str) -> dict[str, dict]:
        """
        Returns {pos_str: {"tube_id": ..., "status": STATUS_*}}
        for every position in the box's standard layout grid.
        Positions that have no tube get STATUS_EMPTY.
        """
        rows, cols = self.get_box_layout(box_id)
        inventory  = self.box_inventory.get(box_id, {})
        scanned    = self.scanned_per_box.get(box_id, {})
        warned     = self.warning_per_box.get(box_id, {})

        grid: dict[str, dict] = {}

        for ri in range(rows):
            for ci in range(1, cols + 1):
                pos = _make_pos_str(ROW_LETTERS[ri], ci)
                tube_id = inventory.get(pos, "")

                if not tube_id:
                    grid[pos] = {"tube_id": "", "status": STATUS_EMPTY}
                    continue

                if tube_id in scanned:
                    status = STATUS_SCANNED
                elif tube_id in warned.values() or any(
                    p == pos for p in warned.values()
                ):
                    status = STATUS_WARNING
                elif tube_id in self.picklist:
                    status = STATUS_PICKLIST
                else:
                    status = STATUS_PLAIN

                grid[pos] = {"tube_id": tube_id, "status": status}

        # Also add any warned (non-inventory) positions
        for tube_id, pos in warned.items():
            if pos not in grid:
                grid[pos] = {"tube_id": tube_id, "status": STATUS_WARNING}

        return grid

    def record_scan(self, box_id: str, tube_id: str) -> dict | None:
        """
        Record that a tube was scanned from this box.
        Returns:
          {"status": STATUS_SCANNED, "case_id": ..., "metadata": {...}}  — picklist hit
          {"status": STATUS_WARNING}                                      — not in picklist
          {"status": "not_in_box"}                                        — tube not found in box
        """
        inventory = self.box_inventory.get(box_id, {})
        # Find position of this tube
        pos = next((p for p, t in inventory.items() if t == tube_id), None)

        if pos is None:
            return {"status": "not_in_box"}

        if tube_id in self.picklist:
            if box_id not in self.scanned_per_box:
                self.scanned_per_box[box_id] = {}
            self.scanned_per_box[box_id][tube_id] = pos
            pl = self.picklist[tube_id]
            return {
                "status": STATUS_SCANNED,
                "position": pos,
                "tube_id": tube_id,
                "case_id": pl["case_id"],
                "metadata": pl["metadata"],
            }
        else:
            if box_id not in self.warning_per_box:
                self.warning_per_box[box_id] = {}
            self.warning_per_box[box_id][tube_id] = pos
            return {
                "status": STATUS_WARNING,
                "position": pos,
                "tube_id": tube_id,
            }

    def is_box_complete(self, box_id: str) -> bool:
        """True when every picklist tube present in this box has been scanned."""
        inventory = self.box_inventory.get(box_id, {})
        tubes_in_box = set(inventory.values())
        picklist_in_box = tubes_in_box & set(self.picklist.keys())
        if not picklist_in_box:
            return False
        scanned = set(self.scanned_per_box.get(box_id, {}).keys())
        return picklist_in_box.issubset(scanned)

    def picklist_count_for_box(self, box_id: str) -> tuple[int, int]:
        """Returns (scanned_count, total_picklist_count) for box."""
        inventory = self.box_inventory.get(box_id, {})
        tubes_in_box = set(inventory.values())
        total = len(tubes_in_box & set(self.picklist.keys()))
        scanned = len(self.scanned_per_box.get(box_id, {}))
        return scanned, total

    def get_tube_metadata(self, tube_id: str) -> dict | None:
        return self.picklist.get(tube_id)

    # ── Reset ──────────────────────────────────────────────────────────────────

    def reset(self):
        self.box_inventory.clear()
        self.box_sizes.clear()
        self.picklist.clear()
        self.scanned_per_box.clear()
        self.warning_per_box.clear()

    def reset_scans_only(self):
        """Clear scan history but keep inventory and picklist."""
        self.scanned_per_box.clear()
        self.warning_per_box.clear()
