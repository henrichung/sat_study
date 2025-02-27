#!/usr/bin/env python3
"""
PyQt GUI for the SAT Worksheet Generator and SAT Question Generator.
This application provides a unified interface for:
  • Managing questions (add, edit, delete)
  • Generating worksheets from selected questions
"""
import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QThreadPool
from src.ui.question_manager import WorksheetAndQuestionManagerWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAT Question Manager & Worksheet Generator")
        self.setMinimumSize(1200, 800)
        self.threadpool = QThreadPool()
        self.init_ui()

    def init_ui(self):
        # Use the merged widget as the central widget
        central_widget = WorksheetAndQuestionManagerWidget()
        self.setCentralWidget(central_widget)