#!/usr/bin/env python3
"""
PyQt GUI for the SAT Worksheet Generator and SAT Question Generator.
This application now provides three tabs:
  • Worksheet Generator
  • Question Generator
  • Question Manager (new): Browse, filter, edit, and delete questions.
"""
import sys
import os
import random
import json
import json_utils
from types import SimpleNamespace

from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QFileDialog,
                             QMessageBox, QPushButton, QLabel, QLineEdit, QCheckBox,
                             QFormLayout, QHBoxLayout, QVBoxLayout, QTabWidget, QTextEdit,
                             QComboBox, QListWidget, QSplitter, QListView)
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QRunnable, QThreadPool, pyqtSignal, QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem

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

# -------------------- Worksheet Generator Widget -------------------- #
class WorksheetGeneratorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.all_questions = []  # Add this line
        self.init_ui()
        self.threadpool = QThreadPool()
    
    def init_ui(self):
        # (Existing code unchanged)
        form_layout = QFormLayout()
        self.json_file_edit = QLineEdit()
        json_btn = QPushButton("Browse...")
        json_btn.clicked.connect(self.browse_json_file)
        hbox_json = QHBoxLayout()
        hbox_json.addWidget(self.json_file_edit)
        hbox_json.addWidget(json_btn)
        form_layout.addRow("JSON File:", hbox_json)
        self.title_edit = QLineEdit("Worksheet")
        form_layout.addRow("Worksheet Title:", self.title_edit)
        self.tags_edit = QLineEdit()
        form_layout.addRow("Tags (comma separated):", self.tags_edit)
        self.num_questions_edit = QLineEdit()
        form_layout.addRow("Number of Questions (optional):", self.num_questions_edit)
        self.shuffle_checkbox = QCheckBox("Shuffle Questions")
        form_layout.addRow(self.shuffle_checkbox)
        self.pages_edit = QLineEdit("1")
        form_layout.addRow("Number of Pages:", self.pages_edit)
        self.n_max_edit = QLineEdit("100")
        form_layout.addRow("Max Questions per Worksheet:", self.n_max_edit)
        self.output_dir_edit = QLineEdit(os.getcwd())
        out_btn = QPushButton("Browse...")
        out_btn.clicked.connect(self.browse_output_dir)
        hbox_out = QHBoxLayout()
        hbox_out.addWidget(self.output_dir_edit)
        hbox_out.addWidget(out_btn)
        form_layout.addRow("Output Directory:", hbox_out)
        self.generate_btn = QPushButton("Generate Worksheets")
        self.generate_btn.clicked.connect(self.generate_worksheets)
        vbox = QVBoxLayout()
        vbox.addLayout(form_layout)
        vbox.addWidget(self.generate_btn)
        self.setLayout(vbox)
    
    def browse_json_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select JSON File", "", "JSON Files (*.json)")
        if filename:
            try:
                # Load questions once when file is selected
                self.all_questions = json_utils.load_questions(filename)
                self.json_file_edit.setText(filename)
                QMessageBox.information(self, "Success", f"Loaded {len(self.all_questions)} questions successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load questions:\n{str(e)}")
                self.all_questions = []
                self.json_file_edit.clear()
    
    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", os.getcwd())
        if directory:
            self.output_dir_edit.setText(directory)
    
    def generate_worksheets(self):
        if not self.all_questions:
            QMessageBox.critical(self, "Error", "No questions loaded! Please select a JSON file first.")
            return

        worksheet_title = self.title_edit.text().strip() or "Worksheet"
        tags = [t.strip() for t in self.tags_edit.text().split(",")] if self.tags_edit.text().strip() else []
        
        try:
            num_questions = int(self.num_questions_edit.text().strip()) if self.num_questions_edit.text().strip() else None
            pages = int(self.pages_edit.text().strip())
            n_max = int(self.n_max_edit.text().strip())
        except ValueError:
            QMessageBox.critical(self, "Error", "Please enter valid numeric values for number of questions, pages, and max questions.")
            return
        
        output_dir = self.output_dir_edit.text().strip()
        if not os.path.isdir(output_dir):
            QMessageBox.critical(self, "Error", "Output directory does not exist!")
            return
        
        try:
            # Use already loaded questions instead of loading again
            filtered_questions = filter_questions(self.all_questions, tags)
            
            if self.shuffle_checkbox.isChecked():
                random.shuffle(filtered_questions)
            
            filtered_questions = [shuffle_options(q) for q in filtered_questions]
            
            if num_questions:
                filtered_questions = filtered_questions[:num_questions]
            
            args = SimpleNamespace(
                json_file=self.json_file_edit.text().strip(),
                num_questions=num_questions,
                pages=pages,
                n_max=n_max,
                tags=tags
            )
            validate_args(args, len(filtered_questions))
            self.generate_btn.setEnabled(False)
            worker = GenerateWorksheetsWorker(
                filtered_questions, output_dir, 
                worksheet_title, pages, n_max
            )
            worker.signals.finished.connect(self.handle_generate_finished)
            worker.signals.error.connect(self.handle_generate_error)
            worker.signals.progress.connect(self.update_progress)
            self.threadpool.start(worker)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")

    def handle_generate_finished(self):
        self.generate_btn.setEnabled(True)
        QMessageBox.information(self, "Success", "Worksheets generated successfully!")

    def handle_generate_error(self, error):
        self.generate_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"An error occurred:\n{str(error)}")

    def update_progress(self, value):
        # Optional: Add progress bar to show worksheet generation progress
        pass

