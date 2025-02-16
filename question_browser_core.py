#!/usr/bin/env python3
"""
Core functions for question browsing and editing.
"""
import json

def load_questions(json_file):
    """Load questions from the given JSON file."""
    with open(json_file, 'r') as f:
        return json.load(f)

def save_questions(json_file, questions):
    """Save the questions list to the given JSON file."""
    with open(json_file, 'w') as f:
        json.dump(questions, f, indent=2)