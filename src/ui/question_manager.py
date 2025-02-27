#!/usr/bin/env python3
"""
Question management interface
"""
import os
from typing import List, Set, Dict, Any, Optional, Union, Tuple, cast
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                            QLineEdit, QPushButton, QSplitter, QFileDialog,
                            QMessageBox, QApplication)
from PyQt5.QtCore import Qt, QThreadPool
import logging
from types import SimpleNamespace

# Import subcomponents
from src.ui.question_form import QuestionFormWidget
from src.ui.components.question_list_panel import QuestionListPanel
from src.ui.components.worksheet_generator_panel import WorksheetGeneratorPanel
from src.ui.components.progress_dialog import ProgressDialog
from src.ui.workers.question_workers import (LoadQuestionsWorker, SaveQuestionWorker, 
                                           DeleteQuestionWorker, SearchQuestionsWorker,
                                           ImportQuestionsWorker)
from src.ui.db_selection import DatabaseSelectionDialog
from src.utils.config import load_config, save_config
from src.core.db.operations import export_questions_to_list
from src.ui.error_handler import ErrorHandler

# Combined widget that merges WorksheetGeneratorWidget and QuestionManagerWidget
class WorksheetAndQuestionManagerWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.questions: List[SimpleNamespace] = []
        self.selected_questions: List[SimpleNamespace] = []
        self.excluded_question_uids: Set[str] = set()
        self.current_question_index: Optional[int] = None
        self.db_path: Optional[str] = None
        self.config: Dict[str, Any] = load_config()
        self.loading_more: bool = False
        self.chunk_size: int = 100
        self.threadpool: QThreadPool = QThreadPool()
        self.error_handler = ErrorHandler(self)
        self.init_ui()
        
    def init_ui(self) -> None:
        main_layout = QVBoxLayout()
        
        # Database selection group
        db_group = QGroupBox("Database Selection")
        db_layout = QHBoxLayout()
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setPlaceholderText("Select SQLite database")
        self.db_path_edit.setReadOnly(True)
        db_btn = QPushButton("Select Database...")
        db_btn.clicked.connect(self.select_database)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load_questions)
        import_btn = QPushButton("Import JSON...")
        import_btn.clicked.connect(self.import_from_json)
        db_layout.addWidget(self.db_path_edit)
        db_layout.addWidget(db_btn)
        db_layout.addWidget(load_btn)
        db_layout.addWidget(import_btn)
        db_group.setLayout(db_layout)
        main_layout.addWidget(db_group)
        
        # Main content layout with splitters
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Question List and Management
        self.question_list_panel = QuestionListPanel()
        self.question_list_panel.question_selected.connect(self.on_question_selected)
        self.question_list_panel.delete_question_requested.connect(self.delete_question)
        self.question_list_panel.questions_added_to_worksheet.connect(self.add_to_selected)
        self.question_list_panel.questions_removed_from_worksheet.connect(self.remove_from_selected)
        
        # Middle - Question Form
        self.question_form = QuestionFormWidget()
        self.question_form.save_question_requested.connect(self.save_question_from_form)
        self.question_form.clear_form_requested.connect(self.clear_fields)
        self.question_form.new_question_requested.connect(self.create_new_question)
        
        # Right side - Worksheet Generator
        self.worksheet_generator = WorksheetGeneratorPanel()
        self.worksheet_generator.generate_worksheets_requested.connect(self.generate_worksheets)
        
        # Add widgets to the splitter
        content_splitter.addWidget(self.question_list_panel)
        content_splitter.addWidget(self.question_form)
        content_splitter.addWidget(self.worksheet_generator)
        
        # Set splitter sizes
        content_splitter.setSizes([300, 400, 300])
        
        # Add the splitter to the main layout
        main_layout.addWidget(content_splitter)
        
        self.setLayout(main_layout)
        
        # Try to load default database if present
        default_db = self.config.get("default_db_path")
        if default_db and os.path.exists(default_db):
            self.db_path = default_db
            self.db_path_edit.setText(default_db)
            self.load_questions()
    
    def select_database(self) -> None:
        """Open database selection dialog"""
        dialog = DatabaseSelectionDialog(self)
        dialog.db_selected.connect(self.on_database_selected)
        dialog.exec_()
    
    def on_database_selected(self, db_path: str) -> None:
        """Handle database selection"""
        if db_path and os.path.exists(db_path):
            self.db_path = db_path
            self.db_path_edit.setText(db_path)
            self.load_questions()
    
    def load_questions(self) -> None:
        """Load questions from the database"""
        if not self.db_path:
            self.error_handler.show_error("Error", "Please select a database.")
            return
            
        # Create and show progress dialog
        self.progress_dialog = ProgressDialog("Loading Questions", self)
        self.progress_dialog.update_status("Loading questions from database...")
        self.progress_dialog.show()
        
        self.setEnabled(False)  # Disable the UI while loading
            
        try:
            # Create and run worker
            worker = LoadQuestionsWorker(self.db_path, limit=self.chunk_size)
            worker.signals.result.connect(self.handle_load_result)
            worker.signals.error.connect(self.handle_load_error)
            worker.signals.progress.connect(self.progress_dialog.update_progress)
            worker.signals.status_update.connect(self.progress_dialog.update_status)
            worker.signals.finished.connect(self.handle_load_finished)
            self.threadpool.start(worker)
        except Exception as e:
            self.setEnabled(True)
            self.progress_dialog.accept()
            self.error_handler.handle_exception(e, "Error", "Failed to start loading questions")
    
    def handle_load_result(self, questions: List[SimpleNamespace]) -> None:
        self.questions = questions
        self.question_list_panel.set_questions(self.questions, self.excluded_question_uids)
        # Result message will be shown after progress dialog closes in handle_load_finished
    
    def handle_load_error(self, error: str) -> None:
        self.progress_dialog.accept()  # Close progress dialog on error
        self.setEnabled(True)
        self.error_handler.show_error("Error", "Failed to load questions", error)
    
    def handle_load_finished(self) -> None:
        self.progress_dialog.accept()  # Close progress dialog when finished
        self.setEnabled(True)
        # Only show success message if questions were loaded
        if hasattr(self, 'questions') and self.questions:
            self.error_handler.show_info("Success", f"Loaded {len(self.questions)} questions successfully!")
    
    def on_question_selected(self, question_uid: str) -> None:
        self.commit_current_question()
        
        # Find question index in our list
        for i, q in enumerate(self.questions):
            if q.uid == question_uid:
                self.current_question_index = i
                break
        
        if self.current_question_index is not None:
            question = self.questions[self.current_question_index]
            self.question_form.set_question_data(question)
    
    def commit_current_question(self) -> None:
        """Check if current question is dirty and save if needed."""
        if self.current_question_index is None:
            return
            
        updated_data = self.question_form.get_question_data()
        if hasattr(updated_data, '_dirty') and updated_data._dirty:
            self.save_question()  # Use unified save logic
    
    def delete_question(self) -> None:
        if self.current_question_index is None:
            return
            
        if self.error_handler.confirm("Delete Question", "Are you sure you want to delete this question?"):
            question = self.questions[self.current_question_index]
            worker = DeleteQuestionWorker(
                self.db_path,
                question.uid
            )
            worker.signals.finished.connect(self.handle_delete_finished)
            worker.signals.error.connect(self.handle_delete_error)
            self.threadpool.start(worker)
    
    def handle_delete_finished(self) -> None:
        if self.current_question_index is not None:
            deleted_question = self.questions[self.current_question_index]
            # Remove from the questions list
            self.questions.pop(self.current_question_index)
            self.current_question_index = None
            self.question_list_panel.set_questions(self.questions, self.excluded_question_uids)
            self.question_form.clear()

            # Show success message
            self.error_handler.show_info("Success", "Question deleted successfully!")
            
            # Signal to the list panel to clear selection
            self.question_list_panel.clear_selection()
    
    def handle_delete_error(self, error: str) -> None:
        self.error_handler.show_error("Error", "Failed to delete question", error)
    
    def save_question(self) -> None:
        """Save the current question, handling both new questions and updates."""
        if not self.db_path:
            self.error_handler.show_error("Error", "Please select a database first.")
            return

        try:
            # Get question object
            question = self.question_form.get_question_data()
            is_dirty = getattr(question, '_dirty', True)
            if hasattr(question, '_dirty'):
                delattr(question, '_dirty')
            
            if not is_dirty:
                return

            # Show progress dialog
            self.progress_dialog = ProgressDialog("Saving Question", self)
            self.progress_dialog.update_status("Saving question to database...")
            self.progress_dialog.show()

            try:
                is_new = self.current_question_index is None
                
                if not is_new:
                    # Update existing
                    existing_question = self.questions[self.current_question_index]
                    question.uid = existing_question.uid

                worker = SaveQuestionWorker(
                    self.db_path, question, is_new
                )
                worker.signals.result.connect(self.handle_save_result)
                worker.signals.error.connect(self.handle_save_error)
                worker.signals.finished.connect(lambda: self.setEnabled(True))
                self.threadpool.start(worker)

            except Exception as e:
                self.progress_dialog.accept()
                self.error_handler.handle_exception(e, "Error", "Failed to save question")
                return

        except Exception as e:
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.accept()
            self.error_handler.handle_exception(e, "Error", "Failed to process question data")
    
    def handle_save_result(self, question: SimpleNamespace) -> None:
        if self.current_question_index is None:
            self.questions.append(question)
        else:
            self.questions[self.current_question_index] = question

        # Update UI
        self.question_list_panel.set_questions(self.questions, self.excluded_question_uids)
        self.error_handler.show_info("Success", "Question saved successfully!")
    
    def handle_save_error(self, error: str) -> None:
        self.error_handler.show_error("Error", "Failed to save question", error)
    
    def clear_fields(self) -> None:
        """Clear all form fields and reset state."""
        self.question_form.clear()
    
    def add_to_selected(self, questions: List[str]) -> None:
        """Add selected questions to the worksheet list."""
        selected_question_objects: List[SimpleNamespace] = []
        for uid in questions:
            for q in self.questions:
                if q.uid == uid:
                    selected_question_objects.append(q)
                    break
        
        self.selected_questions.extend([q for q in selected_question_objects if q not in self.selected_questions])
        self.question_list_panel.update_selected_list(self.selected_questions)
    
    def remove_from_selected(self, indices: List[int]) -> None:
        """Remove questions from the selected list."""
        if not indices or not self.selected_questions:
            return
        
        # Get the indexes in reverse order to avoid index shifting
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self.selected_questions):
                self.selected_questions.pop(index)
        
        # Update the UI
        self.question_list_panel.update_selected_list(self.selected_questions)
    
    def generate_worksheets(self) -> None:
        """Generate worksheets using selected questions."""
        if not self.questions:
            self.error_handler.show_error("Error", "No questions loaded. Please load questions first.")
            return
        
        questions_to_use: List[SimpleNamespace] = self.selected_questions if self.selected_questions else self.questions
        if not questions_to_use:
            self.error_handler.show_error("Error", "No questions available for worksheet.")
            return
        
        try:
            # Get worksheet generation parameters from the panel
            worksheet_params = self.worksheet_generator.get_worksheet_parameters()
            
            # Filter by tags if specified
            if worksheet_params.tags:
                filtered_questions = [q for q in questions_to_use if any(tag in q.tags for tag in worksheet_params.tags)]
                if not filtered_questions:
                    self.error_handler.show_error("Error", 
                        f"No questions match the specified tags: {', '.join(worksheet_params.tags)}")
                    return
                questions_to_use = filtered_questions
            
            # Limit number of questions if specified
            if worksheet_params.num_questions is not None:
                if worksheet_params.num_questions <= 0:
                    self.error_handler.show_error("Error", "Number of questions must be positive.")
                    return
                if worksheet_params.num_questions > len(questions_to_use):
                    self.error_handler.show_error("Error", 
                        f"Requested number of questions ({worksheet_params.num_questions}) exceeds available questions ({len(questions_to_use)}).")
                    return
                questions_to_use = questions_to_use[:worksheet_params.num_questions]
            
            # Shuffle if requested
            if worksheet_params.shuffle:
                import random
                questions_to_use = [q for q in questions_to_use]  # Create a copy
                random.shuffle(questions_to_use)
            
            # Show progress dialog
            self.progress_dialog = ProgressDialog("Generating Worksheets", self)
            self.progress_dialog.update_status("Preparing worksheet content...")
            self.progress_dialog.show()
        
            # Start the worksheet generation process
            from src.ui.workers.worksheet_workers import GenerateWorksheetsWorker, shuffle_options
            
            # Export questions to dictionary format for worksheet generation
            question_uids = [q.uid for q in questions_to_use]
            worksheet_questions = export_questions_to_list(self.db_path, question_uids)
            
            # Shuffle options within each question
            for q in worksheet_questions:
                shuffle_options(q)
            
            worker = GenerateWorksheetsWorker(
                worksheet_questions, 
                worksheet_params.output_dir, 
                worksheet_params.title, 
                worksheet_params.pages, 
                worksheet_params.n_max
            )
            worker.signals.finished.connect(self.handle_generate_finished)
            worker.signals.error.connect(self.handle_generate_error)
            worker.signals.progress.connect(self.progress_dialog.update_progress)
            worker.signals.status_update.connect(self.progress_dialog.update_status)
            self.threadpool.start(worker)
            
        except Exception as e:
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.accept()
            self.error_handler.handle_exception(e, "Error", "An error occurred during worksheet generation")
    
    def handle_generate_finished(self) -> None:
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.accept()
        self.error_handler.show_info("Success", "Worksheets generated successfully!")
    
    def handle_generate_error(self, error: str) -> None:
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.accept()
        self.error_handler.show_error("Error", "An error occurred during worksheet generation", error)
    
    def update_progress(self, value: int) -> None:
        # Could be expanded to use a progress bar in the future
        pass

    def save_question_from_form(self, question: SimpleNamespace, is_new: bool) -> None:
        """Save a question coming directly from the form widget."""
        if not self.db_path:
            self.error_handler.show_error("Error", "Please select a database first.")
            return

        try:
            # Show progress dialog
            self.progress_dialog = ProgressDialog("Saving Question", self)
            self.progress_dialog.update_status("Saving question to database...")
            self.progress_dialog.show()

            try:
                worker = SaveQuestionWorker(
                    self.db_path, question, is_new
                )
                worker.signals.result.connect(self.handle_save_result)
                worker.signals.error.connect(self.handle_save_error)
                worker.signals.finished.connect(lambda: self.setEnabled(True))
                self.threadpool.start(worker)

            except Exception as e:
                self.progress_dialog.accept()
                self.error_handler.handle_exception(e, "Error", "Failed to save question")
                return

        except Exception as e:
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.accept()
            self.error_handler.handle_exception(e, "Error", "Failed to process question data")
            
    def import_from_json(self) -> None:
        """Import questions from a JSON file into the database"""
        if not self.db_path:
            self.error_handler.show_error("Error", "Please select a database first.")
            return
            
        # Open file dialog to select JSON file
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select JSON File", "", "JSON Files (*.json)"
        )
        
        if not file_path:
            return  # User canceled
            
        # Show confirmation dialog
        if not self.error_handler.confirm("Import Questions", 
                                        f"Are you sure you want to import questions from {os.path.basename(file_path)}?"):
            return
            
        # Create and show progress dialog
        self.progress_dialog = ProgressDialog("Importing Questions", self)
        self.progress_dialog.update_status("Importing questions from JSON file...")
        self.progress_dialog.show()
        
        self.setEnabled(False)  # Disable the UI while importing
        
        try:
            # Create and run worker
            worker = ImportQuestionsWorker(file_path, self.db_path)
            worker.signals.result.connect(self.handle_import_result)
            worker.signals.error.connect(self.handle_import_error)
            worker.signals.progress.connect(self.progress_dialog.update_progress)
            worker.signals.status_update.connect(self.progress_dialog.update_status)
            worker.signals.finished.connect(self.handle_import_finished)
            self.threadpool.start(worker)
        except Exception as e:
            self.setEnabled(True)
            self.progress_dialog.accept()
            self.error_handler.handle_exception(e, "Error", "Failed to start importing questions")
    
    def handle_import_result(self, imported_count: int) -> None:
        """Handle successful import of questions"""
        # Reload questions to include the newly imported ones
        self.load_questions()
        # Message will be shown in handle_import_finished
    
    def handle_import_error(self, error: str) -> None:
        """Handle error during import"""
        self.progress_dialog.accept()  # Close progress dialog on error
        self.setEnabled(True)
        self.error_handler.show_error("Error", "Failed to import questions", error)
    
    def handle_import_finished(self) -> None:
        """Handle completion of import process"""
        self.progress_dialog.accept()  # Close progress dialog when finished
        self.setEnabled(True)

    def create_new_question(self) -> None:
        """Create a new question by clearing the form and resetting the current index."""
        if not self.db_path:
            self.error_handler.show_error("Error", "Please select a database first.")
            return

        # Check if there's an unsaved current question and ask to save
        if self.current_question_index is not None:
            updated_data = self.question_form.get_question_data()
            if hasattr(updated_data, '_dirty') and updated_data._dirty:
                reply = QMessageBox.question(
                    self, "Save Changes",
                    "Do you want to save changes to the current question?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                
                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Yes:
                    self.save_question()

        # Reset current question index to indicate we're creating a new one
        self.current_question_index = None
        
        # Clear the form for a new question
        self.question_form.clear()
        
        # Clear selection in the question list panel
        self.question_list_panel.clear_selection()