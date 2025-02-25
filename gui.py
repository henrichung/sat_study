#!/usr/bin/env python3
"""
PyQt GUI for the SAT Worksheet Generator and SAT Question Generator.
This application provides a unified interface for:
  • Managing questions (add, edit, delete)
  • Generating worksheets from selected questions
"""
import sys
import os
import random
import json
import json_utils
import logging
from types import SimpleNamespace

from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QFileDialog,
                           QMessageBox, QPushButton, QLabel, QLineEdit, QCheckBox,
                           QFormLayout, QHBoxLayout, QVBoxLayout, QTabWidget, QTextEdit,
                           QComboBox, QListWidget, QSplitter, QListView, QGroupBox)
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QRunnable, QThreadPool, pyqtSignal, QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor

# Import worksheet generator functions (existing module)
from sat_worksheet_core import load_questions, filter_questions, shuffle_options, \
    create_worksheet, validate_args, distribute_questions


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
    def __init__(self, json_file):
        super().__init__()
        self.json_file = json_file

    def run(self):
        try:
            questions = json_utils.load_questions(self.json_file)
            self.signals.result.emit(questions)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(e)

class SaveQuestionWorker(BaseWorker):
    def __init__(self, json_file, question, index_file=None, index=None, is_new=False):
        super().__init__()
        self.json_file = json_file
        self.question = question
        self.index_file = index_file
        self.index = index
        self.is_new = is_new

    def run(self):
        try:
            if self.is_new:
                json_utils.append_question(self.json_file, self.question)
            else:
                json_utils.save_questions(self.json_file, [self.question])

            # Modified index handling
            if self.index is not None and self.index_file:
                if self.question.uid not in self.index:
                    self.index.append(self.question.uid)
                json_utils.save_index(self.index, self.index_file)

            self.signals.result.emit(self.question)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(e)

class DeleteQuestionWorker(BaseWorker):
    def __init__(self, json_file, uid, index_file=None, index=None):
        super().__init__()
        self.json_file = json_file
        self.uid = uid
        self.index_file = index_file
        self.index = index

    def run(self):
        try:
            json_utils.delete_question(self.json_file, self.index, self.uid)
            
            if self.index is not None:
                # Remove the UID from the index list if it exists
                if self.uid in self.index:
                    self.index.remove(self.uid)
                    if self.index_file:
                        json_utils.save_index(self.index, self.index_file)

            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(e)

class GenerateWorksheetsWorker(BaseWorker):
    def __init__(self, questions, output_dir, worksheet_title, pages, n_max):
        super().__init__()
        self.questions = questions
        self.output_dir = output_dir
        self.worksheet_title = worksheet_title
        self.pages = pages
        self.n_max = n_max

    def run(self):
        try:
            distributed_questions = distribute_questions(self.questions, self.pages, self.n_max)
            
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

