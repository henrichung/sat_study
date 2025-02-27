import os
import random
from PyQt5.QtCore import QRunnable, pyqtSlot
from src.ui.workers.question_workers import WorkerSignals
from src.core.worksheet import create_worksheet, distribute_questions

def shuffle_options(question_dict):
    """Shuffle options within a question dictionary."""
    # Make a copy of the options to shuffle
    options = question_dict.get('options', {})
    
    # Get answer key
    answer_key = question_dict.get('answer', '')
    
    # If we have options and an answer key, shuffle
    if options and answer_key and answer_key in options:
        # Get list of keys (A, B, C, D, etc.)
        keys = list(options.keys())
        
        # Remember which key has the answer
        answer_content = options[answer_key]
        
        # Shuffle the keys
        random.shuffle(keys)
        
        # Create new options dictionary with shuffled keys
        shuffled_options = {}
        new_answer_key = None
        
        for i, original_key in enumerate(keys):
            new_key = chr(65 + i)  # A, B, C, D, etc.
            shuffled_options[new_key] = options[original_key]
            
            # If this was the answer, update the answer key
            if original_key == answer_key:
                new_answer_key = new_key
        
        # Update the question with shuffled options and new answer key
        question_dict['options'] = shuffled_options
        question_dict['answer'] = new_answer_key
    
    return question_dict

class GenerateWorksheetsWorker(QRunnable):
    def __init__(self, questions, output_dir, worksheet_title, pages, n_max):
        super().__init__()
        self.questions = questions
        self.output_dir = output_dir
        self.worksheet_title = worksheet_title
        self.pages = pages
        self.n_max = n_max
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            self.signals.progress.emit(10)
            self.signals.status_update.emit("Distributing questions across pages...")
            
            distributed_questions = distribute_questions(self.questions, self.pages, self.n_max)

            self.signals.progress.emit(20)
            self.signals.status_update.emit("Creating worksheets...")
            
            total_pages = len(distributed_questions)
            for i, page_questions in enumerate(distributed_questions, 1):
                # Calculate progress: 20% base + up to 70% for pages creation
                progress = 20 + int((i / total_pages) * 70)
                self.signals.progress.emit(progress)
                self.signals.status_update.emit(f"Creating worksheet {i} of {total_pages}...")
                
                base_name = self.worksheet_title.replace(' ', '_')
                output_file = os.path.join(self.output_dir, f"{base_name}_Page_{i}.pdf")
                create_worksheet(page_questions, output_file, f"{self.worksheet_title} - Page {i}")
                
                answer_key_file = os.path.join(self.output_dir, f"{base_name}_Page_{i}_answer_key.pdf")
                create_worksheet(page_questions, answer_key_file, 
                               f"{self.worksheet_title} - Page {i} (Answer Key)", 
                               include_answers=True)
            
            self.signals.progress.emit(100)
            self.signals.status_update.emit("Worksheets created successfully!")
            
        except Exception as e:
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()