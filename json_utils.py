import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from uuid import uuid4

@dataclass
class QuestionOption:
    text: str
    image: Optional[str] = None

@dataclass
class QuestionContent:
    text: str
    image: Optional[str] = None

@dataclass
class QuestionExplanation:
    text: str

@dataclass
class Question:
    content: QuestionContent
    options: Dict[str, QuestionOption]
    answer: str
    difficulty: str
    tags: List[str]
    explanation: QuestionExplanation
    uid: str = None

    def __post_init__(self):
        if self.uid is None:
            self.uid = str(uuid4())

    @property
    def text(self) -> str:
        return self.content.text

    @property
    def image(self) -> Optional[str]:
        return self.content.image

    @classmethod
    def from_dict(cls, data: dict) -> 'Question':
        # Convert nested dictionaries to appropriate objects
        options = {k: QuestionOption(**v) for k, v in data.get('options', {}).items()}
        explanation = QuestionExplanation(**data.get('explanation', {'text': ''}))
        
        # Create QuestionContent from question data
        content = QuestionContent(
            text=data.get('question', {}).get('text', ''),
            image=data.get('question', {}).get('image')
        )
        
        # Extract question data
        question_data = {
            'content': content,
            'options': options,
            'answer': data.get('answer', ''),
            'difficulty': data.get('difficulty', ''),
            'tags': data.get('tags', []),
            'explanation': explanation,
            'uid': data.get('uid')
        }
        return cls(**question_data)

    def to_dict(self) -> dict:
        data = asdict(self)
        # Restructure for JSON format
        return {
            'question': {
                'text': self.content.text,
                'image': self.content.image
            },
            'options': data['options'],
            'answer': data['answer'],
            'difficulty': data['difficulty'],
            'tags': data['tags'],
            'explanation': data['explanation'],
            'uid': data['uid']
        }

def yield_questions(json_file):
    """Yield questions one at a time from the JSON file."""
    try:
        with open(json_file, 'r') as f:
            in_object = False
            current_object = []
            
            for line in f:
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                    
                # Start of array or end of array
                if line == '[' or line == ']':
                    continue
                    
                # Start collecting object
                if line.startswith('{'):
                    in_object = True
                    current_object = [line]
                    continue
                
                # Continue collecting object
                if in_object:
                    current_object.append(line)
                    
                    # Check if object is complete
                    if line.startswith('}'):
                        # Remove trailing comma if present
                        if current_object[-1].endswith(','):
                            current_object[-1] = current_object[-1][:-1]
                            
                        try:
                            # Parse the complete object
                            question_dict = json.loads(''.join(current_object))
                            
                            # Ensure question has a UID
                            if 'uid' not in question_dict:
                                question_dict['uid'] = str(uuid4())
                                
                            # Create and yield Question object
                            yield Question.from_dict(question_dict)
                            
                        except json.JSONDecodeError as e:
                            logging.error(f"Error parsing question: {str(e)}")
                            
                        # Reset for next object
                        in_object = False
                        current_object = []
                        
    except FileNotFoundError:
        logging.error(f"File not found: {json_file}")
        raise
    except Exception as e:
        logging.error(f"Error reading file {json_file}: {str(e)}")
        raise

def load_questions(json_file):
    """Load questions from the given JSON file."""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON content is not an array")
            return [Question.from_dict(q) for q in data]
    except FileNotFoundError:
        logging.error(f"File not found: {json_file}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in {json_file}: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error reading file {json_file}: {str(e)}")
        raise

def save_questions(json_file, questions_to_update, questions_to_delete):
    """
    Update the JSON file with modifications and deletions.
    Args:
        json_file: Path to the JSON file
        questions_to_update: List of Question objects to update or add
        questions_to_delete: List of Question objects to remove
    """
    import tempfile
    import os
    import shutil
    
    # Convert lists to sets for O(1) lookup using UIDs
    questions_to_delete = {q.uid for q in questions_to_delete}
    questions_to_update = {q.uid: q for q in questions_to_update}
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        # Write opening bracket
        temp_file.write('[\n')
        first_item = True
        
        # Process existing questions
        try:
            for question in yield_questions(json_file):
                # Skip if question is marked for deletion
                if question.uid in questions_to_delete:
                    continue
                
                # Write comma if not first item
                if not first_item:
                    temp_file.write(',\n')
                first_item = False
                
                # Write updated or original question
                if question.uid in questions_to_update:
                    json.dump(questions_to_update[question.uid].to_dict(), temp_file, indent=2)
                    del questions_to_update[question.uid]
                else:
                    json.dump(question.to_dict(), temp_file, indent=2)
        
        except FileNotFoundError:
            # If file doesn't exist, we'll just create it with new questions
            pass
        
        # Append remaining new questions
        for question in questions_to_update.values():
            if not first_item:
                temp_file.write(',\n')
            first_item = False
            json.dump(question.to_dict(), temp_file, indent=2)
        
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

