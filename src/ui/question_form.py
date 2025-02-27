#!/usr/bin/env python3
"""
Question form for adding and editing questions
"""
from PyQt5.QtWidgets import (QWidget, QFormLayout, QTextEdit, QLineEdit, 
                            QPushButton, QHBoxLayout, QComboBox, QFileDialog,
                            QVBoxLayout, QMessageBox)
from PyQt5.QtCore import pyqtSignal
from src.models.question import Question, QuestionContent, QuestionOption, QuestionExplanation

class QuestionFormWidget(QWidget):
    # Define signals for question form actions
    save_question_requested = pyqtSignal(object, bool)  # Question object, is_new flag
    clear_form_requested = pyqtSignal()
    new_question_requested = pyqtSignal()  # New signal for new question request
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.original_data = None  # Store original question data
        self._dirty = False

    def init_ui(self):
        main_layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # Question text
        self.question_text_edit = QTextEdit()
        self.question_text_edit.setPlaceholderText("Enter question text here")
        self.question_text_edit.textChanged.connect(lambda: self.mark_dirty())
        form_layout.addRow("Question Text:", self.question_text_edit)
        
        # Question image
        self.question_image_edit = QLineEdit()
        self.question_image_edit.setPlaceholderText("Path to question image (optional)")
        self.question_image_edit.textChanged.connect(lambda: self.mark_dirty())
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
            text_edit.textChanged.connect(lambda: self.mark_dirty())
            form_layout.addRow(f"Option {opt} Text:", text_edit)
            
            # Image field
            image_edit = QLineEdit()
            image_edit.setPlaceholderText(f"Path to Option {opt} image (optional)")
            image_edit.textChanged.connect(lambda: self.mark_dirty())
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
        self.correct_answer_combo.currentIndexChanged.connect(lambda: self.mark_dirty())
        form_layout.addRow("Correct Answer:", self.correct_answer_combo)
        
        # Difficulty
        self.difficulty_edit = QLineEdit()
        self.difficulty_edit.setPlaceholderText("e.g., Easy, Medium, Hard")
        self.difficulty_edit.textChanged.connect(lambda: self.mark_dirty())
        form_layout.addRow("Difficulty:", self.difficulty_edit)
        
        # Tags
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Comma separated tags")
        self.tags_edit.textChanged.connect(lambda: self.mark_dirty())
        form_layout.addRow("Tags (comma separated):", self.tags_edit)
        
        # Explanation
        self.explanation_text_edit = QTextEdit()
        self.explanation_text_edit.setPlaceholderText("Enter explanation text here")
        self.explanation_text_edit.textChanged.connect(lambda: self.mark_dirty())
        form_layout.addRow("Explanation Text:", self.explanation_text_edit)
        
        main_layout.addLayout(form_layout)
        
        # Add buttons at the bottom
        button_layout = QHBoxLayout()
        self.new_btn = QPushButton("New Question")
        self.new_btn.clicked.connect(self.new_question_requested)
        self.save_btn = QPushButton("Save Question")
        self.save_btn.clicked.connect(self.request_save)
        self.clear_btn = QPushButton("Clear Form")
        self.clear_btn.clicked.connect(self.request_clear)
        
        button_layout.addWidget(self.new_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.clear_btn)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)

    def browse_question_image(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Question Image", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if filename:
            self.question_image_edit.setText(filename)
            self.mark_dirty()

    def browse_option_image(self, line_edit):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Option Image", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if filename:
            line_edit.setText(filename)
            self.mark_dirty()

    def _compare_questions(self, q1: Question, q2: Question) -> bool:
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
        content = QuestionContent(
            text=self.question_text_edit.toPlainText().strip(),
            image=self.question_image_edit.text().strip() or None
        )
        
        options = {
            opt: QuestionOption(
                text=self.option_edits[opt]['text'].text().strip(),
                image=self.option_edits[opt]['image'].text().strip() or None
            ) for opt in ['A', 'B', 'C', 'D']
        }
        
        explanation = QuestionExplanation(
            text=self.explanation_text_edit.toPlainText().strip()
        )
        
        # Create Question object
        question = Question(
            content=content,
            options=options,
            answer=self.correct_answer_combo.currentText(),
            difficulty=self.difficulty_edit.text().strip(),
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            explanation=explanation,
            uid=getattr(self.original_data, 'uid', None)
        )
        
        # Set dirty flag based on whether this is a new question or data has changed
        is_dirty = self._dirty
        question._dirty = is_dirty  # Add temporary attribute
        return question

    def set_question_data(self, question: Question):
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
        
        # Reset dirty state since we just loaded the data
        self._dirty = False

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
        self._dirty = False
    
    def mark_dirty(self):
        """Mark the form as having unsaved changes"""
        self._dirty = True
    
    def request_save(self):
        """Handle save button click by validating and emitting signal"""
        # Basic validation
        if not self.question_text_edit.toPlainText().strip():
            QMessageBox.warning(self, "Validation Error", "Question text cannot be empty")
            return
        
        # Check required options
        empty_options = []
        for opt in ['A', 'B', 'C', 'D']:
            if not self.option_edits[opt]['text'].text().strip():
                empty_options.append(opt)
        
        if empty_options:
            QMessageBox.warning(self, "Validation Error", 
                                f"Option{'s' if len(empty_options) > 1 else ''} {', '.join(empty_options)} cannot be empty")
            return
        
        # Create question object
        question = self.get_question_data()
        
        # Determine if this is a new question
        is_new = self.original_data is None
        
        # Emit signal with question and is_new flag
        self.save_question_requested.emit(question, is_new)
    
    def request_clear(self):
        """Handle clear button click by emitting signal"""
        if self._dirty:
            reply = QMessageBox.question(self, "Confirm Clear", 
                                        "There are unsaved changes. Are you sure you want to clear the form?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        self.clear_form_requested.emit()
        self.clear()