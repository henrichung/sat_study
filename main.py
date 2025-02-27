#!/usr/bin/env python3
"""
Main entry point for the SAT Study application
"""
import sys
import os
from PyQt5.QtWidgets import QApplication
from src.ui.main_window import MainWindow


def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()