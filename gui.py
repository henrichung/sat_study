#!/usr/bin/env python3
"""
PyQt GUI for the SAT Worksheet Generator and SAT Question Generator.
This application now provides three tabs:
  • Worksheet Generator
  • Question Generator
  • Question Browser (new): Browse, filter, edit, and delete questions.
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
from PyQt5.QtCore import Qt, QSortFilterProxyModel
from PyQt5.QtGui import QStandardItemModel, QStandardItem

# Import worksheet generator functions (existing module)
from sat_worksheet_core import load_questions, filter_questions, shuffle_options, \
    create_worksheet, validate_args, distribute_questions

# Import core functions for question browsing/editing
from question_browser_core import load_questions as load_qs, save_questions

class QuestionFormWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

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

    def get_question_data(self):
        return {
            "question": {
                "text": self.question_text_edit.toPlainText().strip(),
                "image": self.question_image_edit.text().strip()
            },
            "options": {
                opt: {
                    "text": self.option_edits[opt]['text'].text().strip(),
                    "image": self.option_edits[opt]['image'].text().strip()
                } for opt in ['A', 'B', 'C', 'D']
            },
            "answer": self.correct_answer_combo.currentText(),
            "difficulty": self.difficulty_edit.text().strip(),
            "tags": [t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            "explanation": {
                "text": self.explanation_text_edit.toPlainText().strip()
            }
        }

    def set_question_data(self, question):
        if not question:
            self.clear()
            return

        self.question_text_edit.setPlainText(question.get("question", {}).get("text", ""))
        self.question_image_edit.setText(question.get("question", {}).get("image", ""))
        
        options = question.get("options", {})
        for opt in ['A', 'B', 'C', 'D']:
            option_data = options.get(opt, {})
            if isinstance(option_data, str):  # Handle legacy format
                self.option_edits[opt]['text'].setText(option_data)
                self.option_edits[opt]['image'].setText("")
            else:
                self.option_edits[opt]['text'].setText(option_data.get("text", ""))
                self.option_edits[opt]['image'].setText(option_data.get("image", ""))
        
        answer = question.get("answer", "A")
        idx = self.correct_answer_combo.findText(answer)
        if idx >= 0:
            self.correct_answer_combo.setCurrentIndex(idx)
            
        self.difficulty_edit.setText(question.get("difficulty", ""))
        self.tags_edit.setText(", ".join(question.get("tags", [])))
        self.explanation_text_edit.setPlainText(question.get("explanation", {}).get("text", ""))

    def clear(self):
        self.question_text_edit.clear()
        self.question_image_edit.clear()
        for opt in ['A', 'B', 'C', 'D']:
            self.option_edits[opt]['text'].clear()
            self.option_edits[opt]['image'].clear()
        self.correct_answer_combo.setCurrentIndex(0)
        self.difficulty_edit.clear()
        self.tags_edit.clear()
        self.explanation_text_edit.clear()

# -------------------- Worksheet Generator Widget -------------------- #
class WorksheetGeneratorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
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
            self.json_file_edit.setText(filename)
    
    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", os.getcwd())
        if directory:
            self.output_dir_edit.setText(directory)
    
    def generate_worksheets(self):
        json_path = self.json_file_edit.text().strip()
        if not os.path.exists(json_path):
            QMessageBox.critical(self, "Error", "JSON file not found!")
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
            questions = load_questions(json_path)
            filtered_questions = filter_questions(questions, tags)
            
            if self.shuffle_checkbox.isChecked():
                random.shuffle(filtered_questions)
            
            filtered_questions = [shuffle_options(q) for q in filtered_questions]
            
            if num_questions:
                filtered_questions = filtered_questions[:num_questions]
            
            args = SimpleNamespace(
                json_file=json_path,
                num_questions=num_questions,
                pages=pages,
                n_max=n_max,
                tags=tags
            )
            validate_args(args, len(filtered_questions))
            distributed_questions = distribute_questions(filtered_questions, pages, n_max)
            
            for i, page_questions in enumerate(distributed_questions, 1):
                base_name = worksheet_title.replace(' ', '_')
                output_file = os.path.join(output_dir, f"{base_name}_Page_{i}.pdf")
                create_worksheet(page_questions, output_file, f"{worksheet_title} - Page {i}")
                answer_key_file = os.path.join(output_dir, f"{base_name}_Page_{i}_answer_key.pdf")
                create_worksheet(page_questions, answer_key_file, f"{worksheet_title} - Page {i} (Answer Key)", include_answers=True)
            
            QMessageBox.information(self, "Success", "Worksheets generated successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")

# -------------------- Question Generator Widget -------------------- #
class QuestionGeneratorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # JSON file selection
        file_layout = QHBoxLayout()
        self.json_file_edit = QLineEdit()
        self.json_file_edit.setPlaceholderText("Select or enter target JSON file")
        json_btn = QPushButton("Browse...")
        json_btn.clicked.connect(self.browse_json_file)
        file_layout.addWidget(self.json_file_edit)
        file_layout.addWidget(json_btn)
        layout.addLayout(file_layout)
        
        # Question form
        self.question_form = QuestionFormWidget()
        layout.addWidget(self.question_form)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.save_question_btn = QPushButton("Save Question")
        self.save_question_btn.clicked.connect(self.save_question)
        self.clear_fields_btn = QPushButton("Clear Fields")
        self.clear_fields_btn.clicked.connect(self.clear_fields)
        button_layout.addWidget(self.save_question_btn)
        button_layout.addWidget(self.clear_fields_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def save_question(self):
        json_file = self.json_file_edit.text().strip()
        if not json_file:
            QMessageBox.critical(self, "Error", "Please specify the output JSON file.")
            return

        question_dict = self.question_form.get_question_data()
        
        try:
            json_utils.append_question(question_dict, json_file)
            QMessageBox.information(self, "Success", "Question saved successfully!")
            self.clear_fields()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save question:\n{str(e)}")

    def clear_fields(self):
        self.question_form.clear()

    def browse_json_file(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Select or Create JSON File", "", "JSON Files (*.json)")
        if filename:
            self.json_file_edit.setText(filename)

# -------------------- New: Question Browser Widget -------------------- #
class QuestionBrowserWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.questions = []
        self.current_question_index = None
        self.json_file_path = None
        self.init_ui()
        self.load_questions()

    def init_ui(self):
        main_layout = QVBoxLayout()
        # JSON file selection
        file_layout = QHBoxLayout()
        self.json_file_edit = QLineEdit()
        browse_file_btn = QPushButton("Browse...")
        browse_file_btn.clicked.connect(self.browse_json_file)
        load_btn = QPushButton("Load Questions")
        load_btn.clicked.connect(self.load_questions)
        file_layout.addWidget(QLabel("JSON File:"))
        file_layout.addWidget(self.json_file_edit)
        file_layout.addWidget(browse_file_btn)
        file_layout.addWidget(load_btn)
        main_layout.addLayout(file_layout)
        
        # Filter/search field
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search/Filter:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.textChanged.connect(self.filter_questions)
        filter_layout.addWidget(self.filter_edit)
        main_layout.addLayout(filter_layout)
        
        # Split view with models
        splitter = QSplitter(Qt.Horizontal)
        self.question_list = QListView()
        self.model = QStandardItemModel()
        self.proxyModel = QSortFilterProxyModel()
        self.proxyModel.setSourceModel(self.model)
        self.question_list.setModel(self.proxyModel)
        self.question_list.selectionModel().selectionChanged.connect(self.on_question_selected)
        splitter.addWidget(self.question_list)
        
        # Form widget setup
        form_widget = QWidget()
        form_layout = QVBoxLayout()
        self.question_form = QuestionFormWidget()
        form_layout.addWidget(self.question_form)
        
        # Buttons
        self.delete_btn = QPushButton("Delete Question")
        self.delete_btn.clicked.connect(self.delete_question)
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_changes)
        form_layout.addWidget(self.save_btn)
        form_layout.addWidget(self.delete_btn)
        
        form_widget.setLayout(form_layout)
        splitter.addWidget(form_widget)
        splitter.setSizes([200, 400])
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def browse_json_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select JSON File", "", "JSON Files (*.json)")
        if filename:
            self.json_file_edit.setText(filename)

    def load_questions(self):
        self.json_file_path = self.json_file_edit.text().strip()
        if not self.json_file_path:
            QMessageBox.critical(self, "Error", "Please select a JSON file.")
            return
            
        if not os.path.exists(self.json_file_path):
            self.questions = []
            QMessageBox.information(
                self,
                "New File",
                "The specified JSON file doesn't exist. A new file will be created when saving."
            )
            self.populate_list()
            return
            
        try:
            self.questions = load_qs(self.json_file_path)
            self.populate_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load questions: {str(e)}")

    def populate_list(self):
        self.model.clear()
        for i, q in enumerate(self.questions):
            question_text = q.get("question", {}).get("text", "")
            display_text = f"{i+1}: {question_text[:50]}"
            item = QStandardItem(display_text)
            item.setData(i, Qt.UserRole)
            self.model.appendRow(item)

    def filter_questions(self):
        self.proxyModel.setFilterFixedString(self.filter_edit.text())

    def save_changes(self):
        if not self.json_file_path:
            QMessageBox.critical(self, "Error", "No JSON file selected.")
            return

        try:
            json_utils.save_questions(self.json_file_path, self.questions)
            QMessageBox.information(self, "Success", "Changes saved successfully!")
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "The specified JSON file location is not accessible.")
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Failed to encode questions as JSON.")
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Failed to write to file: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")

    def on_question_selected(self):
        selected_indexes = self.question_list.selectedIndexes()
        if not selected_indexes:
            self.current_question_index = None
            self.question_form.clear()
            return
        
        selected_index = selected_indexes[0]
        model_index = self.proxyModel.mapToSource(selected_index)
        index = model_index.data(Qt.UserRole)
        self.commit_current_question()
        
        self.current_question_index = index
        question = self.questions[index]
        self.question_form.set_question_data(question)

    def commit_current_question(self):
        if self.current_question_index is None:
            return
        self.questions[self.current_question_index] = self.question_form.get_question_data()
        self.populate_list()

    def delete_question(self):
        if self.current_question_index is None:
            return
        reply = QMessageBox.question(self, "Delete Question", "Are you sure you want to delete this question?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.questions[self.current_question_index]
            self.current_question_index = None
            self.populate_list()
            self.question_form.clear()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAT Worksheet & Question Generator")
        self.setMinimumSize(600, 400)
        self.init_ui()

    def init_ui(self):
        tab_widget = QTabWidget()
        worksheet_tab = WorksheetGeneratorWidget()
        question_tab = QuestionGeneratorWidget()
        question_browser_tab = QuestionBrowserWidget()  # New tab for browsing/editing questions
        tab_widget.addTab(worksheet_tab, "Worksheet Generator")
        tab_widget.addTab(question_tab, "Question Generator")
        tab_widget.addTab(question_browser_tab, "Question Browser")
        self.setCentralWidget(tab_widget)
        
        # Connect aboutToQuit signal to save_changes
        QApplication.instance().aboutToQuit.connect(question_browser_tab.save_changes)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()