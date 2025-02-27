from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QProgressBar, 
                           QLabel, QPushButton)
from PyQt5.QtCore import Qt

class ProgressDialog(QDialog):
    def __init__(self, title="Operation in Progress", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout()
        
        self.status_label = QLabel("Please wait...")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignRight)
        
        self.setLayout(layout)
    
    def update_progress(self, value):
        """Update the progress bar with a percentage value (0-100)"""
        self.progress_bar.setValue(value)
    
    def update_status(self, text):
        """Update the status text"""
        self.status_label.setText(text)