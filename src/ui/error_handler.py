#!/usr/bin/env python3
"""
Error handling utilities for UI components
"""
import traceback
import logging
from typing import Optional, Callable, Any, Union
from PyQt5.QtWidgets import QMessageBox, QWidget

class ErrorHandler:
    """
    Centralized error handling for UI components
    """
    def __init__(self, parent_widget: Optional[QWidget] = None):
        self.parent = parent_widget
        self.logger = logging.getLogger(__name__)
    
    def set_parent(self, parent_widget: QWidget) -> None:
        """Set the parent widget for error messages"""
        self.parent = parent_widget
    
    def show_error(self, title: str, message: str, detailed_error: Optional[str] = None) -> None:
        """Display error message to user and log it"""
        if detailed_error:
            self.logger.error(f"{message}: {detailed_error}")
        else:
            self.logger.error(message)
            
        if self.parent:
            error_box = QMessageBox(self.parent)
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle(title)
            error_box.setText(message)
            if detailed_error:
                error_box.setDetailedText(detailed_error)
            error_box.exec_()
    
    def show_warning(self, title: str, message: str) -> None:
        """Display warning message to user and log it"""
        self.logger.warning(message)
        if self.parent:
            QMessageBox.warning(self.parent, title, message)
    
    def show_info(self, title: str, message: str) -> None:
        """Display information message to user"""
        if self.parent:
            QMessageBox.information(self.parent, title, message)
    
    def confirm(self, title: str, message: str) -> bool:
        """Ask user for confirmation, returns True if confirmed"""
        if self.parent:
            reply = QMessageBox.question(
                self.parent, title, message,
                QMessageBox.Yes | QMessageBox.No
            )
            return reply == QMessageBox.Yes
        return False
    
    def handle_exception(self, e: Exception, title: str, message: str) -> None:
        """Handle exception by showing error message with details"""
        error_details = f"{str(e)}\n\n{traceback.format_exc()}"
        self.show_error(title, message, error_details)
    
    def execute_with_error_handling(self, func: Callable, error_title: str, error_msg: str,
                                   success_title: Optional[str] = None, success_msg: Optional[str] = None,
                                   *args, **kwargs) -> Optional[Any]:
        """Execute a function with standardized error handling"""
        try:
            result = func(*args, **kwargs)
            if success_title and success_msg:
                self.show_info(success_title, success_msg)
            return result
        except Exception as e:
            self.handle_exception(e, error_title, error_msg)
            return None
