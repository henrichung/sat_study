import json
import os

def save_question_to_json(question, json_file_path):
    """
    Appends a new question dictionary to the specified JSON file.
    If the file does not exist or cannot be parsed as JSON, a new list is created.
    """
    if os.path.exists(json_file_path):
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
        except (json.JSONDecodeError, IOError):
            data = []
    else:
        data = []

    data.append(question)

    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)