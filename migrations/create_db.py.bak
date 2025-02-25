#!/usr/bin/env python3
"""
SQLite database schema for SAT questions
This script creates a SQLite database with tables for questions and related data.
"""
import os
import sys
import sqlite3
import json
import uuid
import logging

# Add parent directory to path so we can import json_utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json_utils

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_SCHEMA = """
-- Questions table stores basic question metadata
CREATE TABLE IF NOT EXISTS questions (
    uid TEXT PRIMARY KEY,
    question_text TEXT NOT NULL,
    question_image TEXT,
    answer TEXT NOT NULL,
    difficulty TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Options table stores the multiple choice options for questions
CREATE TABLE IF NOT EXISTS options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_uid TEXT NOT NULL,
    option_key TEXT NOT NULL,  -- A, B, C, D
    option_text TEXT NOT NULL,
    option_image TEXT,
    FOREIGN KEY (question_uid) REFERENCES questions(uid) ON DELETE CASCADE,
    UNIQUE(question_uid, option_key)
);

-- Tags table stores the unique tags
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

-- Question_tags junction table for many-to-many relationship
CREATE TABLE IF NOT EXISTS question_tags (
    question_uid TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (question_uid, tag_id),
    FOREIGN KEY (question_uid) REFERENCES questions(uid) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Explanations table stores the explanations for questions
CREATE TABLE IF NOT EXISTS explanations (
    question_uid TEXT PRIMARY KEY,
    explanation_text TEXT NOT NULL,
    FOREIGN KEY (question_uid) REFERENCES questions(uid) ON DELETE CASCADE
);

-- Triggers to update the updated_at timestamp when a question is modified
CREATE TRIGGER IF NOT EXISTS update_questions_timestamp
AFTER UPDATE ON questions
BEGIN
    UPDATE questions SET updated_at = CURRENT_TIMESTAMP WHERE uid = NEW.uid;
END;
"""

def create_database(db_path):
    """Create a new SQLite database with the required schema"""
    try:
        # Create database directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Connect to database and create tables
        conn = sqlite3.connect(db_path)
        conn.executescript(DB_SCHEMA)
        conn.commit()
        logging.info(f"Created database at {db_path}")
        return conn
    except Exception as e:
        logging.error(f"Error creating database: {str(e)}")
        raise

def migrate_json_to_sqlite(json_file, db_path):
    """Migrate questions from a JSON file to a SQLite database"""
    try:
        # Check if JSON file exists
        if not os.path.exists(json_file):
            logging.error(f"JSON file not found: {json_file}")
            return False
        
        # Create database if it doesn't exist
        if not os.path.exists(db_path):
            conn = create_database(db_path)
        else:
            conn = sqlite3.connect(db_path)
        
        # Load questions from JSON
        logging.info(f"Loading questions from {json_file}")
        questions = json_utils.load_questions(json_file)
        logging.info(f"Found {len(questions)} questions")
        
        # Begin transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Insert questions
        inserted_count = 0
        for question in questions:
            try:
                # Insert question
                conn.execute(
                    "INSERT OR IGNORE INTO questions (uid, question_text, question_image, answer, difficulty) VALUES (?, ?, ?, ?, ?)",
                    (
                        question.uid,
                        question.content.text,
                        question.content.image,
                        question.answer,
                        question.difficulty
                    )
                )
                
                # Insert options
                for option_key, option in question.options.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO options (question_uid, option_key, option_text, option_image) VALUES (?, ?, ?, ?)",
                        (
                            question.uid,
                            option_key,
                            option.text,
                            option.image
                        )
                    )
                
                # Insert tags
                for tag in question.tags:
                    # First ensure tag exists in tags table
                    conn.execute(
                        "INSERT OR IGNORE INTO tags (name) VALUES (?)",
                        (tag,)
                    )
                    
                    # Get tag id
                    cursor = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,))
                    tag_id = cursor.fetchone()[0]
                    
                    # Create relationship
                    conn.execute(
                        "INSERT OR IGNORE INTO question_tags (question_uid, tag_id) VALUES (?, ?)",
                        (question.uid, tag_id)
                    )
                
                # Insert explanation
                conn.execute(
                    "INSERT OR REPLACE INTO explanations (question_uid, explanation_text) VALUES (?, ?)",
                    (
                        question.uid,
                        question.explanation.text
                    )
                )
                
                inserted_count += 1
            except Exception as e:
                logging.error(f"Error inserting question {question.uid}: {str(e)}")
        
        # Commit transaction
        conn.commit()
        logging.info(f"Successfully migrated {inserted_count} questions to database")
        
        return True
    except Exception as e:
        logging.error(f"Error migrating data: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def main():
    """Main function to create database and migrate data"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate SAT questions from JSON to SQLite')
    parser.add_argument('--json', required=True, help='Path to JSON file with questions')
    parser.add_argument('--db', required=True, help='Path to SQLite database')
    args = parser.parse_args()
    
    # Create database and migrate data
    success = migrate_json_to_sqlite(args.json, args.db)
    
    if success:
        logging.info("Migration completed successfully")
        return 0
    else:
        logging.error("Migration failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())