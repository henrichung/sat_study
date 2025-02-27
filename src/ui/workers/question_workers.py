#!/usr/bin/env python3
"""
Question worker threads for background processing
"""
import os
import logging
from PyQt5.QtCore import QRunnable, pyqtSlot, QObject, pyqtSignal
import traceback
import sys

from src.core.db.operations import (load_questions, save_question, 
                                  delete_question, get_question_by_uid,
                                  search_questions)
from src.data.json_utils import load_questions as load_json_questions

class WorkerSignals(QObject):
    """Signals for worker threads."""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)
    status_update = pyqtSignal(str)  

class BaseWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()

class LoadQuestionsWorker(BaseWorker):
    def __init__(self, db_path, limit=None, offset=0, tags=None, difficulty=None):
        super().__init__()
        self.db_path = db_path
        self.limit = limit
        self.offset = offset
        self.tags = tags
        self.difficulty = difficulty

    @pyqtSlot()
    def run(self):
        try:
            self.signals.status_update.emit("Connecting to database...")
            self.signals.progress.emit(10)
            
            self.signals.status_update.emit("Retrieving questions...")
            self.signals.progress.emit(30)
            
            questions = load_questions(
                self.db_path, 
                limit=self.limit, 
                offset=self.offset,
                tags=self.tags,
                difficulty=self.difficulty
            )
            
            self.signals.status_update.emit("Processing questions...")
            self.signals.progress.emit(70)
            
            self.signals.result.emit(questions)
            self.signals.progress.emit(100)
            self.signals.status_update.emit("Loading complete!")
        except Exception as e:
            print(traceback.format_exc())
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

class SaveQuestionWorker(BaseWorker):
    def __init__(self, db_path, question, is_new=False):
        super().__init__()
        self.db_path = db_path
        self.question = question
        self.is_new = is_new

    @pyqtSlot()
    def run(self):
        try:
            self.signals.progress.emit(25)  # Started
            success = save_question(self.db_path, self.question, self.is_new)
            self.signals.progress.emit(75)  # Database updated
            
            if success:
                # Reload the question to get the complete object with any DB-generated values
                updated_question = get_question_by_uid(self.db_path, self.question.uid)
                self.signals.result.emit(updated_question)
            else:
                self.signals.error.emit(Exception("Failed to save question"))
                
            self.signals.progress.emit(100)  # Complete
        except Exception as e:
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()

class DeleteQuestionWorker(BaseWorker):
    def __init__(self, db_path, uid):
        super().__init__()
        self.db_path = db_path
        self.uid = uid

    @pyqtSlot()
    def run(self):
        try:
            success = delete_question(self.db_path, self.uid)
            if not success:
                self.signals.error.emit(Exception("Failed to delete question"))
        except Exception as e:
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()

class SearchQuestionsWorker(BaseWorker):
    def __init__(self, db_path, search_text, limit=None, offset=0):
        super().__init__()
        self.db_path = db_path
        self.search_text = search_text
        self.limit = limit
        self.offset = offset

    @pyqtSlot()
    def run(self):
        try:
            self.signals.progress.emit(10)  # Initial progress
            
            questions = search_questions(
                self.db_path, 
                self.search_text,
                limit=self.limit,
                offset=self.offset
            )
            
            self.signals.progress.emit(90)  # Almost done
            self.signals.result.emit(questions)
            self.signals.progress.emit(100)  # Complete
        except Exception as e:
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()

class ImportQuestionsWorker(BaseWorker):
    """Worker thread for importing questions from JSON file to database"""
    
    def __init__(self, json_file_path, db_path):
        super().__init__()
        self.json_file_path = json_file_path
        self.db_path = db_path
    
    @pyqtSlot()
    def run(self):
        try:
            self.signals.status_update.emit(f"Loading questions from JSON file...")
            self.signals.progress.emit(10)
            
            # Load questions from JSON
            json_questions = load_json_questions(self.json_file_path)
            
            if not json_questions:
                self.signals.error.emit("No questions found in JSON file")
                return
                
            self.signals.status_update.emit(f"Found {len(json_questions)} questions in JSON file")
            self.signals.progress.emit(30)
            
            # Save each question to the database
            successful_imports = 0
            for i, question in enumerate(json_questions):
                self.signals.status_update.emit(f"Importing question {i+1}/{len(json_questions)}")
                
                # Save to database
                result = save_question(self.db_path, question, is_new=True)
                if result:
                    successful_imports += 1
                
                # Update progress
                progress = int(30 + ((i + 1) / len(json_questions) * 70))
                self.signals.progress.emit(progress)
            
            self.signals.status_update.emit(f"Successfully imported {successful_imports} of {len(json_questions)} questions")
            self.signals.result.emit(successful_imports)
        
        except Exception as e:
            logging.error(f"Error importing questions: {str(e)}")
            traceback.print_exc()
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()