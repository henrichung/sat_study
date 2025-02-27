from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QTextEdit, QComboBox, QPushButton,
                             QGroupBox, QFormLayout, QScrollArea, QFrame)
from PyQt5.QtCore import Qt
from src.models.question import Question, QuestionContent, QuestionOption, QuestionExplanation
import uuid

class QuestionFormWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._dirty = False
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        scroll_content = QWidget()
        form_layout = QVBoxLayout(scroll_content)
        
        # Question content group
        content_group = QGroupBox("Question Content")
        content_layout = QFormLayout()
        
        self.question_text = QTextEdit()
        self.question_text.setPlaceholderText("Enter question text here...")
        self.question_text.setMinimumHeight(100)
        self.question_text.textChanged.connect(self.mark_dirty)
        content_layout.addRow("Text:", self.question_text)
        
        self.question_image = QLineEdit()
        self.question_image.setPlaceholderText("Optional: path to image file")
        self.question_image.textChanged.connect(self.mark_dirty)
        content_layout.addRow("Image:", self.question_image)
        
        content_group.setLayout(content_layout)
        form_layout.addWidget(content_group)
        
        # Options group
        options_group = QGroupBox("Answer Options")
        options_layout = QFormLayout()
        
        # Add fields for options A-E
        self.option_widgets = {}
        for key in ['A', 'B', 'C', 'D', 'E']:
            option_layout = QVBoxLayout()
            option_text = QTextEdit()
            option_text.setPlaceholderText(f"Enter text for option {key}...")
            option_text.setMaximumHeight(80)
            option_text.textChanged.connect(self.mark_dirty)
            
            option_image = QLineEdit()
            option_image.setPlaceholderText(f"Optional: path to image for option {key}")
            option_image.textChanged.connect(self.mark_dirty)
            
            option_layout.addWidget(option_text)
            option_layout.addWidget(option_image)
            
            self.option_widgets[key] = {
                'text': option_text,
                'image': option_image
            }
            
            options_layout.addRow(f"Option {key}:", QWidget())
            options_layout.setWidget(options_layout.rowCount() - 1, QFormLayout.FieldRole, QWidget())
            options_layout.itemAt(options_layout.rowCount() - 1, QFormLayout.FieldRole).widget().setLayout(option_layout)
        
        options_group.setLayout(options_layout)
        form_layout.addWidget(options_group)
        
        # Answer and metadata group
        metadata_group = QGroupBox("Answer & Metadata")
        metadata_layout = QFormLayout()
        
        self.answer_dropdown = QComboBox()
        self.answer_dropdown.addItems(['A', 'B', 'C', 'D', 'E'])
        self.answer_dropdown.currentTextChanged.connect(self.mark_dirty)
        metadata_layout.addRow("Correct Answer:", self.answer_dropdown)
        
        self.difficulty_dropdown = QComboBox()
        self.difficulty_dropdown.addItems(['Easy', 'Medium', 'Hard', 'Very Hard'])
        self.difficulty_dropdown.currentTextChanged.connect(self.mark_dirty)
        metadata_layout.addRow("Difficulty:", self.difficulty_dropdown)
        
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Enter tags separated by commas (e.g., algebra,equations,linear)")
        self.tags_input.textChanged.connect(self.mark_dirty)
        metadata_layout.addRow("Tags:", self.tags_input)
        
        metadata_group.setLayout(metadata_layout)
        form_layout.addWidget(metadata_group)
        
        # Explanation group
        explanation_group = QGroupBox("Explanation")
        explanation_layout = QVBoxLayout()
        
        self.explanation_text = QTextEdit()
        self.explanation_text.setPlaceholderText("Enter explanation for the correct answer...")
        self.explanation_text.setMinimumHeight(100)
        self.explanation_text.textChanged.connect(self.mark_dirty)
        explanation_layout.addWidget(self.explanation_text)
        
        explanation_group.setLayout(explanation_layout)
        form_layout.addWidget(explanation_group)
        
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        self.setLayout(main_layout)
    
    def mark_dirty(self):
        """Mark the form as modified."""
        self._dirty = True
    
    def clear(self):
        """Clear all form fields."""
        self.question_text.clear()
        self.question_image.clear()
        
        for key in self.option_widgets:
            self.option_widgets[key]['text'].clear()
            self.option_widgets[key]['image'].clear()
        
        self.answer_dropdown.setCurrentIndex(0)
        self.difficulty_dropdown.setCurrentIndex(0)
        self.tags_input.clear()
        self.explanation_text.clear()
        self._dirty = False
    
    def set_question_data(self, question):
        """Populate form with question data."""
        # Block signals temporarily to avoid triggering dirty state
        self.blockSignals(True)
        
        # Set question content
        self.question_text.setText(question.content.text)
        self.question_image.setText(question.content.image or "")
        
        # Set options
        for key in self.option_widgets:
            if key in question.options:
                self.option_widgets[key]['text'].setText(question.options[key].text)
                self.option_widgets[key]['image'].setText(question.options[key].image or "")
            else:
                self.option_widgets[key]['text'].clear()
                self.option_widgets[key]['image'].clear()
        
        # Set answer
        index = self.answer_dropdown.findText(question.answer)
        if index >= 0:
            self.answer_dropdown.setCurrentIndex(index)
        
        # Set difficulty
        index = self.difficulty_dropdown.findText(question.difficulty)
        if index >= 0:
            self.difficulty_dropdown.setCurrentIndex(index)
        
        # Set tags
        self.tags_input.setText(", ".join(question.tags))
        
        # Set explanation
        self.explanation_text.setText(question.explanation.text)
        
        # Unblock signals
        self.blockSignals(False)
        
        # Reset dirty state
        self._dirty = False
    
    def get_question_data(self):
        """Get question data from form."""
        # Create content
        content = QuestionContent(
            text=self.question_text.toPlainText(),
            image=self.question_image.text() if self.question_image.text() else None
        )
        
        # Create options
        options = {}
        for key in self.option_widgets:
            text = self.option_widgets[key]['text'].toPlainText()
            if text:  # Only add non-empty options
                options[key] = QuestionOption(
                    text=text,
                    image=self.option_widgets[key]['image'].text() if self.option_widgets[key]['image'].text() else None
                )
        
        # Get tags
        tags_text = self.tags_input.text()
        tags = [tag.strip() for tag in tags_text.split(',')] if tags_text else []
        
        # Create explanation
        explanation = QuestionExplanation(
            text=self.explanation_text.toPlainText()
        )
        
        # Create question
        question = Question(
            content=content,
            options=options,
            answer=self.answer_dropdown.currentText(),
            difficulty=self.difficulty_dropdown.currentText(),
            tags=tags,
            explanation=explanation,
            uid=None  # Will be set later
        )
        
        # Add dirty flag
        question._dirty = self._dirty
        
        return question