def append_question(json_file, question: Question):
    """
    Append a question to the JSON file. Creates new file if doesn't exist.
    Handles invalid JSON gracefully by creating new list.
    """
    try:
        questions = list(yield_questions(json_file))
    except (FileNotFoundError, json.JSONDecodeError):
        questions = []

    questions.append(question)

    try:
        with open(json_file, 'w') as f:
            json.dump([q.to_dict() for q in questions], f, indent=2)
    except IOError as e:
        print(f"Error saving to {json_file}: {str(e)}")
        raise

def create_index(json_file_path, index_file_path):
    """Create an index mapping question UIDs to their line positions in the file."""
    index = {}
    
    try:
        # First check if file exists and has content
        if not os.path.exists(json_file_path):
            logging.info(f"File {json_file_path} does not exist, creating empty file")
            with open(json_file_path, 'w') as f:
                json.dump([], f)
            return index

        # Read the entire file content
        with open(json_file_path, 'r') as f:
            content = f.read().strip()
            
        # If file is empty or just contains whitespace
        if not content:
            logging.info(f"File {json_file_path} is empty")
            with open(json_file_path, 'w') as f:
                json.dump([], f)
            return index
            
        # Try to parse the content
        data = json.loads(content)
        if not isinstance(data, list):
            logging.error("JSON content is not an array")
            raise ValueError("JSON content is not an array")
            
        # Create the index
        for question_dict in data:
            if 'uid' not in question_dict:
                question_dict['uid'] = str(uuid4())
            index[question_dict['uid']] = question_dict
            
        # Save the index
        with open(index_file_path, 'w') as f:
            json.dump(index, f, indent=2)
            
        logging.info(f"Successfully created index with {len(index)} questions")
        return index
            
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in {json_file_path}: {str(e)}")
        # Don't initialize with empty array if JSON is invalid
        raise
    except Exception as e:
        logging.error(f"Error creating index: {str(e)}")
        raise

