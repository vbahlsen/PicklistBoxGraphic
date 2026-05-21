"""QSS stylesheet constants and helpers."""

MAIN_QSS = """
QMainWindow, QDialog {
    background-color: #ECEFF1;
}

QGroupBox {
    font-weight: bold;
    font-size: 9pt;
    color: #000000;
    border: 1px solid #B0BEC5;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    background-color: #ECEFF1;
}

QPushButton {
    background-color: #37474F;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 9pt;
}
QPushButton:hover  { background-color: #546E7A; }
QPushButton:pressed { background-color: #263238; }
QPushButton:disabled { background-color: #B0BEC5; color: #ECEFF1; }

QPushButton#btn_scan_box {
    background-color: #1565C0;
    font-size: 10pt;
    padding: 8px 18px;
}
QPushButton#btn_scan_box:hover  { background-color: #1976D2; }
QPushButton#btn_scan_box:pressed { background-color: #0D47A1; }

QPushButton#btn_reset {
    background-color: #B71C1C;
}
QPushButton#btn_reset:hover  { background-color: #C62828; }
QPushButton#btn_reset:pressed { background-color: #7F0000; }

QPushButton#btn_import {
    background-color: #2E7D32;
}
QPushButton#btn_import:hover  { background-color: #388E3C; }
QPushButton#btn_import:pressed { background-color: #1B5E20; }

QLineEdit {
    background-color: #FFFFFF;
    border: 2px solid #90A4AE;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12pt;
    color: #212121;
}
QLineEdit:focus {
    border-color: #1565C0;
}

QLabel#mode_label {
    font-size: 11pt;
    font-weight: bold;
    color: #37474F;
}
QLabel#mode_label[mode="BOX"] {
    color: #1565C0;
}
QLabel#mode_label[mode="TUBE"] {
    color: #2E7D32;
}

QLabel#banner_label {
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 9pt;
    font-weight: bold;
}
QLabel#banner_label[severity="error"] {
    background-color: #FFCDD2;
    color: #000000;
    border: 1px solid #EF9A9A;
}
QLabel#banner_label[severity="warning"] {
    background-color: #FFF9C4;
    color: #000000;
    border: 1px solid #F9A825;
}
QLabel#banner_label[severity="success"] {
    background-color: #C8E6C9;
    color: #000000;
    border: 1px solid #66BB6A;
}
QLabel#banner_label[severity="info"] {
    background-color: #E3F2FD;
    color: #000000;
    border: 1px solid #90CAF9;
}

QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #CFD8DC;
    border-radius: 4px;
    font-size: 9pt;
    color: #000000;
}
QListWidget::item {
    padding: 5px 8px;
    border-bottom: 1px solid #ECEFF1;
}
QListWidget::item:selected {
    background-color: #1565C0;
    color: #FFFFFF;
}

QTableWidget {
    gridline-color: #CFD8DC;
    font-size: 9pt;
    background-color: #FFFFFF;
    color: #000000;
}
QHeaderView::section {
    background-color: #546E7A;
    color: #FFFFFF;
    padding: 4px;
    font-weight: bold;
    border: none;
}

QScrollArea { border: none; }

/* ── Global text defaults so dialog widgets are always readable ── */
QLabel {
    color: #000000;
    font-size: 9pt;
}

QCheckBox {
    color: #000000;
    font-size: 9pt;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
}

QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    color: #000000;
    border: 1px solid #90A4AE;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 9pt;
    min-height: 22px;
}
QSpinBox:focus, QDoubleSpinBox:focus { border-color: #1565C0; }
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    width: 16px;
    border: none;
    background-color: #ECEFF1;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #B0BEC5;
}

QComboBox {
    background-color: #FFFFFF;
    color: #000000;
    border: 1px solid #90A4AE;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 9pt;
    min-height: 24px;
}
QComboBox:hover  { border-color: #546E7A; }
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #000000;
    selection-background-color: #1565C0;
    selection-color: #FFFFFF;
    border: 1px solid #90A4AE;
    font-size: 9pt;
}

QTableWidget QTableCornerButton::section {
    background-color: #546E7A;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}

/* Metadata panel */
QLabel#meta_title {
    font-size: 22pt;
    font-weight: bold;
    color: #000000;
}
QLabel#meta_key {
    font-size: 9pt;
    color: #000000;
    font-weight: bold;
}
QLabel#meta_value {
    font-size: 10pt;
    color: #000000;
}
"""
