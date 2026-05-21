"""WYSIWYG label template editor dialog."""

from __future__ import annotations

import copy
from typing import Callable

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QBrush, QColor, QFont, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .label_config import FieldDef, LabelConfig, LabelTemplateStore

_SCALE = 10.0  # canvas pixels per millimetre


# -- Draggable canvas item -----------------------------------------------------

class _DraggableTextItem(QGraphicsTextItem):
    """Text item that notifies a callback whenever it is moved."""

    def __init__(
        self,
        text: str,
        field_idx: int,
        on_moved: Callable[[int, float, float], None],
    ) -> None:
        super().__init__(text)
        self._field_idx = field_idx
        self._on_moved = on_moved
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pt: QPointF = value
            self._on_moved(self._field_idx, pt.x(), pt.y())
        return super().itemChange(change, value)


# -- Sample text helper --------------------------------------------------------

_SAMPLE_VALUES: dict[str, str] = {
    "case_id":  "2026-01-12345",
    "tube_id":  "TUBE_001",
    "position": "A1",
}


def _sample_text(fdef: FieldDef) -> str:
    """Return realistic preview text for a field."""
    value = _SAMPLE_VALUES.get(fdef.field_key, fdef.field_key)
    if fdef.show_prefix and fdef.display_name:
        return f"{fdef.display_name}: {value}"
    return value


# -- Dialog --------------------------------------------------------------------

