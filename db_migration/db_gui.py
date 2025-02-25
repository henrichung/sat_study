#!/usr/bin/env python3
"""
Updated PyQt GUI for the SAT Worksheet Generator and SAT Question Generator.
This version uses SQLite database instead of JSON files for better performance.
"""
import sys
import os
import random
import json
import json_utils
import db_utils
import logging
from types import SimpleNamespace

from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QFileDialog,
                           QMessageBox, QPushButton, QLabel, QLineEdit, QCheckBox,
                           QFormLayout, QHBoxLayout, QVBoxLayout, QTabWidget, QTextEdit,
                           QComboBox, QListWidget, QSplitter, QListView, QGroupBox,
                           QProgressBar, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QRunnable, QThreadPool, pyqtSignal, QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor

# Import worksheet generator functions (existing module)
from sat_worksheet_core import filter_questions, shuffle_options, \
    create_worksheet, validate_args, distribute_questions

# Constants
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'questions.db')


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(Exception)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)


class BaseWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()


class LoadQuestionsWorker(BaseWorker):
    def __init__(self, db_path, limit=100, offset=0, tags=None, difficulty=None):
        super().__init__()
        self.db_path = db_path
        self.limit = limit
        self.offset = offset
        self.tags = tags
        self.difficulty = difficulty

    def run(self):
        try:
            questions = db_utils.load_questions(
                self.db_path, 
                limit=self.limit, 
                offset=self.offset,
                tags=self.tags, 
                difficulty=self.difficulty
            )
            self.signals.result.emit(questions)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(e)


class SearchQuestionsWorker(BaseWorker):
    def __init__(self, db_path, search_text, limit=100, offset=0):
        super().__init__()
        self.db_path = db_path
        self.search_text = search_text
        self.limit = limit
        self.offset = offset

    def run(self):
        try:
            questions = db_utils.search_questions(
                self.db_path,
                self.search_text,
                limit=self.limit,
                offset=self.offset
            )
            self.signals.result.emit(questions)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(e)


class SaveQuestionWorker(BaseWorker):
    def __init__(self, db_path, question, is_new=False):
        super().__init__()
        self.db_path = db_path
        self.question = question
        self.is_new = is_new

    def run(self):
        try:
            success = db_utils.save_question(
                self.db_path,
                self.question,
                self.is_new
            )
            
            if success:
                self.signals.result.emit(self.question)
            else:
                self.signals.error.emit(Exception("Failed to save question"))
            
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(e)


class DeleteQuestionWorker(BaseWorker):
    def __init__(self, db_path, uid):
        super().__init__()
        self.db_path = db_path
        self.uid = uid

    def run(self):
        try:
            success = db_utils.delete_question(self.db_path, self.uid)
            
            if success:
                self.signals.result.emit(self.uid)
            else:
                self.signals.error.emit(Exception(f"Failed to delete question {self.uid}"))
                
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(e)


class GenerateWorksheetsWorker(BaseWorker):
    def __init__(self, db_path, question_uids, output_dir, worksheet_title, pages, n_max):
        super().__init__()
        self.db_path = db_path
        self.question_uids = question_uids
        self.output_dir = output_dir
        self.worksheet_title = worksheet_title
        self.pages = pages
        self.n_max = n_max

    def run(self):
        try:
            # Get questions from the database
            questions = db_utils.export_questions_to_list(self.db_path, self.question_uids)
            
            # Distribute questions across pages
            distributed_questions = distribute_questions(questions, self.pages, self.n_max)
            
            total_pages = len(distributed_questions)
            for i, page_questions in enumerate(distributed_questions, 1):
                self.signals.progress.emit(int((i / total_pages) * 100))
                
                base_name = self.worksheet_title.replace(' ', '_')
                output_file = os.path.join(self.output_dir, f"{base_name}_Page_{i}.pdf")
                create_worksheet(page_questions, output_file, f"{self.worksheet_title} - Page {i}")
                
                answer_key_file = os.path.join(self.output_dir, f"{base_name}_Page_{i}_answer_key.pdf")
                create_worksheet(page_questions, answer_key_file, 
                               f"{self.worksheet_title} - Page {i} (Answer Key)", 
                               include_answers=True)

            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(e)


class QuestionFormWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.original_data = None  # Store original question data

    def init_ui(self):
        form_layout = QFormLayout()
        
        # Question text
        self.question_text_edit = QTextEdit()
        self.question_text_edit.setPlaceholderText("Enter question text here")
        form_layout.addRow("Question Text:", self.question_text_edit)
        
        # Question image
        self.question_image_edit = QLineEdit()
        self.question_image_edit.setPlaceholderText("Path to question image (optional)")
        question_img_btn = QPushButton("Browse...")
        question_img_btn.clicked.connect(self.browse_question_image)
        hbox_qimg = QHBoxLayout()
        hbox_qimg.addWidget(self.question_image_edit)
        hbox_qimg.addWidget(question_img_btn)
        form_layout.addRow("Question Image:", hbox_qimg)
        
        # Options A-D
        self.option_edits = {}
        for opt in ['A', 'B', 'C', 'D']:
            # Text field
            text_edit = QLineEdit()
            text_edit.setPlaceholderText(f"Enter Option {opt} text")
            form_layout.addRow(f"Option {opt} Text:", text_edit)
            
            # Image field
            image_edit = QLineEdit()
            image_edit.setPlaceholderText(f"Path to Option {opt} image (optional)")
            img_btn = QPushButton("Browse...")
            img_btn.clicked.connect(lambda checked, e=image_edit: self.browse_option_image(e))
            hbox = QHBoxLayout()
            hbox.addWidget(image_edit)
            hbox.addWidget(img_btn)
            form_layout.addRow(f"Option {opt} Image:", hbox)
            
            self.option_edits[opt] = {'text': text_edit, 'image': image_edit}
        
        # Correct answer
        self.correct_answer_combo = QComboBox()
        self.correct_answer_combo.addItems(["A", "B", "C", "D"])
        form_layout.addRow("Correct Answer:", self.correct_answer_combo)
        
        # Difficulty
        self.difficulty_edit = QLineEdit()
        self.difficulty_edit.setPlaceholderText("e.g., Easy, Medium, Hard")
        form_layout.addRow("Difficulty:", self.difficulty_edit)
        
        # Tags
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Comma separated tags")
        form_layout.addRow("Tags (comma separated):", self.tags_edit)
        
        # Explanation
        self.explanation_text_edit = QTextEdit()
        self.explanation_text_edit.setPlaceholderText("Enter explanation text here")
        form_layout.addRow("Explanation Text:", self.explanation_text_edit)
        
        self.setLayout(form_layout)

    def browse_question_image(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Question Image", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if filename:
            self.question_image_edit.setText(filename)

    def browse_option_image(self, line_edit):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Option Image", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if filename:
            line_edit.setText(filename)

    def _compare_questions(self, q1: json_utils.Question, q2: json_utils.Question) -> bool:
        """Compare two questions for equality, avoiding nested object comparison."""
        if q1 is None or q2 is None:
            return q1 is q2

        # Convert both questions to dictionaries for flat comparison
        try:
            dict1 = q1.to_dict() if hasattr(q1, 'to_dict') else {}
            dict2 = q2.to_dict() if hasattr(q2, 'to_dict') else {}
            return dict1 == dict2
        except Exception:
            return False

    def get_question_data(self):
        """Get the current form data as a Question object."""
        # Create nested objects first
        content = json_utils.QuestionContent(
            text=self.question_text_edit.toPlainText().strip(),
            image=self.question_image_edit.text().strip() or None
        )
        
        options = {
            opt: json_utils.QuestionOption(
                text=self.option_edits[opt]['text'].text().strip(),
                image=self.option_edits[opt]['image'].text().strip() or None
            ) for opt in ['A', 'B', 'C', 'D']
        }
        
        explanation = json_utils.QuestionExplanation(
            text=self.explanation_text_edit.toPlainText().strip()
        )
        
        # Create Question object
        question = json_utils.Question(
            content=content,
            options=options,
            answer=self.correct_answer_combo.currentText(),
            difficulty=self.difficulty_edit.text().strip(),
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            explanation=explanation,
            uid=getattr(self.original_data, 'uid', None)
        )
        
        # Set dirty flag based on whether this is a new question or data has changed
        is_dirty = not self._compare_questions(question, self.original_data)
        question._dirty = is_dirty  # Add temporary attribute
        return question

    def set_question_data(self, question: json_utils.Question):
        """Set form data from a Question object."""
        if not question:
            self.clear()
            return
            
        # Store original question
        self.original_data = question
        
        # Set form fields
        self.question_text_edit.setPlainText(question.content.text)
        self.question_image_edit.setText(question.content.image or "")
        
        for opt, option_data in question.options.items():
            self.option_edits[opt]['text'].setText(option_data.text)
            self.option_edits[opt]['image'].setText(option_data.image or "")
        
        idx = self.correct_answer_combo.findText(question.answer)
        if idx >= 0:
            self.correct_answer_combo.setCurrentIndex(idx)
            
        self.difficulty_edit.setText(question.difficulty)
        self.tags_edit.setText(", ".join(question.tags))
        self.explanation_text_edit.setPlainText(question.explanation.text)

    def clear(self):
        """Clear all form fields and reset state."""
        self.question_text_edit.clear()
        self.question_image_edit.clear()
        
        for opt in self.option_edits.values():
            opt['text'].clear()
            opt['image'].clear()
            
        self.correct_answer_combo.setCurrentIndex(0)
        self.difficulty_edit.clear()
        self.tags_edit.clear()
        self.explanation_text_edit.clear()
        self.original_data = None


class DatabaseSelectionWidget(QWidget):
    db_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Database selection
        db_group = QGroupBox("Database Selection")
        db_layout = QVBoxLayout()
        
        # Default database option
        self.default_db_radio = QRadioButton("Use default database")
        self.default_db_radio.setChecked(True)
        db_layout.addWidget(self.default_db_radio)
        
        # Custom database option
        custom_db_layout = QHBoxLayout()
        self.custom_db_radio = QRadioButton("Use custom database:")
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setEnabled(False)
        db_browse_btn = QPushButton("Browse...")
        db_browse_btn.clicked.connect(self.browse_db_file)
        
        custom_db_layout.addWidget(self.custom_db_radio)
        custom_db_layout.addWidget(self.db_path_edit)
        custom_db_layout.addWidget(db_browse_btn)
        db_layout.addLayout(custom_db_layout)
        
        # Migration options
        migration_group = QGroupBox("Migration Tools")
        migration_layout = QVBoxLayout()
        
        # JSON to DB conversion
        json_to_db_layout = QHBoxLayout()
        self.json_path_edit = QLineEdit()
        self.json_path_edit.setPlaceholderText("Path to JSON file")
        json_browse_btn = QPushButton("Browse...")
        json_browse_btn.clicked.connect(self.browse_json_file)
        migrate_btn = QPushButton("Migrate JSON to DB")
        migrate_btn.clicked.connect(self.migrate_json_to_db)
        
        json_to_db_layout.addWidget(self.json_path_edit)
        json_to_db_layout.addWidget(json_browse_btn)
        json_to_db_layout.addWidget(migrate_btn)
        migration_layout.addLayout(json_to_db_layout)
        
        migration_group.setLayout(migration_layout)
        
        # Connect radio buttons
        self.db_group = QButtonGroup()
        self.db_group.addButton(self.default_db_radio)
        self.db_group.addButton(self.custom_db_radio)
        self.default_db_radio.toggled.connect(self.on_db_selection_changed)
        self.custom_db_radio.toggled.connect(self.on_db_selection_changed)
        
        # Add button to continue
        continue_btn = QPushButton("Continue to Question Manager")
        continue_btn.clicked.connect(self.on_continue)
        
        # Add layouts to the main widget
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)
        layout.addWidget(migration_group)
        layout.addWidget(continue_btn)
        
        self.setLayout(layout)
    
    def on_db_selection_changed(self):
        self.db_path_edit.setEnabled(self.custom_db_radio.isChecked())
    
    def browse_db_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select SQLite Database", "", "SQLite Database (*.db *.sqlite)")
        if filename:
            self.db_path_edit.setText(filename)
            self.custom_db_radio.setChecked(True)
    
    def browse_json_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select JSON File", "", "JSON Files (*.json)")
        if filename:
            self.json_path_edit.setText(filename)
    
    def migrate_json_to_db(self):
        json_path = self.json_path_edit.text().strip()
        if not json_path:
            QMessageBox.critical(self, "Error", "Please select a JSON file to migrate")
            return
        
        db_path = self.get_db_path()
        
        # Ask for confirmation
        reply = QMessageBox.question(
            self, 
            "Confirm Migration",
            f"This will migrate questions from {json_path} to {db_path}.\n\n"
            "If the database doesn't exist, it will be created.\n"
            "If it exists, questions will be added or updated.\n\n"
            "Do you want to continue?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Make sure the database directory exists
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                
                # Use the migration script
                from migrations.create_db import migrate_json_to_sqlite
                success = migrate_json_to_sqlite(json_path, db_path)
                
                if success:
                    QMessageBox.information(
                        self, 
                        "Migration Complete", 
                        f"Successfully migrated questions from {json_path} to {db_path}"
                    )
                else:
                    QMessageBox.critical(
                        self, 
                        "Migration Failed", 
                        f"Failed to migrate questions from {json_path}"
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Migration Error", 
                    f"An error occurred during migration: {str(e)}"
                )
    
    def get_db_path(self):
        """Get the currently selected database path"""
        if self.default_db_radio.isChecked():
            return DEFAULT_DB_PATH
        else:
            return self.db_path_edit.text().strip()
    
    def on_continue(self):
        db_path = self.get_db_path()
        
        # Validate the database exists or can be created
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error", 
                    f"Cannot create database directory: {str(e)}"
                )
                return
        
        # If custom DB is selected but no path provided
        if self.custom_db_radio.isChecked() and not db_path:
            QMessageBox.critical(
                self, 
                "Error", 
                "Please provide a database path or select the default database"
            )
            return
        
        # Check if the database exists, and if not, ask to create it
        if not os.path.exists(db_path):
            reply = QMessageBox.question(
                self, 
                "Create Database",
                f"Database {db_path} does not exist. Create it now?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                try:
                    from migrations.create_db import create_database
                    create_database(db_path)
                    QMessageBox.information(
                        self, 
                        "Database Created", 
                        f"Database created at {db_path}"
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self, 
                        "Error", 
                        f"Failed to create database: {str(e)}"
                    )
                    return
            else:
                return
        
        # Emit the signal with the selected database path
        self.db_selected.emit(db_path)


# Combined widget that uses the database for storage
class WorksheetAndQuestionManagerWidget(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.questions = []
        self.selected_questions = []
        self.current_question_index = None
        self.loading_more = False
        self.chunk_size = 50
        self.total_questions = 0
        self.current_offset = 0
        self.current_filter_tags = None
        self.current_filter_difficulty = None
        self.current_search_text = None
        # Initialize threadpool BEFORE UI setup
        self.threadpool = QThreadPool()
        self.init_ui()
        
        # Get initial count of questions
        self.update_question_count()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel(f"Database: {self.db_path}")
        self.count_label = QLabel("Loading...")
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.count_label)
        main_layout.addLayout(status_layout)
        
        # Main content layout with splitters
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Question List and Management
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        
        # Search/Filter
        filter_layout = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search questions...")
        self.filter_edit.returnPressed.connect(self.search_questions)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.search_questions)
        filter_layout.addWidget(self.filter_edit)
        filter_layout.addWidget(search_btn)
        left_layout.addLayout(filter_layout)
        
        # Advanced filter options
        adv_filter_layout = QHBoxLayout()
        
        # Tags combo
        self.tags_combo = QComboBox()
        self.tags_combo.setPlaceholderText("Select Tag")
        self.tags_combo.currentIndexChanged.connect(self.on_tag_filter_changed)
        adv_filter_layout.addWidget(QLabel("Tag:"))
        adv_filter_layout.addWidget(self.tags_combo)
        
        # Difficulty combo
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.setPlaceholderText("Select Difficulty")
        self.difficulty_combo.addItems(["", "Easy", "Medium", "Hard"])
        self.difficulty_combo.currentIndexChanged.connect(self.on_difficulty_filter_changed)
        adv_filter_layout.addWidget(QLabel("Difficulty:"))
        adv_filter_layout.addWidget(self.difficulty_combo)
        
        left_layout.addLayout(adv_filter_layout)
        
        # Question list
        self.model = QStandardItemModel()
        
        list_label = QLabel("Available Questions:")
        left_layout.addWidget(list_label)
        self.question_list = QListView()
        self.question_list.setModel(self.model)
        self.question_list.selectionModel().selectionChanged.connect(
            lambda: self.on_question_selected())
        self.question_list.setSelectionMode(QListView.ExtendedSelection)
        left_layout.addWidget(self.question_list)
        
        # Load more button
        self.load_more_btn = QPushButton("Load More Questions")
        self.load_more_btn.clicked.connect(self.load_more_questions)
        left_layout.addWidget(self.load_more_btn)
        
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
        self.add_to_selected_btn.clicked.connect(self.add_to_selected)
        self.remove_from_selected_btn = QPushButton("Remove from Worksheet")
        self.remove_from_selected_btn.clicked.connect(self.remove_from_selected)
        selection_buttons.addWidget(self.add_to_selected_btn)
        selection_buttons.addWidget(self.remove_from_selected_btn)
        left_layout.addLayout(selection_buttons)
        
        # Question management buttons
        qm_buttons = QHBoxLayout()
        add_btn = QPushButton("Add New Question")
        add_btn.clicked.connect(self.add_new_question)
        self.delete_btn = QPushButton("Delete Question")
        self.delete_btn.clicked.connect(self.delete_question)
        self.save_question_btn = QPushButton("Save Question")
        self.save_question_btn.clicked.connect(self.save_question)
        self.clear_fields_btn = QPushButton("Clear Fields")
        self.clear_fields_btn.clicked.connect(self.clear_fields)
        
        qm_buttons.addWidget(add_btn)
        qm_buttons.addWidget(self.delete_btn)
        qm_buttons.addWidget(self.save_question_btn)
        qm_buttons.addWidget(self.clear_fields_btn)
        left_layout.addLayout(qm_buttons)
        
        left_widget.setLayout(left_layout)
        
        # Middle - Question Form
        self.question_form = QuestionFormWidget()
        
        # Right side - Worksheet Generator
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        
        right_layout.addWidget(QLabel("Worksheet Generator"))
        
        # Worksheet settings form
        form_layout = QFormLayout()
        self.title_edit = QLineEdit("Worksheet")
        form_layout.addRow("Worksheet Title:", self.title_edit)
        
        self.worksheet_tags_edit = QLineEdit()
        form_layout.addRow("Tags (comma separated):", self.worksheet_tags_edit)
        
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
        
        right_layout.addLayout(form_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)
        
        # Generate button
        self.generate_btn = QPushButton("Generate Worksheets")
        self.generate_btn.clicked.connect(self.generate_worksheets)
        right_layout.addWidget(self.generate_btn)
        
        right_widget.setLayout(right_layout)
        
        # Add widgets to the splitter
        content_splitter.addWidget(left_widget)
        content_splitter.addWidget(self.question_form)
        content_splitter.addWidget(right_widget)
        
        # Set splitter sizes
        content_splitter.setSizes([300, 400, 300])
        
        # Add the splitter to the main layout
        main_layout.addWidget(content_splitter)
        
        self.setLayout(main_layout)
        
        # Initialize state of buttons
        self.save_question_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        self.remove_from_selected_btn.setEnabled(False)
        
        # Load initial data
        self.load_initial_data()
    
    def load_initial_data(self):
        """Load initial data for the widget"""
        # Load available tags
        self.load_tags()
        
        # Load first batch of questions
        self.load_questions()
    
    def load_tags(self):
        """Load available tags from the database"""
        try:
            tags = db_utils.get_all_tags(self.db_path)
            self.tags_combo.clear()
            self.tags_combo.addItem("")  # Empty option for no filter
            self.tags_combo.addItems(tags)
        except Exception as e:
            logging.error(f"Error loading tags: {str(e)}")
            QMessageBox.warning(self, "Warning", f"Failed to load tags: {str(e)}")
    
    def update_question_count(self):
        """Update the total question count"""
        try:
            # Ensure threadpool is initialized
            if not hasattr(self, 'threadpool'):
                self.threadpool = QThreadPool()
                
            count = db_utils.get_question_count(
                self.db_path,
                tags=self.current_filter_tags,
                difficulty=self.current_filter_difficulty
            )
            self.total_questions = count
            self.count_label.setText(f"Total Questions: {count}")
        except Exception as e:
            logging.error(f"Error getting question count: {str(e)}")
            self.count_label.setText("Count unavailable")
    
    def load_questions(self, clear_first=True):
        """Load questions from the database with current filters"""
        # Disable UI during load
        self.setEnabled(False)
        
        if clear_first:
            self.current_offset = 0
            self.questions = []
            self.model.clear()
        
        try:
            if self.current_search_text:
                # Use search function
                worker = SearchQuestionsWorker(
                    self.db_path,
                    self.current_search_text,
                    limit=self.chunk_size,
                    offset=self.current_offset
                )
            else:
                # Use regular load with filters
                worker = LoadQuestionsWorker(
                    self.db_path,
                    limit=self.chunk_size,
                    offset=self.current_offset,
                    tags=self.current_filter_tags,
                    difficulty=self.current_filter_difficulty
                )
            
            worker.signals.result.connect(lambda questions: self.handle_load_result(questions, clear_first))
            worker.signals.error.connect(self.handle_load_error)
            worker.signals.finished.connect(lambda: self.setEnabled(True))
            self.threadpool.start(worker)
        
        except Exception as e:
            self.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Failed to start loading questions: {str(e)}")
    
    def load_more_questions(self):
        """Load more questions from the database"""
        self.current_offset += self.chunk_size
        self.load_questions(clear_first=False)
    
    def handle_load_result(self, questions, clear_first=True):
        """Handle loaded questions"""
        if clear_first:
            self.questions = questions
        else:
            self.questions.extend(questions)
        
        self.update_question_list()
        self.update_load_more_button()
    
    def update_question_list(self):
        """Update the question list view"""
        # Clear model only if necessary to maintain selection
        if self.model.rowCount() == 0:
            self.model.clear()
        
        # Add each question to the model
        start_idx = self.model.rowCount()
        for i, question in enumerate(self.questions[start_idx:], start_idx):
            try:
                text = question.content.text if hasattr(question, 'content') else str(question)
                text = text[:50] + "..." if len(text) > 50 else text
                text = text if text else "Untitled Question"
            except (AttributeError, TypeError):
                text = "Untitled Question"
            
            display_text = f"{i+1}: {text}"
            item = QStandardItem(display_text)
            item.setData(question.uid, Qt.UserRole)
            self.model.appendRow(item)
    
    def update_load_more_button(self):
        """Update the Load More button based on available questions"""
        loaded_count = len(self.questions)
        self.load_more_btn.setEnabled(loaded_count < self.total_questions)
        self.load_more_btn.setText(
            f"Load More Questions ({loaded_count} of {self.total_questions} loaded)"
        )
    
    def handle_load_error(self, error):
        """Handle error when loading questions"""
        QMessageBox.critical(self, "Error", f"Failed to load questions: {str(error)}")
    
    def search_questions(self):
        """Search questions by text"""
        search_text = self.filter_edit.text().strip()
        self.current_search_text = search_text if search_text else None
        self.load_questions()
    
    def on_tag_filter_changed(self, index):
        """Handle tag filter change"""
        tag = self.tags_combo.currentText()
        self.current_filter_tags = [tag] if tag else None
        self.update_question_count()
        # Only reload if not in search mode
        if not self.current_search_text:
            self.load_questions()
    
    def on_difficulty_filter_changed(self, index):
        """Handle difficulty filter change"""
        difficulty = self.difficulty_combo.currentText()
        self.current_filter_difficulty = difficulty if difficulty else None
        self.update_question_count()
        # Only reload if not in search mode
        if not self.current_search_text:
            self.load_questions()
    
    def on_question_selected(self):
        """Handle question selection"""
        selected_indexes = self.question_list.selectedIndexes()
        if not selected_indexes:
            self.current_question_index = None
            self.question_form.clear()
            self.save_question_btn.setVisible(False)
            self.delete_btn.setVisible(False)
            return
        
        # Only load the first selected question into the form
        selected_index = selected_indexes[0]
        model_index = selected_index
        question_uid = model_index.data(Qt.UserRole)
        self.commit_current_question()
        
        # Find question index in our list
        for i, q in enumerate(self.questions):
            if q.uid == question_uid:
                self.current_question_index = i
                break
        
        if self.current_question_index is not None:
            question = self.questions[self.current_question_index]
            self.question_form.set_question_data(question)
            self.save_question_btn.setVisible(True)
            self.delete_btn.setVisible(True)
    
    def commit_current_question(self):
        """Check if current question is dirty and save if needed"""
        if self.current_question_index is None:
            return
            
        updated_data = self.question_form.get_question_data()
        if hasattr(updated_data, '_dirty') and updated_data._dirty:
            self.save_question()  # Use unified save logic
    
    def add_new_question(self):
        """Handler for Add Question button clicks"""
        self.current_question_index = None  # Signify creating new question
        self.question_form.clear()  # Clear the form
        self.save_question_btn.setVisible(True)  # Show save button
        self.delete_btn.setVisible(False)  # Hide delete button
        self.question_list.clearSelection()  # Deselect any selected question
    
    def save_question(self):
        """Save the current question"""
        try:
            # Get question object
            question = self.question_form.get_question_data()
            is_dirty = getattr(question, '_dirty', True)
            if hasattr(question, '_dirty'):
                delattr(question, '_dirty')
            
            if not is_dirty:
                return
            
            # Determine if this is a new question
            is_new = self.current_question_index is None
            
            # Disable UI during save
            self.setEnabled(False)
            QApplication.processEvents()
            
            # Create and run worker
            worker = SaveQuestionWorker(self.db_path, question, is_new)
            worker.signals.result.connect(self.handle_save_result)
            worker.signals.error.connect(self.handle_save_error)
            worker.signals.finished.connect(lambda: self.setEnabled(True))
            self.threadpool.start(worker)
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process question data: {str(e)}")
            self.setEnabled(True)
    
    def handle_save_result(self, question):
        """Handle successful question save"""
        is_new = self.current_question_index is None
        
        if is_new:
            # Add to the beginning of the list and model
            self.questions.insert(0, question)
            
            # Update model
            item = QStandardItem(f"1: {question.content.text[:50]}...")
            item.setData(question.uid, Qt.UserRole)
            self.model.insertRow(0, item)
            
            # Renumber items
            for i in range(1, self.model.rowCount()):
                old_text = self.model.item(i).text()
                new_text = f"{i+1}: {old_text.split(':', 1)[1].strip()}"
                self.model.item(i).setText(new_text)
        else:
            # Update existing question
            self.questions[self.current_question_index] = question
            
            # Update model item
            for i in range(self.model.rowCount()):
                if self.model.item(i).data(Qt.UserRole) == question.uid:
                    self.model.item(i).setText(f"{i+1}: {question.content.text[:50]}...")
                    break
        
        # Update the total count
        self.update_question_count()
        
        # Update the form with the saved question
        self.question_form.set_question_data(question)
        
        # Show success message
        QMessageBox.information(self, "Success", "Question saved successfully!")
    
    def handle_save_error(self, error):
        """Handle error when saving a question"""
        QMessageBox.critical(self, "Error", f"Failed to save question: {str(error)}")
    
    def delete_question(self):
        """Delete the current question"""
        if self.current_question_index is None:
            return
            
        reply = QMessageBox.question(
            self, "Delete Question",
            "Are you sure you want to delete this question?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            question = self.questions[self.current_question_index]
            
            # Disable UI during delete
            self.setEnabled(False)
            QApplication.processEvents()
            
            # Create and run worker
            worker = DeleteQuestionWorker(self.db_path, question.uid)
            worker.signals.result.connect(self.handle_delete_result)
            worker.signals.error.connect(self.handle_delete_error)
            worker.signals.finished.connect(lambda: self.setEnabled(True))
            self.threadpool.start(worker)
    
    def handle_delete_result(self, uid):
        """Handle successful question deletion"""
        if self.current_question_index is not None:
            # Find and remove from the model
            for i in range(self.model.rowCount()):
                if self.model.item(i).data(Qt.UserRole) == uid:
                    self.model.removeRow(i)
                    break
            
            # Remove from the questions list
            self.questions.pop(self.current_question_index)
            self.current_question_index = None
            
            # Update the total count
            self.update_question_count()
            
            # Clear form and update UI
            self.question_form.clear()
            self.save_question_btn.setVisible(False)
            self.delete_btn.setVisible(False)
            
            # Show success message
            QMessageBox.information(self, "Success", "Question deleted successfully!")
    
    def handle_delete_error(self, error):
        """Handle error when deleting a question"""
        QMessageBox.critical(self, "Error", f"Failed to delete question: {str(error)}")
    
    def clear_fields(self):
        """Clear all form fields and reset state"""
        self.question_form.clear()
        self.save_question_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        self.question_list.clearSelection()
    
    def add_to_selected(self):
        """Add selected questions to the worksheet list"""
        selected_indexes = self.question_list.selectedIndexes()
        if not selected_indexes:
            return
        
        # Create selected_questions list if it doesn't exist
        if not hasattr(self, 'selected_questions'):
            self.selected_questions = []
        
        # Get all currently selected questions
        added = 0
        for index in selected_indexes:
            uid = index.data(Qt.UserRole)
            
            # Find the question with this UID
            for question in self.questions:
                if question.uid == uid and question not in self.selected_questions:
                    self.selected_questions.append(question)
                    added += 1
                    break
        
        # Update the selected questions list
        self.update_selected_list()
        
        # Clear selection and update UI
        self.question_list.clearSelection()
        self.remove_from_selected_btn.setEnabled(len(self.selected_questions) > 0)
        
        if added > 0:
            QMessageBox.information(self, "Success", 
                f"Added {added} question{'s' if added > 1 else ''} to worksheet")
    
    def remove_from_selected(self):
        """Remove questions from the selected list"""
        selected_indexes = self.selected_list.selectedIndexes()
        if not selected_indexes or not self.selected_questions:
            return
        
        # Get the indexes in reverse order to avoid index shifting
        indexes = sorted([index.row() for index in selected_indexes], reverse=True)
        
        # Remove questions
        for index in indexes:
            if 0 <= index < len(self.selected_questions):
                self.selected_questions.pop(index)
        
        # Update the UI
        self.update_selected_list()
        self.remove_from_selected_btn.setEnabled(len(self.selected_questions) > 0)
    
    def update_selected_list(self):
        """Update the selected questions list view"""
        self.selected_model.clear()
        
        if not self.selected_questions:
            return
        
        for i, question in enumerate(self.selected_questions):
            try:
                text = question.content.text[:50] + "..." if len(question.content.text) > 50 else question.content.text
                item = QStandardItem(f"{i+1}: {text}")
                item.setData(question.uid, Qt.UserRole)
                self.selected_model.appendRow(item)
            except (AttributeError, TypeError):
                item = QStandardItem(f"{i+1}: Untitled Question")
                self.selected_model.appendRow(item)
    
    def browse_output_dir(self):
        """Browse for output directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", os.getcwd())
        if directory:
            self.output_dir_edit.setText(directory)
    
    def generate_worksheets(self):
        """Generate worksheets using selected questions"""
        if not self.questions:
            QMessageBox.critical(self, "Error", "No questions loaded. Please load questions first.")
            return
        
        questions_to_use = self.selected_questions if self.selected_questions else self.questions
        if not questions_to_use:
            QMessageBox.critical(self, "Error", "No questions available for worksheet.")
            return
        
        try:
            # Get and validate numeric inputs
            worksheet_title = self.title_edit.text().strip() or "Worksheet"
            tags = [t.strip() for t in self.worksheet_tags_edit.text().split(",")] if self.worksheet_tags_edit.text().strip() else []
            
            try:
                num_questions = int(self.num_questions_edit.text().strip()) if self.num_questions_edit.text().strip() else None
                pages = int(self.pages_edit.text().strip())
                n_max = int(self.n_max_edit.text().strip())
            except ValueError:
                QMessageBox.critical(self, "Error", "Please enter valid numeric values for number of questions, pages, and max questions.")
                return
            
            # Filter by tags if specified
            if tags:
                filtered_questions = [q for q in questions_to_use if any(tag in q.tags for tag in tags)]
                if not filtered_questions:
                    QMessageBox.critical(self, "Error", f"No questions match the specified tags: {', '.join(tags)}")
                    return
                questions_to_use = filtered_questions
            
            # Limit number of questions if specified
            if num_questions is not None:
                if num_questions <= 0:
                    QMessageBox.critical(self, "Error", "Number of questions must be positive.")
                    return
                if num_questions > len(questions_to_use):
                    QMessageBox.critical(self, "Error", 
                        f"Requested number of questions ({num_questions}) exceeds available questions ({len(questions_to_use)}).")
                    return
                questions_to_use = questions_to_use[:num_questions]
            
            # Shuffle if requested
            if self.shuffle_checkbox.isChecked():
                questions_to_use = [q for q in questions_to_use]  # Create a copy
                random.shuffle(questions_to_use)
            
            # Get question UIDs
            question_uids = [q.uid for q in questions_to_use]
            
            # Validate output directory
            output_dir = self.output_dir_edit.text().strip()
            if not os.path.isdir(output_dir):
                QMessageBox.critical(self, "Error", "Output directory does not exist!")
                return
            
            # Show progress bar
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            
            # Create worksheets
            self.setEnabled(False)  # Disable entire UI
            worker = GenerateWorksheetsWorker(
                self.db_path,
                question_uids, 
                output_dir, 
                worksheet_title, 
                pages, 
                n_max
            )
            worker.signals.finished.connect(self.handle_generate_finished)
            worker.signals.error.connect(self.handle_generate_error)
            worker.signals.progress.connect(self.update_progress)
            self.threadpool.start(worker)
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
    
    def handle_generate_finished(self):
        """Handle worksheet generation completion"""
        self.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "Success", "Worksheets generated successfully!")
    
    def handle_generate_error(self, error):
        """Handle worksheet generation error"""
        self.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", f"An error occurred: {str(error)}")
    
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAT Question Manager & Worksheet Generator")
        self.setMinimumSize(1200, 800)
        self.init_ui()

    def init_ui(self):
        # Start with the database selection widget
        self.db_selection_widget = DatabaseSelectionWidget()
        self.db_selection_widget.db_selected.connect(self.on_db_selected)
        self.setCentralWidget(self.db_selection_widget)
    
    def on_db_selected(self, db_path):
        # Create the question manager widget with the selected database
        self.question_manager = WorksheetAndQuestionManagerWidget(db_path)
        self.setCentralWidget(self.question_manager)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()