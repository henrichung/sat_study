import json
import logging

def yield_questions(json_file):
    """Yield questions one at a time from the JSON file."""
    try:
        with open(json_file, 'r') as f:
            decoder = json.JSONDecoder()
            content = f.read()
            pos = 0
            
            # Skip any whitespace at the beginning and first [
            content = content.strip()
            if content.startswith('['):
                content = content[1:].lstrip()
            
            while pos < len(content):
                try:
                    question, pos = decoder.raw_decode(content[pos:])
                    yield question
                    # Move past any whitespace or comma to the next object
                    content = content[pos:].lstrip()
                    if content.startswith(','):
                        content = content[1:].lstrip()
                    pos = 0
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing question at position {pos}: {str(e)}")
                    # Try to find the start of the next object
                    next_pos = content.find('{', pos)
                    if next_pos == -1:
                        break
                    pos = next_pos
    except FileNotFoundError:
        logging.error(f"File not found: {json_file}")
        raise
    except Exception as e:
        logging.error(f"Error reading file {json_file}: {str(e)}")
        raise

def load_questions(json_file):
    """Load questions from the given JSON file using the generator."""
    return list(yield_questions(json_file))

def save_questions(json_file, questions_to_update, questions_to_delete):
    """
    Update the JSON file with modifications and deletions.
    Args:
        json_file: Path to the JSON file
        questions_to_update: List of questions to update or add
        questions_to_delete: List of questions to remove
    """
    import tempfile
    import os
    import shutil
    
    # Convert lists to sets for O(1) lookup
    questions_to_delete = set(json.dumps(q, sort_keys=True) for q in questions_to_delete)
    questions_to_update = {json.dumps(q, sort_keys=True): q for q in questions_to_update}
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        # Write opening bracket
        temp_file.write('[\n')
        first_item = True
        
        # Process existing questions
        try:
            for question in yield_questions(json_file):
                question_str = json.dumps(question, sort_keys=True)
                
                # Skip if question is marked for deletion
                if question_str in questions_to_delete:
                    continue
                
                # Write comma if not first item
                if not first_item:
                    temp_file.write(',\n')
                first_item = False
                
                # Write updated or original question
                if question_str in questions_to_update:
                    json.dump(questions_to_update[question_str], temp_file, indent=2)
                    del questions_to_update[question_str]
                else:
                    json.dump(question, temp_file, indent=2)
        
        except FileNotFoundError:
            # If file doesn't exist, we'll just create it with new questions
            pass
        
        # Append remaining new questions
        for question in questions_to_update.values():
            if not first_item:
                temp_file.write(',\n')
            first_item = False
            json.dump(question, temp_file, indent=2)
        
        # Write closing bracket
        temp_file.write('\n]')
    
    # Replace original file with temporary file
    try:
        # First try to move the file (fast)
        os.replace(temp_file.name, json_file)
    except OSError:
        try:
            # If move fails, try copy and delete (slower but works across devices)
            shutil.copy2(temp_file.name, json_file)
            os.unlink(temp_file.name)
        except Exception as e:
            os.unlink(temp_file.name)  # Clean up temp file
            raise e

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