class LabelEditorDialog(QDialog):
    """
    WYSIWYG label template editor with multi-template support.

    Pass the LabelTemplateStore and the path to the config file.
    The file is only written when the user explicitly clicks Save / Save As.
    Clicking Apply updates the store's active template for the current session
    without writing to disk.
    """

    def __init__(
        self,
        store: LabelTemplateStore,
        config_path: str,
        extra_metadata_keys: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Label Template Editor")
        self.setMinimumSize(820, 600)

        self._store = store
        self._config_path = config_path
        self._extra_keys: list[str] = list(extra_metadata_keys)
        self._dirty = False

        # Working copy of the currently selected template
        self._tpl_name: str = store.active_name
        self._working: LabelConfig = copy.deepcopy(store.active)

        self._scene = QGraphicsScene()
        self._scene.setBackgroundBrush(QBrush(QColor("#90A4AE")))
        self._text_items: dict[int, _DraggableTextItem] = {}

        self._build_ui()
        self._rebuild_canvas()
        self._rebuild_field_list()

    # -- UI construction -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # -- Template management bar --------------------------------------------
        tpl_row = QHBoxLayout()
        tpl_row.setSpacing(6)
        tpl_row.addWidget(QLabel("Template:"))

        self._cmb_tpl = QComboBox()
        self._cmb_tpl.setMinimumWidth(150)
        self._cmb_tpl.addItems(list(self._store.templates.keys()))
        self._cmb_tpl.setCurrentText(self._tpl_name)
        self._cmb_tpl.currentTextChanged.connect(self._on_template_switched)
        tpl_row.addWidget(self._cmb_tpl)

        self._btn_save = QPushButton("Save")
        self._btn_save.setToolTip("Overwrite this template in the saved config file")
        self._btn_save.clicked.connect(self._on_save)
        tpl_row.addWidget(self._btn_save)

        btn_save_as = QPushButton("Save As\u2026")
        btn_save_as.setToolTip("Save the current design as a new named template")
        btn_save_as.clicked.connect(self._on_save_as)
        tpl_row.addWidget(btn_save_as)

        self._btn_del_tpl = QPushButton("Delete Template")
        self._btn_del_tpl.setToolTip("Remove this template (cannot remove the last one)")
        self._btn_del_tpl.clicked.connect(self._on_delete_template)
        self._btn_del_tpl.setEnabled(len(self._store.templates) > 1)
        tpl_row.addWidget(self._btn_del_tpl)

        tpl_row.addStretch()
        root.addLayout(tpl_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        # -- Dimension row ------------------------------------------------------
        dim_row = QHBoxLayout()
        dim_row.setSpacing(6)
        dim_row.addWidget(QLabel("Label size:"))

        self._spn_width = QDoubleSpinBox()
        self._spn_width.setRange(5.0, 300.0)
        self._spn_width.setDecimals(1)
        self._spn_width.setSuffix(" mm")
        self._spn_width.setValue(self._working.label_width_mm)
        self._spn_width.valueChanged.connect(self._on_dimensions_changed)

        self._spn_height = QDoubleSpinBox()
        self._spn_height.setRange(5.0, 300.0)
        self._spn_height.setDecimals(1)
        self._spn_height.setSuffix(" mm")
        self._spn_height.setValue(self._working.label_height_mm)
        self._spn_height.valueChanged.connect(self._on_dimensions_changed)

        dim_row.addWidget(QLabel("W:"))
        dim_row.addWidget(self._spn_width)
        dim_row.addWidget(QLabel("\u00d7  H:"))
        dim_row.addWidget(self._spn_height)
        dim_row.addStretch()
        root.addLayout(dim_row)

        # -- Middle: canvas + field list ----------------------------------------
        mid = QHBoxLayout()
        mid.setSpacing(10)

        canvas_grp = QGroupBox("Preview  (drag fields to reposition)")
        canvas_lay = QVBoxLayout(canvas_grp)
        self._view = QGraphicsView(self._scene)
        canvas_lay.addWidget(self._view)
        mid.addWidget(canvas_grp, 1)

        fields_grp = QGroupBox("Fields")
        fields_grp.setFixedWidth(320)
        fields_lay = QVBoxLayout(fields_grp)

        # Column headers
        hdr = QHBoxLayout()
        hdr.setContentsMargins(2, 0, 2, 0)
        hdr.setSpacing(4)
        lbl_on  = QLabel("On");  lbl_on.setFixedWidth(20)
        lbl_pfx = QLabel("Pfx"); lbl_pfx.setFixedWidth(20)
        lbl_pfx.setToolTip("Show prefix label on printed output")
        lbl_field = QLabel("Field / Prefix Label")
        lbl_size  = QLabel("Size"); lbl_size.setFixedWidth(62)
        hdr.addWidget(lbl_on)
        hdr.addWidget(lbl_pfx)
        hdr.addWidget(lbl_field, 1)
        hdr.addWidget(lbl_size)
        hdr.addSpacing(28)
        fields_lay.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fields_widget = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_widget)
        self._fields_layout.setContentsMargins(2, 2, 2, 2)
        self._fields_layout.setSpacing(3)
        self._fields_layout.addStretch()
        self._fields_widget.setStyleSheet("background-color: #ECEFF1;")
        scroll.setWidget(self._fields_widget)
        fields_lay.addWidget(scroll, 1)

        btn_add = QPushButton("\uff0b  Add Field\u2026")
        btn_add.clicked.connect(self._on_add_field)
        fields_lay.addWidget(btn_add)

        mid.addWidget(fields_grp)
        root.addLayout(mid, 1)

        # -- Apply / Cancel -----------------------------------------------------
        btns = QDialogButtonBox()
        btn_apply = btns.addButton("Apply", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_apply.setToolTip(
            "Use this design for printing in the current session "
            "(does not save to file \u2014 use Save for that)"
        )
        btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # -- Template management ---------------------------------------------------

    def _on_template_switched(self, name: str) -> None:
        if name == self._tpl_name:
            return
        if self._dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Save changes to '{self._tpl_name}' before switching?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                self._cmb_tpl.blockSignals(True)
                self._cmb_tpl.setCurrentText(self._tpl_name)
                self._cmb_tpl.blockSignals(False)
                return
            if reply == QMessageBox.StandardButton.Save:
                self._do_save(self._tpl_name)

        self._tpl_name = name
        self._working = copy.deepcopy(self._store.templates[name])
        self._dirty = False
        self._load_working_into_ui()

    def _on_save(self) -> None:
        self._do_save(self._tpl_name)

    def _on_save_as(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            "Save As New Template",
            "Template name:",
            text=self._tpl_name,
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._store.templates and name != self._tpl_name:
            reply = QMessageBox.question(
                self,
                "Overwrite?",
                f"Template '{name}' already exists. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._do_save(name)
        self._cmb_tpl.blockSignals(True)
        if self._cmb_tpl.findText(name) < 0:
            self._cmb_tpl.addItem(name)
        self._cmb_tpl.setCurrentText(name)
        self._cmb_tpl.blockSignals(False)
        self._tpl_name = name
        self._btn_del_tpl.setEnabled(len(self._store.templates) > 1)

    def _on_delete_template(self) -> None:
        if len(self._store.templates) <= 1:
            QMessageBox.information(self, "Cannot Delete", "Cannot delete the last template.")
            return
        reply = QMessageBox.question(
            self,
            "Delete Template",
            f"Delete template '{self._tpl_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del self._store.templates[self._tpl_name]
        try:
            self._store.save_to_file(self._config_path)
        except Exception:
            pass
        self._cmb_tpl.blockSignals(True)
        idx = self._cmb_tpl.findText(self._tpl_name)
        self._cmb_tpl.removeItem(idx)
        self._tpl_name = self._cmb_tpl.currentText()
        self._cmb_tpl.blockSignals(False)
        self._working = copy.deepcopy(self._store.templates[self._tpl_name])
        self._dirty = False
        self._load_working_into_ui()
        self._btn_del_tpl.setEnabled(len(self._store.templates) > 1)

    def _do_save(self, name: str) -> None:
        self._store.templates[name] = copy.deepcopy(self._working)
        if self._store.active_name not in self._store.templates:
            self._store.active_name = name
        try:
            self._store.save_to_file(self._config_path)
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save config:\n{exc}")
            return
        self._dirty = False

    def _load_working_into_ui(self) -> None:
        self._spn_width.blockSignals(True)
        self._spn_height.blockSignals(True)
        self._spn_width.setValue(self._working.label_width_mm)
        self._spn_height.setValue(self._working.label_height_mm)
        self._spn_width.blockSignals(False)
        self._spn_height.blockSignals(False)
        self._rebuild_canvas()
        self._rebuild_field_list()

    def _mark_dirty(self) -> None:
        self._dirty = True

    # -- Canvas helpers --------------------------------------------------------

    def _rebuild_canvas(self) -> None:
        self._scene.clear()
        self._text_items.clear()

        w_px = self._working.label_width_mm * _SCALE
        h_px = self._working.label_height_mm * _SCALE

        self._scene.addRect(
            0, 0, w_px, h_px,
            QPen(QColor("#212121"), 1.5),
            QBrush(QColor("#FFFFFF")),
        )

        for idx, fdef in enumerate(self._working.fields):
            if not fdef.enabled:
                continue
            sample = _sample_text(fdef)
            item = _DraggableTextItem(sample, idx, self._on_item_moved)
            item.setDefaultTextColor(QColor("#000000"))
            font = QFont()
            font.setPointSizeF(float(fdef.font_size_pt))
            item.setFont(font)
            item.setPos(fdef.x_mm * _SCALE, fdef.y_mm * _SCALE)
            self._scene.addItem(item)
            self._text_items[idx] = item

        self._fit_canvas()

    def _fit_canvas(self) -> None:
        w_px = self._working.label_width_mm * _SCALE
        h_px = self._working.label_height_mm * _SCALE
        margin = 20.0
        self._view.setSceneRect(-margin, -margin, w_px + 2 * margin, h_px + 2 * margin)
        self._view.fitInView(
            self._scene.sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    # -- Field-list helpers ----------------------------------------------------

    def _rebuild_field_list(self) -> None:
        while self._fields_layout.count() > 1:
            item = self._fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for idx, fdef in enumerate(self._working.fields):
            row_w = self._make_field_row(idx, fdef)
            self._fields_layout.insertWidget(self._fields_layout.count() - 1, row_w)

    def _make_field_row(self, idx: int, fdef: FieldDef) -> QWidget:
        row_w = QWidget()
        lay = QHBoxLayout(row_w)
        lay.setContentsMargins(2, 1, 2, 1)
        lay.setSpacing(4)

        # Enabled checkbox
        chk_enabled = QCheckBox()
        chk_enabled.setChecked(fdef.enabled)
        chk_enabled.setFixedWidth(20)
        chk_enabled.toggled.connect(lambda checked, i=idx: self._on_field_enabled(i, checked))
        lay.addWidget(chk_enabled)

        # Prefix-visible checkbox
        chk_pfx = QCheckBox()
        chk_pfx.setChecked(fdef.show_prefix)
        chk_pfx.setFixedWidth(20)
        chk_pfx.setToolTip("Show prefix label (e.g. 'Case:') on the printed label")
        chk_pfx.toggled.connect(lambda checked, i=idx: self._on_field_show_prefix(i, checked))
        lay.addWidget(chk_pfx)

        # Field name button (click to rename display_name / prefix text)
        label_text = fdef.display_name if fdef.display_name else fdef.field_key
        btn_name = QPushButton(label_text)
        btn_name.setFlat(True)
        btn_name.setToolTip(f"Field key: {fdef.field_key}\nClick to rename the prefix label")
        btn_name.setStyleSheet("text-align: left; padding: 1px 3px; color: #212121;")
        btn_name.clicked.connect(lambda _, i=idx: self._on_rename_prefix(i))
        lay.addWidget(btn_name, 1)

        # Font size spinbox
        spn = QSpinBox()
        spn.setRange(4, 48)
        spn.setValue(fdef.font_size_pt)
        spn.setSuffix("pt")
        spn.setFixedWidth(62)
        spn.valueChanged.connect(lambda val, i=idx: self._on_field_fontsize(i, val))
        lay.addWidget(spn)

        # Delete button
        btn_del = QPushButton("\u00d7")
        btn_del.setFixedWidth(24)
        btn_del.setFixedHeight(24)
        btn_del.setToolTip("Remove field")
        btn_del.setEnabled(fdef.field_key not in ("case_id", "tube_id", "position"))
        btn_del.clicked.connect(lambda _, i=idx: self._on_field_delete(i))
        lay.addWidget(btn_del)

        return row_w

    # -- Event handlers --------------------------------------------------------

    def _on_dimensions_changed(self) -> None:
        self._working.label_width_mm = self._spn_width.value()
        self._working.label_height_mm = self._spn_height.value()
        self._mark_dirty()
        self._rebuild_canvas()

    def _on_item_moved(self, field_idx: int, px_x: float, px_y: float) -> None:
        if field_idx < len(self._working.fields):
            fdef = self._working.fields[field_idx]
            fdef.x_mm = max(0.0, round(px_x / _SCALE, 2))
            fdef.y_mm = max(0.0, round(px_y / _SCALE, 2))
            self._mark_dirty()

    def _on_field_enabled(self, field_idx: int, checked: bool) -> None:
        self._working.fields[field_idx].enabled = checked
        self._mark_dirty()
        self._rebuild_canvas()

    def _on_field_show_prefix(self, field_idx: int, checked: bool) -> None:
        self._working.fields[field_idx].show_prefix = checked
        self._mark_dirty()
        if field_idx in self._text_items:
            fdef = self._working.fields[field_idx]
            self._text_items[field_idx].setPlainText(_sample_text(fdef))

    def _on_rename_prefix(self, field_idx: int) -> None:
        fdef = self._working.fields[field_idx]
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Prefix Label",
            f"Prefix label for '{fdef.field_key}':",
            text=fdef.display_name,
        )
        if not ok:
            return
        fdef.display_name = new_name.strip()
        self._mark_dirty()
        self._rebuild_field_list()
        if field_idx in self._text_items:
            self._text_items[field_idx].setPlainText(_sample_text(fdef))

    def _on_field_fontsize(self, field_idx: int, value: int) -> None:
        self._working.fields[field_idx].font_size_pt = value
        self._mark_dirty()
        if field_idx in self._text_items:
            font = QFont()
            font.setPointSizeF(float(value))
            self._text_items[field_idx].setFont(font)

    def _on_field_delete(self, field_idx: int) -> None:
        del self._working.fields[field_idx]
        self._mark_dirty()
        self._rebuild_canvas()
        self._rebuild_field_list()

    def _on_add_field(self) -> None:
        existing_keys = {f.field_key for f in self._working.fields}
        available = [k for k in self._extra_keys if k not in existing_keys]

        if available:
            key, ok = QInputDialog.getItem(
                self,
                "Add Field",
                "Select a metadata field to add:",
                available,
                editable=False,
            )
        else:
            key, ok = QInputDialog.getText(
                self,
                "Add Field",
                "Enter the metadata field key:",
            )

        if ok and key.strip() and key.strip() not in existing_keys:
            key = key.strip()
            last_y = max((f.y_mm for f in self._working.fields), default=2.0) + 5.0
            last_y = min(last_y, max(0.0, self._working.label_height_mm - 3.0))
            self._working.fields.append(
                FieldDef(
                    field_key=key,
                    display_name=key,
                    x_mm=2.0,
                    y_mm=last_y,
                    font_size_pt=7,
                    enabled=True,
                    show_prefix=True,
                )
            )
            self._mark_dirty()
            self._rebuild_canvas()
            self._rebuild_field_list()

    # -- accept override -------------------------------------------------------

    def accept(self) -> None:
        """Apply working copy to the store's active template for session use."""
        self._store.templates[self._tpl_name] = copy.deepcopy(self._working)
        self._store.active_name = self._tpl_name
        super().accept()

    # -- Public API ------------------------------------------------------------

    def get_config(self) -> LabelConfig:
        """Return the edited config (valid after exec() == Accepted)."""
        return self._working

    # -- Qt overrides ----------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fit_canvas()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_view"):
            self._fit_canvas()
