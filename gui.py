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
from types import SimpleNamespace

from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QFileDialog,
                             QMessageBox, QPushButton, QLabel, QLineEdit, QCheckBox,
                             QFormLayout, QHBoxLayout, QVBoxLayout, QTabWidget, QTextEdit,
                             QComboBox, QListWidget, QSplitter)
from PyQt5.QtCore import Qt

# Import worksheet generator functions (existing module)
from sat_worksheet_core import load_questions, filter_questions, shuffle_options, \
    create_worksheet, validate_args, distribute_questions

# Import the new question generator core function
from question_generator_core import save_question_to_json
import json_utils
# Import core functions for question browsing/editing
from question_browser_core import load_questions as load_qs, save_questions

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
        # (Existing code unchanged)
        layout = QFormLayout()
        self.json_file_edit = QLineEdit()
        self.json_file_edit.setPlaceholderText("Select or enter target JSON file")
        json_btn = QPushButton("Browse...")
        json_btn.clicked.connect(self.browse_json_file)
        hbox_json = QHBoxLayout()
        hbox_json.addWidget(self.json_file_edit)
        hbox_json.addWidget(json_btn)
        layout.addRow("Output JSON File:", hbox_json)
        self.question_text_edit = QTextEdit()
        self.question_text_edit.setPlaceholderText("Enter question text here")
        layout.addRow("Question Text:", self.question_text_edit)
        self.question_image_edit = QLineEdit()
        self.question_image_edit.setPlaceholderText("Path to question image (optional)")
        question_img_btn = QPushButton("Browse...")
        question_img_btn.clicked.connect(self.browse_question_image)
        hbox_qimg = QHBoxLayout()
        hbox_qimg.addWidget(self.question_image_edit)
        hbox_qimg.addWidget(question_img_btn)
        layout.addRow("Question Image:", hbox_qimg)
        self.optionA_text_edit = QLineEdit()
        self.optionA_text_edit.setPlaceholderText("Enter Option A text")
        self.optionA_image_edit = QLineEdit()
        self.optionA_image_edit.setPlaceholderText("Path to Option A image (optional)")
        optionA_img_btn = QPushButton("Browse...")
        optionA_img_btn.clicked.connect(lambda: self.browse_option_image(self.optionA_image_edit))
        hbox_a_img = QHBoxLayout()
        hbox_a_img.addWidget(self.optionA_image_edit)
        hbox_a_img.addWidget(optionA_img_btn)
        layout.addRow("Option A Text:", self.optionA_text_edit)
        layout.addRow("Option A Image:", hbox_a_img)
        self.optionB_text_edit = QLineEdit()
        self.optionB_text_edit.setPlaceholderText("Enter Option B text")
        self.optionB_image_edit = QLineEdit()
        self.optionB_image_edit.setPlaceholderText("Path to Option B image (optional)")
        optionB_img_btn = QPushButton("Browse...")
        optionB_img_btn.clicked.connect(lambda: self.browse_option_image(self.optionB_image_edit))
        hbox_b_img = QHBoxLayout()
        hbox_b_img.addWidget(self.optionB_image_edit)
        hbox_b_img.addWidget(optionB_img_btn)
        layout.addRow("Option B Text:", self.optionB_text_edit)
        layout.addRow("Option B Image:", hbox_b_img)
        self.optionC_text_edit = QLineEdit()
        self.optionC_text_edit.setPlaceholderText("Enter Option C text")
        self.optionC_image_edit = QLineEdit()
        self.optionC_image_edit.setPlaceholderText("Path to Option C image (optional)")
        optionC_img_btn = QPushButton("Browse...")
        optionC_img_btn.clicked.connect(lambda: self.browse_option_image(self.optionC_image_edit))
        hbox_c_img = QHBoxLayout()
        hbox_c_img.addWidget(self.optionC_image_edit)
        hbox_c_img.addWidget(optionC_img_btn)
        layout.addRow("Option C Text:", self.optionC_text_edit)
        layout.addRow("Option C Image:", hbox_c_img)
        self.optionD_text_edit = QLineEdit()
        self.optionD_text_edit.setPlaceholderText("Enter Option D text")
        self.optionD_image_edit = QLineEdit()
        self.optionD_image_edit.setPlaceholderText("Path to Option D image (optional)")
        optionD_img_btn = QPushButton("Browse...")
        optionD_img_btn.clicked.connect(lambda: self.browse_option_image(self.optionD_image_edit))
        hbox_d_img = QHBoxLayout()
        hbox_d_img.addWidget(self.optionD_image_edit)
        hbox_d_img.addWidget(optionD_img_btn)
        layout.addRow("Option D Text:", self.optionD_text_edit)
        layout.addRow("Option D Image:", hbox_d_img)
        self.correct_answer_combo = QComboBox()
        self.correct_answer_combo.addItems(["A", "B", "C", "D"])
        layout.addRow("Correct Answer:", self.correct_answer_combo)
        self.difficulty_edit = QLineEdit()
        self.difficulty_edit.setPlaceholderText("e.g., Easy, Medium, Hard")
        layout.addRow("Difficulty:", self.difficulty_edit)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Comma separated tags")
        layout.addRow("Tags (comma separated):", self.tags_edit)
        self.explanation_text_edit = QTextEdit()
        self.explanation_text_edit.setPlaceholderText("Enter explanation text here")
        layout.addRow("Explanation Text:", self.explanation_text_edit)
        self.save_question_btn = QPushButton("Save Question")
        self.save_question_btn.clicked.connect(self.save_question)
        self.clear_fields_btn = QPushButton("Clear Fields")
        self.clear_fields_btn.clicked.connect(self.clear_fields)
        hbox_buttons = QHBoxLayout()
        hbox_buttons.addWidget(self.save_question_btn)
        hbox_buttons.addWidget(self.clear_fields_btn)
        layout.addRow(hbox_buttons)
        self.setLayout(layout)

    def browse_json_file(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Select or Create JSON File", "", "JSON Files (*.json)")
        if filename:
            self.json_file_edit.setText(filename)

    def browse_question_image(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Question Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if filename:
            self.question_image_edit.setText(filename)

    def browse_option_image(self, line_edit):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Option Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if filename:
            line_edit.setText(filename)

    def save_question(self):
        json_file = self.json_file_edit.text().strip()
        if not json_file:
            QMessageBox.critical(self, "Error", "Please specify the output JSON file.")
            return

        question_text = self.question_text_edit.toPlainText().strip()
        question_image = self.question_image_edit.text().strip()
        optionA_text = self.optionA_text_edit.text().strip()
        optionA_image = self.optionA_image_edit.text().strip()
        optionB_text = self.optionB_text_edit.text().strip()
        optionB_image = self.optionB_image_edit.text().strip()
        optionC_text = self.optionC_text_edit.text().strip()
        optionC_image = self.optionC_image_edit.text().strip()
        optionD_text = self.optionD_text_edit.text().strip()
        optionD_image = self.optionD_image_edit.text().strip()
        correct_answer = self.correct_answer_combo.currentText()
        difficulty = self.difficulty_edit.text().strip()
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        explanation_text = self.explanation_text_edit.toPlainText().strip()

        question_dict = {
            "question": {
                "text": question_text,
                "image": question_image
            },
            "options": {
                "A": {"text": optionA_text, "image": optionA_image},
                "B": {"text": optionB_text, "image": optionB_image},
                "C": {"text": optionC_text, "image": optionC_image},
                "D": {"text": optionD_text, "image": optionD_image}
            },
            "answer": correct_answer,
            "difficulty": difficulty,
            "tags": tags,
            "explanation": {
                "text": explanation_text
            }
        }

        try:
            json_utils.append_question(question_dict, json_file)
            QMessageBox.information(self, "Success", "Question saved successfully!")
            self.clear_fields()
            self.question_text_edit.setFocus()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save question:\n{str(e)}")

    def clear_fields(self):
        self.question_text_edit.clear()
        self.question_image_edit.clear()
        self.optionA_text_edit.clear()
        self.optionA_image_edit.clear()
        self.optionB_text_edit.clear()
        self.optionB_image_edit.clear()
        self.optionC_text_edit.clear()
        self.optionC_image_edit.clear()
        self.optionD_text_edit.clear()
        self.optionD_image_edit.clear()
        self.difficulty_edit.clear()
        self.tags_edit.clear()
        self.explanation_text_edit.clear()
        self.correct_answer_combo.setCurrentIndex(0)

# -------------------- New: Question Browser Widget -------------------- #
class QuestionBrowserWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.questions = []
        self.current_question_index = None
        self.json_file_path = None
        self.init_ui()

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
        self.filter_edit.textChanged.connect(self.refresh_question_list)
        filter_layout.addWidget(self.filter_edit)
        main_layout.addLayout(filter_layout)
        # Split view: List on left, edit form on right
        splitter = QSplitter(Qt.Horizontal)
        self.question_list = QListWidget()
        self.question_list.itemSelectionChanged.connect(self.on_question_selected)
        splitter.addWidget(self.question_list)
        form_widget = QWidget()
        form_layout = QFormLayout()
        self.question_text_edit = QTextEdit()
        form_layout.addRow("Question Text:", self.question_text_edit)
        self.question_image_edit = QLineEdit()
        question_img_btn = QPushButton("Browse...")
        question_img_btn.clicked.connect(self.browse_question_image)
        qimg_layout = QHBoxLayout()
        qimg_layout.addWidget(self.question_image_edit)
        qimg_layout.addWidget(question_img_btn)
        form_layout.addRow("Question Image:", qimg_layout)
        self.optionA_text_edit = QLineEdit()
        self.optionA_image_edit = QLineEdit()
        optionA_img_btn = QPushButton("Browse...")
        optionA_img_btn.clicked.connect(lambda: self.browse_option_image(self.optionA_image_edit))
        a_img_layout = QHBoxLayout()
        a_img_layout.addWidget(self.optionA_image_edit)
        a_img_layout.addWidget(optionA_img_btn)
        form_layout.addRow("Option A Text:", self.optionA_text_edit)
        form_layout.addRow("Option A Image:", a_img_layout)
        self.optionB_text_edit = QLineEdit()
        self.optionB_image_edit = QLineEdit()
        optionB_img_btn = QPushButton("Browse...")
        optionB_img_btn.clicked.connect(lambda: self.browse_option_image(self.optionB_image_edit))
        b_img_layout = QHBoxLayout()
        b_img_layout.addWidget(self.optionB_image_edit)
        b_img_layout.addWidget(optionB_img_btn)
        form_layout.addRow("Option B Text:", self.optionB_text_edit)
        form_layout.addRow("Option B Image:", b_img_layout)
        self.optionC_text_edit = QLineEdit()
        self.optionC_image_edit = QLineEdit()
        optionC_img_btn = QPushButton("Browse...")
        optionC_img_btn.clicked.connect(lambda: self.browse_option_image(self.optionC_image_edit))
        c_img_layout = QHBoxLayout()
        c_img_layout.addWidget(self.optionC_image_edit)
        c_img_layout.addWidget(optionC_img_btn)
        form_layout.addRow("Option C Text:", self.optionC_text_edit)
        form_layout.addRow("Option C Image:", c_img_layout)
        self.optionD_text_edit = QLineEdit()
        self.optionD_image_edit = QLineEdit()
        optionD_img_btn = QPushButton("Browse...")
        optionD_img_btn.clicked.connect(lambda: self.browse_option_image(self.optionD_image_edit))
        d_img_layout = QHBoxLayout()
        d_img_layout.addWidget(self.optionD_image_edit)
        d_img_layout.addWidget(optionD_img_btn)
        form_layout.addRow("Option D Text:", self.optionD_text_edit)
        form_layout.addRow("Option D Image:", d_img_layout)
        self.correct_answer_combo = QComboBox()
        self.correct_answer_combo.addItems(["A", "B", "C", "D"])
        form_layout.addRow("Correct Answer:", self.correct_answer_combo)
        self.difficulty_edit = QLineEdit()
        form_layout.addRow("Difficulty:", self.difficulty_edit)
        self.tags_edit = QLineEdit()
        form_layout.addRow("Tags (comma separated):", self.tags_edit)
        self.explanation_text_edit = QTextEdit()
        form_layout.addRow("Explanation Text:", self.explanation_text_edit)
        self.delete_btn = QPushButton("Delete Question")
        self.delete_btn.clicked.connect(self.delete_question)
        form_layout.addRow(self.delete_btn)
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
        try:
            self.questions = load_qs(self.json_file_path)
            self.refresh_question_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load questions: {str(e)}")

    def refresh_question_list(self):
        self.question_list.clear()
        filter_text = self.filter_edit.text().lower()
        for i, q in enumerate(self.questions):
            question_text = q.get("question", {}).get("text", "")
            tags = " ".join(q.get("tags", []))
            display_text = f"{i+1}: {question_text[:50]}"
            if filter_text:
                if filter_text in question_text.lower() or filter_text in tags.lower():
                    self.question_list.addItem(display_text)
            else:
                self.question_list.addItem(display_text)

    def on_question_selected(self):
        self.commit_current_question()
        selected_items = self.question_list.selectedItems()
        if not selected_items:
            self.current_question_index = None
            self.clear_form()
            return
        item_text = selected_items[0].text()
        index_str = item_text.split(":")[0]
        try:
            index = int(index_str) - 1
        except ValueError:
            return
        self.current_question_index = index
        question = self.questions[index]
        self.populate_form(question)

    def populate_form(self, question):
        self.question_text_edit.setPlainText(question.get("question", {}).get("text", ""))
        self.question_image_edit.setText(question.get("question", {}).get("image", ""))
        options = question.get("options", {})
        
        # Helper to extract text and image from an option
        def get_option_fields(option):
            if isinstance(option, dict):
                return option.get("text", ""), option.get("image", "")
            else:
                return option if option else "", ""
        
        a_text, a_image = get_option_fields(options.get("A", ""))
        b_text, b_image = get_option_fields(options.get("B", ""))
        c_text, c_image = get_option_fields(options.get("C", ""))
        d_text, d_image = get_option_fields(options.get("D", ""))
        
        self.optionA_text_edit.setText(a_text)
        self.optionA_image_edit.setText(a_image)
        self.optionB_text_edit.setText(b_text)
        self.optionB_image_edit.setText(b_image)
        self.optionC_text_edit.setText(c_text)
        self.optionC_image_edit.setText(c_image)
        self.optionD_text_edit.setText(d_text)
        self.optionD_image_edit.setText(d_image)
        
        correct = question.get("answer", "A")
        idx = self.correct_answer_combo.findText(correct)
        if idx >= 0:
            self.correct_answer_combo.setCurrentIndex(idx)
        self.difficulty_edit.setText(question.get("difficulty", ""))
        self.tags_edit.setText(", ".join(question.get("tags", [])))
        self.explanation_text_edit.setPlainText(question.get("explanation", {}).get("text", ""))

    def clear_form(self):
        self.question_text_edit.clear()
        self.question_image_edit.clear()
        self.optionA_text_edit.clear()
        self.optionA_image_edit.clear()
        self.optionB_text_edit.clear()
        self.optionB_image_edit.clear()
        self.optionC_text_edit.clear()
        self.optionC_image_edit.clear()
        self.optionD_text_edit.clear()
        self.optionD_image_edit.clear()
        self.correct_answer_combo.setCurrentIndex(0)
        self.difficulty_edit.clear()
        self.tags_edit.clear()
        self.explanation_text_edit.clear()

    def commit_current_question(self):
        if self.current_question_index is None:
            return
        updated_question = {
            "question": {
                "text": self.question_text_edit.toPlainText().strip(),
                "image": self.question_image_edit.text().strip()
            },
            "options": {
                "A": {"text": self.optionA_text_edit.text().strip(), "image": self.optionA_image_edit.text().strip()},
                "B": {"text": self.optionB_text_edit.text().strip(), "image": self.optionB_image_edit.text().strip()},
                "C": {"text": self.optionC_text_edit.text().strip(), "image": self.optionC_image_edit.text().strip()},
                "D": {"text": self.optionD_text_edit.text().strip(), "image": self.optionD_image_edit.text().strip()}
            },
            "answer": self.correct_answer_combo.currentText(),
            "difficulty": self.difficulty_edit.text().strip(),
            "tags": [t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            "explanation": {
                "text": self.explanation_text_edit.toPlainText().strip()
            }
        }
        self.questions[self.current_question_index] = updated_question
        if self.json_file_path:
            try:
                json_utils.save_questions(self.json_file_path, self.questions)
                self.refresh_question_list()
            except FileNotFoundError:
                # Show a message box indicating the file was not found.
                QMessageBox.critical(self, "Error", "The specified JSON file could not be found.")
            except json.JSONDecodeError:
                # Show a message box indicating the JSON file is corrupted.
                QMessageBox.critical(self, "Error", "The JSON file is corrupted and could not be loaded.")
            except IOError as e:
                # Show a message box with details about the I/O error.  Include the error message (str(e)).
                QMessageBox.critical(self, "Error", f"An I/O error occurred: {str(e)}")
            except Exception as e:
                # Log the exception for further investigation
                # Show a message box to the user with a generic message + message from exception
                QMessageBox.critical(self, "Error", f"An Unexpected Error Occurred: {str(e)}")

    def browse_question_image(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Question Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if filename:
            self.question_image_edit.setText(filename)

    def browse_option_image(self, line_edit):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Option Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if filename:
            line_edit.setText(filename)

    def delete_question(self):
        if self.current_question_index is None:
            return
        reply = QMessageBox.question(self, "Delete Question", "Are you sure you want to delete this question?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.questions[self.current_question_index]
            if self.json_file_path:
                try:
                    json_utils.save_questions.(self.json_file_path, self.questions)
                    self.current_question_index = None
                    self.refresh_question_list()
                    self.clear_form()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to delete question: {str(e)}")

# -------------------- Main Window with Tabs -------------------- #
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

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()