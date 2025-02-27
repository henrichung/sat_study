#!/usr/bin/env python3
"""
Database Selection Dialog and Utilities
"""
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QComboBox, QPushButton, QFileDialog, QMessageBox)
from PyQt5.QtCore import pyqtSignal

from src.utils.config import load_config, save_config

class DatabaseSelectionDialog(QDialog):
    """Dialog for selecting or creating a SQLite database"""
    
    db_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = load_config()
        self.init_ui()
        
    def init_ui(self):
        """Set up dialog UI"""
        self.setWindowTitle("Select Database")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Recent databases selector
        recent_layout = QHBoxLayout()
        recent_layout.addWidget(QLabel("Recent Databases:"))
        
        self.db_combo = QComboBox()
        self.db_combo.setMinimumWidth(250)
        self.update_recent_databases()
        recent_layout.addWidget(self.db_combo)
        
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self.open_selected_db)
        recent_layout.addWidget(open_btn)
        
        layout.addLayout(recent_layout)
        
        # Browse for database
        browse_layout = QHBoxLayout()
        browse_btn = QPushButton("Browse for Database...")
        browse_btn.clicked.connect(self.browse_db)
        browse_layout.addWidget(browse_btn)
        
        create_btn = QPushButton("Create New Database...")
        create_btn.clicked.connect(self.create_new_db)
        browse_layout.addWidget(create_btn)
        
        layout.addLayout(browse_layout)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        self.setLayout(layout)
        
    def update_recent_databases(self):
        """Update the combobox with recent databases"""
        self.db_combo.clear()
        
        # Add default db first if it exists
        default_db = self.config.get("default_db_path")
        if default_db and os.path.exists(default_db):
            self.db_combo.addItem(f"{default_db} (Default)", default_db)
        
        # Add other recent databases
        for db_path in self.config.get("recent_databases", []):
            if db_path != default_db and os.path.exists(db_path):
                self.db_combo.addItem(db_path, db_path)
                
        # Enable/disable Open button based on whether there are any databases
        if self.db_combo.count() == 0:
            self.db_combo.addItem("No recent databases", "")
    
    def open_selected_db(self):
        """Open the currently selected database"""
        db_path = self.db_combo.currentData()
        if not db_path:
            QMessageBox.warning(self, "No Database Selected", 
                               "No database selected. Please select or create a database.")
            return
            
        self.update_recent_db_list(db_path)
        self.db_selected.emit(db_path)
        self.accept()
        
    def browse_db(self):
        """Browse for existing database file"""
        db_path, _ = QFileDialog.getOpenFileName(
            self, "Select Database File", "", "SQLite Database (*.db);;All Files (*.*)"
        )
        
        if db_path:
            self.update_recent_db_list(db_path)
            self.db_selected.emit(db_path)
            self.accept()
    
    def create_new_db(self):
        """Create a new empty database"""
        db_path, _ = QFileDialog.getSaveFileName(
            self, "Create New Database", "", "SQLite Database (*.db)"
        )
        
        if db_path:
            # Ensure it has .db extension
            if not db_path.lower().endswith('.db'):
                db_path += '.db'
                
            # Create empty database using connection module
            from src.core.db.connection import get_db_connection
            try:
                conn = get_db_connection(db_path, create=True)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    uid TEXT PRIMARY KEY,
                    question_text TEXT NOT NULL,
                    question_image BLOB,
                    answer TEXT NOT NULL,
                    difficulty TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS options (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_uid TEXT NOT NULL,
                    option_key TEXT NOT NULL,
                    option_text TEXT NOT NULL,
                    option_image BLOB,
                    FOREIGN KEY (question_uid) REFERENCES questions(uid) ON DELETE CASCADE
                )
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS question_tags (
                    question_uid TEXT NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (question_uid, tag_id),
                    FOREIGN KEY (question_uid) REFERENCES questions(uid) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                )
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS explanations (
                    question_uid TEXT PRIMARY KEY,
                    explanation_text TEXT,
                    FOREIGN KEY (question_uid) REFERENCES questions(uid) ON DELETE CASCADE
                )
                """)
                
                # Create triggers for updated_at
                conn.execute("""
                CREATE TRIGGER IF NOT EXISTS update_questions_timestamp 
                AFTER UPDATE ON questions
                BEGIN
                    UPDATE questions SET updated_at = CURRENT_TIMESTAMP WHERE uid = NEW.uid;
                END;
                """)
                
                conn.commit()
                conn.close()
                
                self.update_recent_db_list(db_path)
                self.db_selected.emit(db_path)
                self.accept()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create database: {str(e)}")
    
    def update_recent_db_list(self, db_path):
        """Update the recent databases list in config"""
        # Load fresh config
        self.config = load_config()
        
        # Add to recent list if not already there
        recent = self.config.get("recent_databases", [])
        if db_path in recent:
            recent.remove(db_path)
        recent.insert(0, db_path)  # Add to front
        
        # Keep only last 10
        self.config["recent_databases"] = recent[:10]
        
        # Save updated config
        save_config(self.config)