def load_index(index_file_path):
    """
    Load the question index from a file.
    
    Args:
        index_file_path: Path to the index JSON file
        
    Returns:
        dict: Map of question UIDs to line numbers. Empty dict if file doesn't exist.
    """
    try:
        with open(index_file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def get_question_by_uid(json_file_path, uid):  # Removed index parameter as it's not needed
    """
    Get a single question by its UID.
    
    Args:
        json_file_path: Path to the JSON file containing questions
        uid: The UID of the question to retrieve
        
    Returns:
        Question: The requested question object
        
    Raises:
        KeyError: If the UID is not found
        ValueError: If the question cannot be parsed
    """
    try:
        with open(json_file_path, 'r') as f:
            for question in yield_questions(json_file_path):
                if question.uid == uid:
                    return question
        raise KeyError(f"Question with UID {uid} not found")
                
    except FileNotFoundError:
        raise FileNotFoundError(f"Question file not found: {json_file_path}")
    except Exception as e:
        raise ValueError(f"Error reading question: {str(e)}")

def update_question(json_file_path, index, question):
    """
    Update a specific question in the file, handling size changes appropriately.
    
    Args:
        json_file_path: Path to the JSON file containing questions
        index: Dictionary mapping UIDs to line numbers
        question: The updated Question object
        
    Raises:
        KeyError: If the question's UID is not found in the index
        ValueError: If there's an error updating the file
    """
    import tempfile
    import os
    import shutil
    
    if question.uid not in index:
        raise KeyError(f"Question with UID {question.uid} not found in index")
    
    target_line = index[question.uid]
    
    try:
        # Create a temporary file for writing
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            with open(json_file_path, 'r') as f:
                # Copy everything up to the target question
                for _ in range(target_line - 1):
                    line = f.readline()
                    temp_file.write(line)
                
                # Skip the original question by reading until we find its end
                brace_count = 0
                found_start = False
                
                while True:
                    line = f.readline()
                    if not line:
                        break
                        
                    if '{' in line and not found_start:
                        found_start = True
                        brace_count = 1
                    elif found_start:
                        brace_count += line.count('{')
                        brace_count -= line.count('}')
                        if brace_count == 0:
                            break
                
                # Write the updated question
                json.dump(question.to_dict(), temp_file, indent=2)
                
                # Check if we need a comma for the next item
                pos = f.tell()
                next_char = f.read(1)
                f.seek(pos)
                
                if next_char and next_char.strip():
                    temp_file.write(',\n')
                
                # Copy the rest of the file
                shutil.copyfileobj(f, temp_file)
        
        # Replace the original file with the temporary file
        try:
            os.replace(temp_file.name, json_file_path)
        except OSError:
            # If replace fails, try copy and delete
            shutil.copy2(temp_file.name, json_file_path)
            os.unlink(temp_file.name)
            
        # Recreate the index since positions may have changed
        new_index = create_index(json_file_path, os.path.join(os.path.dirname(json_file_path), 'questions.index'))
        index.clear()
        index.update(new_index)
        
    except Exception as e:
        # Clean up temp file if it exists
        if 'temp_file' in locals():
            try:
                os.unlink(temp_file.name)
            except:
                pass
        raise ValueError(f"Error updating question: {str(e)}")

def add_question(json_file_path, index, question):
    """
    Append a new question to the end of the JSON file and update the index.
    
    Args:
        json_file_path: Path to the JSON file containing questions
        index: Dictionary mapping UIDs to line numbers
        question: The Question object to add
    """
    try:
        with open(json_file_path, 'r+') as f:
            # Go to end of file minus closing bracket
            f.seek(0, 2)  # Seek to end
            pos = f.tell()
            
            # Read backwards until we find the closing bracket
            while pos > 0:
                pos -= 1
                f.seek(pos)
                char = f.read(1)
                if char == ']':
                    break
            
            # Go back to position before ]
            f.seek(pos)
            
            # If file is not empty (has other questions), add a comma
            if pos > 2:  # More than just "[]"
                f.write(',\n')
            
            # Write the new question
            json_str = json.dumps(question.to_dict(), indent=2)
            f.write(json_str)
            f.write('\n]')
            
            # Update index with new question's position
            # Line number is pos divided by average line length (estimated)
            # This is an approximation - for exact line number we'd need to count newlines
            avg_line_length = 50  # Estimated average line length
            approx_line = pos // avg_line_length
            index[question.uid] = approx_line
            
    except Exception as e:
        raise ValueError(f"Error adding question: {str(e)}")

def delete_question(json_file_path, index, uid):
    """
    Delete a question from the JSON file and update the index.
    
    Args:
        json_file_path: Path to the JSON file containing questions
        index: Dictionary mapping UIDs to line numbers
        uid: The UID of the question to delete
        
    Raises:
        KeyError: If the UID is not found in the index
        ValueError: If there's an error updating the file
    """
    import tempfile
    import os
    import shutil
    
    if uid not in index:
        raise KeyError(f"Question with UID {uid} not found in index")
    
    try:
        # Create a temporary file for writing
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            # Write opening bracket
            temp_file.write('[\n')
            first_item = True
            
            # Copy all questions except the one to delete
            for question in yield_questions(json_file_path):
                if question.uid != uid:
                    if not first_item:
                        temp_file.write(',\n')
                    json.dump(question.to_dict(), temp_file, indent=2)
                    first_item = False
            
            # Write closing bracket
            temp_file.write('\n]')
        
        # Replace the original file with the temporary file
        try:
            os.replace(temp_file.name, json_file_path)
        except OSError:
            # If replace fails, try copy and delete
            shutil.copy2(temp_file.name, json_file_path)
            os.unlink(temp_file.name)
        
        # Remove the deleted question from the index
        del index[uid]
        
        # Recreate the index since positions have changed
        new_index = create_index(json_file_path, os.path.join(os.path.dirname(json_file_path), 'questions.index'))
        index.clear()
        index.update(new_index)
        
    except Exception as e:
        # Clean up temp file if it exists
        if 'temp_file' in locals():
            try:
                os.unlink(temp_file.name)
            except:
                pass
        raise ValueError(f"Error deleting question: {str(e)}")

def save_index(index, index_file_path):
    """
    Save the index dictionary to a JSON file.
    
    Args:
        index: Dictionary mapping UIDs to line numbers
        index_file_path: Path where the index will be saved
        
    Raises:
        IOError: If there's an error writing to the file
    """
    try:
        with open(index_file_path, 'w') as f:
            json.dump(index, f, indent=2)
    except IOError as e:
        logging.error(f"Error saving index to {index_file_path}: {str(e)}")
        raise