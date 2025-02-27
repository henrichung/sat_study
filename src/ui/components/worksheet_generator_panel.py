import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                           QLineEdit, QFormLayout, QCheckBox, QPushButton,
                           QFileDialog)
from PyQt5.QtCore import pyqtSignal
from types import SimpleNamespace

class WorksheetGeneratorPanel(QWidget):
    # Define signals
    generate_worksheets_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Worksheet Generator"))
        
        # Worksheet settings form
        form_layout = QFormLayout()
        self.title_edit = QLineEdit("Worksheet")
        form_layout.addRow("Worksheet Title:", self.title_edit)
        
        self.tags_edit = QLineEdit()
        form_layout.addRow("Tags (comma separated):", self.tags_edit)
        
        self.num_questions_edit = QLineEdit()
        form_layout.addRow("Number of Questions:", self.num_questions_edit)
        
        self.shuffle_checkbox = QCheckBox("Shuffle Questions")
        form_layout.addRow(self.shuffle_checkbox)
        
        self.pages_edit = QLineEdit("1")
        form_layout.addRow("Number of Pages:", self.pages_edit)
        
        self.n_max_edit = QLineEdit("100")
        form_layout.addRow("Max Questions per Worksheet:", self.n_max_edit)
        
        # Output directory selection
        self.output_dir_edit = QLineEdit(os.getcwd())
        out_btn = QPushButton("Browse...")
        out_btn.clicked.connect(self.browse_output_dir)
        out_layout = QHBoxLayout()
        out_layout.addWidget(self.output_dir_edit)
        out_layout.addWidget(out_btn)
        form_layout.addRow("Output Directory:", out_layout)
        
        layout.addLayout(form_layout)
        
        # Generate button
        self.generate_btn = QPushButton("Generate Worksheets")
        self.generate_btn.clicked.connect(self.on_generate_clicked)
        layout.addWidget(self.generate_btn)
        
        self.setLayout(layout)
    
    def browse_output_dir(self):
        """Open file dialog to select output directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", os.getcwd())
        if directory:
            self.output_dir_edit.setText(directory)
    
    def on_generate_clicked(self):
        """Handle generate button clicks."""
        self.generate_worksheets_requested.emit()
    
    def get_worksheet_parameters(self):
        """Get worksheet generation parameters from form."""
        params = SimpleNamespace()
        
        params.title = self.title_edit.text().strip() or "Worksheet"
        params.tags = [t.strip() for t in self.tags_edit.text().split(",")] if self.tags_edit.text().strip() else []
        
        try:
            params.num_questions = int(self.num_questions_edit.text().strip()) if self.num_questions_edit.text().strip() else None
            params.pages = int(self.pages_edit.text().strip()) if self.pages_edit.text().strip() else 1
            params.n_max = int(self.n_max_edit.text().strip()) if self.n_max_edit.text().strip() else 100
        except ValueError:
            # Return default values if parsing fails
            params.num_questions = None
            params.pages = 1
            params.n_max = 100
        
        params.shuffle = self.shuffle_checkbox.isChecked()
        params.output_dir = self.output_dir_edit.text().strip() or os.getcwd()
        
        return params
