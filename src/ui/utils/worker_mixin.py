#!/usr/bin/env python3
"""
Mixin class to provide standardized worker handling
"""
from typing import Any, Callable, Dict, Optional, Type
from PyQt5.QtCore import QThreadPool
from src.ui.components.progress_dialog import ProgressDialog
from src.ui.error_handler import ErrorHandler

class WorkerMixin:
    """
    Mixin class that provides standardized methods for handling background workers
    with progress dialogs and error handling
    """
    
    def __init__(self):
        # These attributes should be set by the class using this mixin
        self.threadpool = QThreadPool()
        self.error_handler = ErrorHandler()
    
    def run_worker_with_progress(self, 
                                worker_class: Type,
                                worker_args: Dict[str, Any],
                                progress_title: str,
                                progress_message: str,
                                on_result: Optional[Callable] = None,
                                on_error: Optional[Callable] = None,
                                on_finished: Optional[Callable] = None,
                                disable_ui: bool = True) -> None:
        """
        Run a worker in a background thread with progress dialog and error handling
        
        Args:
            worker_class: Worker class to instantiate
            worker_args: Arguments to pass to the worker constructor
            progress_title: Title for the progress dialog
            progress_message: Initial message for the progress dialog
            on_result: Optional function to handle successful results
            on_error: Optional function to handle errors
            on_finished: Optional function to call when worker is finished
            disable_ui: Whether to disable the UI while the worker is running
        """
        # Create and show progress dialog
        self.progress_dialog = ProgressDialog(progress_title, self)
        self.progress_dialog.update_status(progress_message)
        self.progress_dialog.show()
        
        if disable_ui:
            self.setEnabled(False)
        
        try:
            # Create worker instance
            worker = worker_class(**worker_args)
            
            # Connect signals
            if on_result:
                worker.signals.result.connect(on_result)
            
            # Use provided error handler or default
            if on_error:
                worker.signals.error.connect(on_error)
            else:
                worker.signals.error.connect(
                    lambda error: self.handle_worker_error(error, progress_title)
                )
            
            # Connect progress and status signals to dialog
            worker.signals.progress.connect(self.progress_dialog.update_progress)
            worker.signals.status_update.connect(self.progress_dialog.update_status)
            
            # Define default finish handler if none provided
            def default_finish_handler():
                self.progress_dialog.accept()
                if disable_ui:
                    self.setEnabled(True)
            
            # Connect finished signal
            if on_finished:
                worker.signals.finished.connect(on_finished)
            else:
                worker.signals.finished.connect(default_finish_handler)
            
            # Start the worker
            self.threadpool.start(worker)
            
        except Exception as e:
            if disable_ui:
                self.setEnabled(True)
            self.progress_dialog.accept()
            self.error_handler.handle_exception(
                e, "Error", f"Failed to start {progress_title.lower()}"
            )
    
    def handle_worker_error(self, error: str, context: str) -> None:
        """Default error handler for workers"""
        self.progress_dialog.accept()
        self.setEnabled(True)
        self.error_handler.show_error("Error", f"Error during {context.lower()}", error)