# -------------------- New: Question Manager Widget -------------------- #
class QuestionManagerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.questions = []
        self.current_question_index = None
        self.json_file_path = None
        self.index_file_path = None
        self.index = None
        self.loading_more = False
        self.chunk_size = 100
        self.init_ui()
        self.threadpool = QThreadPool()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # JSON file selection
        file_layout = QHBoxLayout()
        self.json_file_edit = QLineEdit()
        self.json_file_edit.setPlaceholderText("Select JSON file to browse/edit")
        json_btn = QPushButton("Browse...")
        json_btn.clicked.connect(self.browse_json_file)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load_questions)
        file_layout.addWidget(self.json_file_edit)
        file_layout.addWidget(json_btn)
        file_layout.addWidget(load_btn)
        layout.addLayout(file_layout)
        
        # Search/Filter
        filter_layout = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search questions...")
        self.filter_edit.textChanged.connect(self.filter_questions)
        filter_layout.addWidget(self.filter_edit)
        layout.addLayout(filter_layout)
        
        # Split view: list on left, form on right
        splitter = QSplitter(Qt.Horizontal)
        
        # Question list
        self.model = QStandardItemModel()
        self.proxyModel = QSortFilterProxyModel()
        self.proxyModel.setSourceModel(self.model)
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        
        self.question_list = QListView()
        self.question_list.setModel(self.proxyModel)
        self.question_list.selectionModel().selectionChanged.connect(
            lambda: self.on_question_selected())
        self.question_list.wheelEvent = self.on_list_wheel
        splitter.addWidget(self.question_list)
        
        # Question form
        self.question_form = QuestionFormWidget()
        splitter.addWidget(self.question_form)
        
        layout.addWidget(splitter)
        
        # Buttons
        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add Question")
        add_btn.clicked.connect(self.add_new_question)
        self.delete_btn = QPushButton("Delete Question")  # Store as instance variable
        self.delete_btn.clicked.connect(self.delete_question)
        self.save_question_btn = QPushButton("Save")
        self.save_question_btn.clicked.connect(self.save_question)  # Connect to new method
        self.save_question_btn.setVisible(False)
        self.clear_fields_btn = QPushButton("Clear Fields")
        self.clear_fields_btn.clicked.connect(self.clear_fields)
        
        button_layout.addWidget(add_btn)
        button_layout.addWidget(self.delete_btn)  # Use instance variable
        button_layout.addWidget(self.save_question_btn)
        button_layout.addWidget(self.clear_fields_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def browse_json_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select JSON File", "", "JSON Files (*.json)")
        if filename:
            self.json_file_edit.setText(filename)

    def filter_questions(self):
        search_text = self.filter_edit.text()
        self.proxyModel.setFilterRegExp(search_text)

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
        
        # Create and run worker
        worker = LoadQuestionsWorker(self.json_file_path)
        worker.signals.result.connect(self.handle_load_result)
        worker.signals.error.connect(self.handle_load_error)
        worker.signals.finished.connect(lambda: self.setEnabled(True))
        self.threadpool.start(worker)

    def handle_load_result(self, questions):
        self.questions = questions
        self.index = self.initialize_index()
        self.populate_list()

    def handle_load_error(self, error):
        QMessageBox.critical(self, "Error", f"Failed to load questions: {str(error)}")

    def populate_list(self):
        """Populate the list with Question objects."""
        self.model.clear()
        for i, question in enumerate(self.questions):
            # Safely extract question text for display
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
            return
        
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
        if updated_data._dirty:
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
        json_utils.save_index(self.index, self.index_file_path)

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
                return

            finally:
                self.setEnabled(True)
                QApplication.processEvents()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process question data: {str(e)}")

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

    def save_changes(self):
        """Save index changes on application exit."""
        if self.index is not None and self.index_file_path:
            try:
                json_utils.save_index(self.index, self.index_file_path)
            except Exception as e:
                logging.error(f"Failed to save index on exit: {str(e)}")

    def clear_fields(self):
        """Clear all form fields and reset state."""
        self.question_form.clear()
                
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAT Worksheet & Question Generator")
        self.setMinimumSize(600, 400)
        self.init_ui()

    def init_ui(self):
        # Remove duplicate init_ui call
        tab_widget = QTabWidget()
        worksheet_tab = WorksheetGeneratorWidget()
        question_manager_tab = QuestionManagerWidget()
        tab_widget.addTab(worksheet_tab, "Worksheet Generator")
        tab_widget.addTab(question_manager_tab, "Question Manager")
        self.setCentralWidget(tab_widget)
        
        # Connect aboutToQuit signal to save_changes
        QApplication.instance().aboutToQuit.connect(question_manager_tab.save_changes)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
