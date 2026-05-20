"""Entry point for the Picklist Box Scanner application."""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Picklist Box Scanner")
    app.setFont(QFont("Segoe UI", 9))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
