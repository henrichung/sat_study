#!/usr/bin/env python3
"""
Utility script to update the SQLite database from JSON files
"""
import sys
import os
import argparse
import logging

# Add parent directory to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

from src.core.db.operations import save_question, get_question_by_uid
from src.data.json_utils import load_questions

def main():
    parser = argparse.ArgumentParser(description="Update SQLite database from JSON files")
    parser.add_argument("--json", required=True, help="Path to JSON file with questions")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Check if files exist
    if not os.path.exists(args.json):
        logging.error(f"JSON file not found: {args.json}")
        return 1
    
    if not os.path.exists(args.db):
        logging.error(f"Database file not found: {args.db}")
        return 1
    
    try:
        # Load questions from JSON
        logging.info(f"Loading questions from {args.json}")
        questions = load_questions(args.json)
        logging.info(f"Found {len(questions)} questions")
        
        # Save each question to database
        success_count = 0
        for question in questions:
            # Check if question already exists
            try:
                existing = get_question_by_uid(args.db, question.uid)
                is_new = False
            except:
                is_new = True
            
            # Save question
            if save_question(args.db, question, is_new):
                success_count += 1
        
        logging.info(f"Successfully updated {success_count} questions in database")
        return 0
    
    except Exception as e:
        logging.error(f"Error updating database: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())