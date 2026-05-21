"""Send a label to the system default printer using QPrinter + QPainter."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtPrintSupport import QPrinter

from .label_config import LabelConfig


def print_label(config: LabelConfig, data: dict) -> bool:
    """
    Render and print one label immediately to the system default printer.

    Returns True on success, False if the printer could not be started.
    ``data`` is the result dict from ``DataManager.record_scan()``.

    NOTE: We deliberately do NOT set a custom QPageSize.  On Windows, sending
    an unrecognised paper size to the driver causes painter.begin() to fail
    silently.  Label printers already have the label size configured in their
    driver; standard printers use their default paper and receive content
    positioned from the top-left corner at the configured mm coordinates.
    """
    from PyQt6.QtGui import QPainter

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setFullPage(True)

    painter = QPainter()
    if not painter.begin(printer):
        return False

    try:
        dpi = printer.resolution()
        mm_to_dots = dpi / 25.4

        for fdef in config.fields:
            if not fdef.enabled:
                continue

            value = _resolve_value(fdef.field_key, data)
            if value is None:
                continue

            if fdef.show_prefix and fdef.display_name:
                text = f"{fdef.display_name}: {value}"
            else:
                text = value

            font = QFont()
            font.setPointSizeF(float(fdef.font_size_pt))
            painter.setFont(font)

            x = fdef.x_mm * mm_to_dots
            y = fdef.y_mm * mm_to_dots
            w = max(1.0, config.label_width_mm - fdef.x_mm) * mm_to_dots
            h = 10.0 * mm_to_dots   # 10 mm bounding-box height - one text line

            painter.drawText(
                QRectF(x, y, w, h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                text,
            )
    finally:
        painter.end()

    return True


def _resolve_value(field_key: str, data: dict) -> str | None:
    """Return the string value for a field key from a scan-result dict."""
    if field_key == "case_id":
        return data.get("case_id") or None
    if field_key == "tube_id":
        return data.get("tube_id") or None
    if field_key == "position":
        return data.get("position") or None
    return data.get("metadata", {}).get(field_key) or None