# Combined widget that merges WorksheetGeneratorWidget and QuestionManagerWidget
class WorksheetAndQuestionManagerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.questions = []
        self.selected_questions = []
        self.excluded_question_uids = set()
        self.current_question_index = None
        self.json_file_path = None
        self.index_file_path = None
        self.index = None
        self.loading_more = False
        self.chunk_size = 100
        self.init_ui()
        self.threadpool = QThreadPool()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # File selection group
        file_group = QGroupBox("Question File Selection")
        file_layout = QHBoxLayout()
        self.json_file_edit = QLineEdit()
        self.json_file_edit.setPlaceholderText("Select JSON file with questions")
        json_btn = QPushButton("Browse...")
        json_btn.clicked.connect(self.browse_json_file)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load_questions)
        file_layout.addWidget(self.json_file_edit)
        file_layout.addWidget(json_btn)
        file_layout.addWidget(load_btn)
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # Main content layout with splitters
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Question List and Management
        left_widget = QWidget()
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
        self.question_list.selectionModel().selectionChanged.connect(
            lambda: self.on_question_selected())
        self.question_list.wheelEvent = self.on_list_wheel
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
        
        right_layout.addLayout(form_layout)
        
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

    # Methods from QuestionManagerWidget
    def browse_json_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select JSON File", "", "JSON Files (*.json)")
        if filename:
            self.json_file_edit.setText(filename)
            # No longer load questions here, wait for user to click Load button
    
    def load_questions(self):
        self.json_file_path = self.json_file_edit.text().strip()
        if not self.json_file_path:
            QMessageBox.critical(self, "Error", "Please select a JSON file.")
            return
            
        # Set index file path
        base, ext = os.path.splitext(self.json_file_path)
        self.index_file_path = f"{base}_index{ext}"
            
        # Disable UI
        self.setEnabled(False)
        
        try:
            # Create and run worker
            worker = LoadQuestionsWorker(self.json_file_path)
            worker.signals.result.connect(self.handle_load_result)
            worker.signals.error.connect(self.handle_load_error)
            worker.signals.finished.connect(lambda: self.setEnabled(True))
            self.threadpool.start(worker)
        except Exception as e:
            self.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Failed to start loading questions: {str(e)}")
    
    def handle_load_result(self, questions):
        self.questions = questions
        self.index = self.initialize_index()
        self.populate_list()
        QMessageBox.information(self, "Success", f"Loaded {len(questions)} questions successfully!")
    
    def handle_load_error(self, error):
        QMessageBox.critical(self, "Error", f"Failed to load questions: {str(error)}")
    
    def initialize_index(self):
        """Initialize or load the question index for the current JSON file."""
        if not self.index_file_path:
            return []
            
        try:
            if os.path.exists(self.index_file_path):
                index = json_utils.load_index(self.index_file_path)
                # Ensure index is a list of UIDs
                if isinstance(index, dict):
                    index = list(index.keys())
                return index if isinstance(index, list) else []
            else:
                # Create new index as list of UIDs
                questions = json_utils.load_questions(self.json_file_path)
                index = [q.uid for q in questions]
                json_utils.save_index(index, self.index_file_path)
                return index
                
        except Exception as e:
            QMessageBox.warning(self, "Index Error", 
                f"Failed to initialize index:\n{str(e)}\nUsing empty index.")
            return []
    
    def populate_list(self):
        """Populate the list with Question objects, accounting for excluded questions."""
        self.model.clear()
        for i, question in enumerate(self.questions):
            # Skip excluded questions
            if question.uid in self.excluded_question_uids:
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
    
    def on_question_selected(self):
        """Handle question selection."""
        selected_indexes = self.question_list.selectedIndexes()
        if not selected_indexes:
            self.current_question_index = None
            self.question_form.clear()
            self.save_question_btn.setVisible(False)
            self.delete_btn.setVisible(False)
            return
        
        # Only load the first selected question into the form
        selected_index = selected_indexes[0]
        model_index = self.proxyModel.mapToSource(selected_index)
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
        """Check if current question is dirty and save if needed."""
        if self.current_question_index is None:
            return
            
        updated_data = self.question_form.get_question_data()
        if hasattr(updated_data, '_dirty') and updated_data._dirty:
            self.save_question()  # Use unified save logic
    
    def delete_question(self):
        if self.current_question_index is None:
            return
            
        reply = QMessageBox.question(
            self, "Delete Question",
            "Are you sure you want to delete this question?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            question = self.questions[self.current_question_index]
            worker = DeleteQuestionWorker(
                self.json_file_path, 
                question.uid,
                self.index_file_path, 
                self.index
            )
            worker.signals.finished.connect(self.handle_delete_finished)
            worker.signals.error.connect(self.handle_delete_error)
            self.threadpool.start(worker)
    
    def handle_delete_finished(self):
        if self.current_question_index is not None:
            deleted_question = self.questions[self.current_question_index]
            # Remove from the questions list
            self.questions.pop(self.current_question_index)
            self.current_question_index = None
            self.populate_list()
            self.question_form.clear()

            # Show success message
            QMessageBox.information(self, "Success", "Question deleted successfully!")
            
            # Clear any selections
            self.question_list.clearSelection()
            self.save_question_btn.setVisible(False)
            self.delete_btn.setVisible(False)
    
    def handle_delete_error(self, error):
        QMessageBox.critical(self, "Error", f"Failed to delete question: {str(error)}")
    
    def save_changes(self):
        """Save index changes on application exit."""
        if self.index is not None and self.index_file_path:
            try:
                json_utils.save_index(self.index, self.index_file_path)
            except Exception as e:
                logging.error(f"Failed to save index on exit: {str(e)}")
    
    def on_list_wheel(self, event):
        QListView.wheelEvent(self.question_list, event)
        
        scrollbar = self.question_list.verticalScrollBar()
        if (scrollbar.value() >= scrollbar.maximum() - 50
            and not self.loading_more 
            and self.index):
            
            self.loading_more = True
            try:
                # Calculate which UIDs to load next
                current_uids = {q.uid for q in self.questions}
                next_uids = [uid for uid in self.index if uid not in current_uids][:self.chunk_size]
                
                # Load next chunk of questions
                for uid in next_uids:
                    question = json_utils.get_question_by_uid(self.json_file_path, uid)
                    if question:
                        self.questions.append(question)
                
                if next_uids:
                    self.populate_list()
            finally:
                self.loading_more = False
    
    def add_new_question(self):
        """Handler for Add Question button clicks."""
        self.current_question_index = None  # Signify creating new question
        self.question_form.clear()  # Clear the form
        self.save_question_btn.setVisible(True)  # Show save button
        self.delete_btn.setVisible(False)  # Hide delete button
        self.question_list.clearSelection()  # Deselect any selected question
    
    def save_question(self):
        """Save the current question, handling both new questions and updates."""
        if not self.json_file_path:
            QMessageBox.critical(self, "Error", "Please select a JSON file first.")
            return

        try:
            # Get question object
            question = self.question_form.get_question_data()
            is_dirty = getattr(question, '_dirty', True)
            if hasattr(question, '_dirty'):
                delattr(question, '_dirty')
            
            if not is_dirty:
                return

            # Disable UI during save
            self.setEnabled(False)
            QApplication.processEvents()

            try:
                if self.current_question_index is None:
                    # New question
                    is_new = True
                else:
                    # Update existing
                    existing_question = self.questions[self.current_question_index]
                    question.uid = existing_question.uid
                    is_new = False

                worker = SaveQuestionWorker(
                    self.json_file_path, question, 
                    self.index_file_path, self.index, 
                    is_new
                )
                worker.signals.result.connect(self.handle_save_result)
                worker.signals.error.connect(self.handle_save_error)
                worker.signals.finished.connect(lambda: self.setEnabled(True))
                self.threadpool.start(worker)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save question: {str(e)}")
                self.setEnabled(True)
                return

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process question data: {str(e)}")
            self.setEnabled(True)
    
    def handle_save_result(self, question):
        if self.current_question_index is None:
            self.questions.append(question)
            if self.index is not None and question.uid not in self.index:
                self.index.append(question.uid)
        else:
            self.questions[self.current_question_index] = question
            if self.index is not None and question.uid not in self.index:
                self.index.append(question.uid)

        # Save index
        if self.index is not None and self.index_file_path:
            json_utils.save_index(self.index, self.index_file_path)

        # Update UI
        self.populate_list()
        QMessageBox.information(self, "Success", "Question saved successfully!")
    
    def handle_save_error(self, error):
        QMessageBox.critical(self, "Error", f"Failed to save question: {str(error)}")
    
    def clear_fields(self):
        """Clear all form fields and reset state."""
        self.question_form.clear()
        self.save_question_btn.setVisible(False)
        self.delete_btn.setVisible(False)
    
    def filter_questions(self):
        search_text = self.filter_edit.text()
        self.proxyModel.setFilterRegExp(search_text)
    
    # Methods for worksheet generation
    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", os.getcwd())
        if directory:
            self.output_dir_edit.setText(directory)
    
    def add_to_selected(self):
        """Add selected questions to the worksheet list."""
        selected_indexes = self.question_list.selectedIndexes()
        if not selected_indexes:
            return
        
        # Create selected_questions list if it doesn't exist
        if not hasattr(self, 'selected_questions'):
            self.selected_questions = []
        
        # Get all currently selected questions
        added = 0
        for index in selected_indexes:
            proxy_index = index
            source_index = self.proxyModel.mapToSource(proxy_index)
            uid = source_index.data(Qt.UserRole)
            
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
        """Remove questions from the selected list."""
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
        """Update the selected questions list view."""
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
    
    def generate_worksheets(self):
        """Generate worksheets using selected questions."""
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
            tags = [t.strip() for t in self.tags_edit.text().split(",")] if self.tags_edit.text().strip() else []
            
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
            
            # Shuffle options within each question and convert to dictionary format
            worksheet_questions = [shuffle_options(q.to_dict()) for q in questions_to_use]
            
            # Validate output directory
            output_dir = self.output_dir_edit.text().strip()
            if not os.path.isdir(output_dir):
                QMessageBox.critical(self, "Error", "Output directory does not exist!")
                return
            
            # Validate arguments
            args = SimpleNamespace(
                num_questions=num_questions,
                pages=pages,
                n_max=n_max,
                tags=tags,
                json_file=self.json_file_path  # Needed for validate_args function
            )
            
            # Create worksheets
            self.setEnabled(False)  # Disable entire UI instead of just the button
            worker = GenerateWorksheetsWorker(
                worksheet_questions, output_dir, 
                worksheet_title, pages, n_max
            )
            worker.signals.finished.connect(self.handle_generate_finished)
            worker.signals.error.connect(self.handle_generate_error)
            worker.signals.progress.connect(self.update_progress)
            self.threadpool.start(worker)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
    
    def handle_generate_finished(self):
        self.setEnabled(True)  # Re-enable the entire UI
        QMessageBox.information(self, "Success", "Worksheets generated successfully!")
    
    def handle_generate_error(self, error):
        self.setEnabled(True)  # Re-enable the entire UI
        QMessageBox.critical(self, "Error", f"An error occurred: {str(error)}")
    
    def update_progress(self, value):
        # Could be expanded to use a progress bar in the future
        pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAT Question Manager & Worksheet Generator")
        self.setMinimumSize(1200, 800)
        self.init_ui()

    def init_ui(self):
        # Use the new merged widget as the central widget
        central_widget = WorksheetAndQuestionManagerWidget()
        self.setCentralWidget(central_widget)
        
        # Connect aboutToQuit signal to save_changes
        QApplication.instance().aboutToQuit.connect(central_widget.save_changes)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()