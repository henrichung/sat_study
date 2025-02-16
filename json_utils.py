import json
import logging

def load_questions(json_file):
    """Load questions from the given JSON file."""
    with open(json_file, 'r') as f:
        return json.load(f)

def save_questions(json_file, questions):
    """Save the questions list to the given JSON file."""
    with open(json_file, 'w') as f:
        json.dump(questions, f, indent=2)

def append_question(json_file, question):
    """
    Append a question to the JSON file. Creates new file if doesn't exist.
    Handles invalid JSON gracefully by creating new list.
    """
    try:
        with open(json_file, 'r') as f:
            try:
                questions = json.load(f)
            except json.JSONDecodeError:
                logging.error(f"Invalid JSON in {json_file}, creating new list")
                questions = []
    except FileNotFoundError:
        questions = []

    questions.append(question)

    try:
        with open(json_file, 'w') as f:
            json.dump(questions, f, indent=2)
    except IOError as e:
        print(f"Error saving to {json_file}: {str(e)}")
        raise