from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                            QListView, QPushButton, QLineEdit, QMessageBox)
from PyQt5.QtCore import Qt, QSortFilterProxyModel, pyqtSignal, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem

class QuestionListPanel(QWidget):
    # Define signals
    question_selected = pyqtSignal(str)  # Emits question UID when selected
    delete_question_requested = pyqtSignal()
    questions_added_to_worksheet = pyqtSignal(list)  # Emits list of questions
    questions_removed_from_worksheet = pyqtSignal(list)  # Emits list of indices

    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        left_layout = QVBoxLayout()
        
        # Search/Filter
        filter_layout = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search questions...")
        self.filter_edit.textChanged.connect(self.filter_questions)
        filter_layout.addWidget(self.filter_edit)
        left_layout.addLayout(filter_layout)
        
        # Question list
        self.model = QStandardItemModel()
        self.proxyModel = QSortFilterProxyModel()
        self.proxyModel.setSourceModel(self.model)
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        
        list_label = QLabel("Available Questions:")
        left_layout.addWidget(list_label)
        self.question_list = QListView()
        self.question_list.setModel(self.proxyModel)
        self.question_list.selectionModel().selectionChanged.connect(self.on_question_selection_changed)
        self.question_list.setSelectionMode(QListView.ExtendedSelection)
        left_layout.addWidget(self.question_list)
        
        # Selected questions list for worksheet
        selected_label = QLabel("Selected Questions for Worksheet:")
        left_layout.addWidget(selected_label)
        self.selected_model = QStandardItemModel()
        self.selected_list = QListView()
        self.selected_list.setModel(self.selected_model)
        self.selected_list.setSelectionMode(QListView.ExtendedSelection)
        left_layout.addWidget(self.selected_list)
        
        # Buttons for question selection
        selection_buttons = QHBoxLayout()
        self.add_to_selected_btn = QPushButton("Add to Worksheet")
        self.add_to_selected_btn.clicked.connect(self.on_add_to_selected)
        self.remove_from_selected_btn = QPushButton("Remove from Worksheet")
        self.remove_from_selected_btn.clicked.connect(self.on_remove_from_selected)
        self.remove_from_selected_btn.setEnabled(False)
        selection_buttons.addWidget(self.add_to_selected_btn)
        selection_buttons.addWidget(self.remove_from_selected_btn)
        left_layout.addLayout(selection_buttons)
        
        # Question management buttons
        qm_buttons = QHBoxLayout()
        self.delete_btn = QPushButton("Delete Question")
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        
        qm_buttons.addWidget(self.delete_btn)
        left_layout.addLayout(qm_buttons)
        
        # Initialize state of buttons
        self.delete_btn.setVisible(False)
        
        self.setLayout(left_layout)
    
    def set_questions(self, questions, excluded_uids=None):
        """Populate the list with Question objects, accounting for excluded questions."""
        excluded_uids = excluded_uids or set()
        self.model.clear()
        for i, question in enumerate(questions):
            # Skip excluded questions
            if question.uid in excluded_uids:
                continue
                
            try:
                text = question.content.text if hasattr(question, 'content') else str(question)
                text = text[:50] if text else "Untitled Question"
            except (AttributeError, TypeError):
                text = "Untitled Question"
            
            display_text = f"{i+1}: {text}"
            item = QStandardItem(display_text)
            item.setData(question.uid, Qt.UserRole)
            self.model.appendRow(item)
    
    def on_question_selection_changed(self):
        selected_indexes = self.question_list.selectedIndexes()
        if not selected_indexes:
            self.delete_btn.setVisible(False)
            return
        
        # Only load the first selected question into the form
        selected_index = selected_indexes[0]
        model_index = self.proxyModel.mapToSource(selected_index)
        question_uid = model_index.data(Qt.UserRole)
        self.question_selected.emit(question_uid)
        
        # Update button visibility
        self.delete_btn.setVisible(True)
    
    def on_add_to_selected(self):
        """Add selected questions to the worksheet list."""
        selected_indexes = self.question_list.selectedIndexes()
        if not selected_indexes:
            return
        
        # Get all selected questions
        selected_questions = []
        for index in selected_indexes:
            proxy_index = index
            source_index = self.proxyModel.mapToSource(proxy_index)
            selected_questions.append(source_index.data(Qt.UserRole))  # Add UID
        
        # Emit signal with selected question UIDs
        self.questions_added_to_worksheet.emit(selected_questions)
        
        # Clear selection
        self.question_list.clearSelection()
    
    def on_remove_from_selected(self):
        """Remove selected questions from the worksheet list."""
        selected_indexes = self.selected_list.selectedIndexes()
        if not selected_indexes:
            return
        
        # Get indices of selected items
        indices = [index.row() for index in selected_indexes]
        
        # Emit signal with indices to remove
        self.questions_removed_from_worksheet.emit(indices)
        
        # Clear selection
        self.selected_list.clearSelection()
    
    def update_selected_list(self, selected_questions):
        """Update the selected questions list view."""
        self.selected_model.clear()
        
        if not selected_questions:
            self.remove_from_selected_btn.setEnabled(False)
            return
        
        for i, question in enumerate(selected_questions):
            try:
                text = question.content.text[:50] + "..." if len(question.content.text) > 50 else question.content.text
                item = QStandardItem(f"{i+1}: {text}")
                item.setData(question.uid, Qt.UserRole)
                self.selected_model.appendRow(item)
            except (AttributeError, TypeError):
                item = QStandardItem(f"{i+1}: Untitled Question")
                self.selected_model.appendRow(item)
        
        self.remove_from_selected_btn.setEnabled(True)
    
    def filter_questions(self):
        """Filter the question list based on search text."""
        search_text = self.filter_edit.text()
        self.proxyModel.setFilterRegExp(search_text)
    
    def on_delete_clicked(self):
        """Handle delete question button clicks."""
        self.delete_question_requested.emit()
    
    def clear_selection(self):
        """Clear any selected items in the question list."""
        self.question_list.clearSelection()
        self.delete_btn.setVisible(False)
