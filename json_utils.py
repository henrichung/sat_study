import json
import logging
import os
import shutil  # Import shutil for move
import tempfile
import uuid
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class QuestionOption:
    text: str
    image: Optional[str] = None


@dataclass
class QuestionExplanation:
    text: str


@dataclass
class QuestionContent:
    text: str
    image: Optional[str] = None


@dataclass
class Question:
    content: QuestionContent
    options: dict[str, QuestionOption]
    answer: str
    difficulty: str
    tags: List[str]
    explanation: QuestionExplanation
    uid: str = None

    def __post_init__(self):
        if self.uid is None:
            self.uid = str(uuid.uuid4())

    @property
    def text(self) -> str:
        return self.content.text

    @property
    def image(self) -> Optional[str]:
        return self.content.image

    @classmethod
    def from_dict(cls, data: dict) -> 'Question':
        options = {k: QuestionOption(**v) for k, v in data.get('options', {}).items()}
        explanation = QuestionExplanation(**data.get('explanation', {'text': ''}))
        content = QuestionContent(
            text=data.get('question', {}).get('text', ''),
            image=data.get('question', {}).get('image')
        )
        question_data = {
            'content': content,
            'options': options,
            'answer': data.get('answer', ''),
            'difficulty': data.get('difficulty', ''),
            'tags': data.get('tags', ),
            'explanation': explanation,
            'uid': data.get('uid')
        }
        return cls(**question_data)

    def to_dict(self) -> dict:
        return {
            'question': {
                'text': self.content.text,
                'image': self.content.image
            },
            'options': {
                k: {'text': v.text, 'image': v.image}
                for k, v in self.options.items()
            },
            'answer': self.answer,
            'difficulty': self.difficulty,
            'tags': self.tags,
            'explanation': {
                'text': self.explanation.text
            },
            'uid': self.uid
        }


def yield_questions(json_file):
    """Yield questions one at a time from the JSON file."""
    if not os.path.exists(json_file):  # Check for file existence first
        logging.warning(f"File not found: {json_file}, yielding no questions.")
        return  # Early return if file doesn't exist

    try:
        with open(json_file, 'r') as f:
            in_object = False
            current_object = []

            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line == '[' or line == '':
                    continue
                if line.startswith('{'):
                    in_object = True
                    current_object = [line]
                    continue
                if in_object:
                    current_object.append(line)
                    if line.startswith('}'):
                        if current_object[-1].endswith(','):
                            current_object[-1] = current_object[-1][:-1]
                        try:
                            question_dict = json.loads(''.join(current_object))
                            if 'uid' not in question_dict:  # Ensure UID exists
                                question_dict['uid'] = str(uuid.uuid4())
                            yield Question.from_dict(question_dict)
                        except json.JSONDecodeError as e:
                            logging.error(f"Error parsing question: {str(e)}")
                        in_object = False
                        current_object = []
    except Exception as e:  # Catch any other reading error
        logging.error(f"Error reading file {json_file}: {str(e)}")
        raise


def load_questions(json_file):
    """Load questions from the given JSON file."""
    if not os.path.exists(json_file):  # Check if the file exists
        logging.warning(f"File not found: {json_file}, returning empty list.")
        return []  # Return an empty list if the file doesn't exist

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON content is not an array")
            return [Question.from_dict(q) for q in data]
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in {json_file}: {str(e)}")
        raise
    except Exception as e:  # Catch any other error during file reading
        logging.error(f"Error reading file {json_file}: {str(e)}")
        raise


def save_questions(json_file, questions_to_update, questions_to_delete=[]):
    """Update JSON file; combines update/delete for efficiency."""
    try:
        # Load existing questions, handling file not found gracefully.
        if os.path.exists(json_file):
            questions = load_questions(json_file)
        else:
            questions = []  # Start with an empty list if file doesn't exist.
            logging.warning(f"Question file {json_file} not found. Creating new file.")

        update_map = {q.uid: q for q in questions_to_update}
        delete_uids = {q.uid for q in questions_to_delete}

        updated_questions = []
        for q in questions:
            if q.uid in update_map:
                # Update existing question
                updated_questions.append(update_map[q.uid])
            elif q.uid not in delete_uids:
                # Keep existing question (not marked for deletion)
                updated_questions.append(q)

        # Add new questions (those not already present)
        for q in questions_to_update:
            if q.uid not in (existing_q.uid for existing_q in questions):
                updated_questions.append(q)

        _write_questions_to_file(json_file, updated_questions)

        # Rebuild the index after *any* change
        index_file = os.path.join(os.path.dirname(json_file), "questions.index")
        create_index(json_file, index_file)


    except Exception as e:
        logging.error(f"Failed to save question: {str(e)}")  # Added logging here
        raise ValueError(f"Error saving questions: {str(e)}")


def _write_questions_to_file(json_file, questions):
    """Helper function to write questions to file using tempfile."""
    temp_file = json_file + '.tmp'  # Use a .tmp extension
    with open(temp_file, 'w') as f:
        json.dump([q.to_dict() for q in questions], f, indent=2)
    os.replace(temp_file, json_file)  # Atomic replacement


def append_question(json_file, question):
    """Append a question to the JSON file (using save_questions)."""
    try:
        save_questions(json_file, [question])  # Use save_questions for consistency

    except Exception as e:
        logging.error(f"Failed to save question: {str(e)}")  # Added logging here
        raise ValueError(f"Error appending question: {str(e)}")


def create_index(json_file_path, index_file_path):
    """Create an index (list of UIDs)."""
    index = []
    try:
        if not os.path.exists(json_file_path):
            logging.info(f"File {json_file_path} does not exist, creating empty file")
            with open(json_file_path, 'w') as f:
                json.dump([], f)
            return index

        questions = load_questions(json_file_path)
        index = [question.uid for question in questions]

        with open(index_file_path, 'w') as f:
            json.dump(index, f, indent=2)  # Store as a simple list

        logging.info(f"Successfully created index with {len(index)} questions")
        return index
    except Exception as e:
        logging.error(f"Error creating index: {str(e)}")
        raise


def load_index(index_file_path):
    """Load the question index (list of UIDs)."""
    try:
        with open(index_file_path, 'r') as f:
            return json.load(f)  # Load the list
    except (FileNotFoundError, json.JSONDecodeError):
        return []  # Return empty list if not found or invalid


def get_question_by_uid(json_file_path, uid):
    """Get a single question by its UID (using yield_questions)."""
    try:
        for question in yield_questions(json_file_path):
            if question.uid == uid:
                return question
        raise KeyError(f"Question with UID {uid} not found")  # Consistent error
    except FileNotFoundError:
        raise FileNotFoundError(f"Question file not found: {json_file_path}")
    except Exception as e:
        raise ValueError(f"Error reading question: {str(e)}")


def update_question(json_file_path, index, question):
    """Update a specific question (using save_questions)."""
    try:
        save_questions(json_file_path, [question])  # Use save_questions for consistency
    except Exception as e:
        logging.error(f"Failed to update question: {str(e)}")  # Added logging here
        raise ValueError(f"Error updating question: {str(e)}")


def add_question(json_file_path, index, question):
    """Append a new question (using save_questions)."""
    try:
        save_questions(json_file_path, [question])  # Use save_questions for consistency
    except Exception as e:
        logging.error(f"Failed to add question: {str(e)}")  # Added logging here
        raise ValueError(f"Error adding question: {str(e)}")


def delete_question(json_file_path, index, uid):
    """Delete a question (using save_questions)."""
    try:
        # We don't need to check if UID is present, save_questions handles it
        dummy_question = Question(
            content=QuestionContent(text="dummy"),
            options={},
            answer="dummy",
            difficulty="dummy",
            tags=[],
            explanation=QuestionExplanation(text="dummy"),
            uid=uid
        )  # Create a dummy question with the UID
        save_questions(json_file_path, [], [dummy_question])
    except Exception as e:
        logging.error(f"Failed to delete question: {str(e)}")  # Added logging here
        raise ValueError(f"Error deleting question: {str(e)}")


def save_index(index, index_file_path):
    """Save the index (list of UIDs) to a file."""
    try:
        # Create the temporary file in the *same* directory as the target file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, dir=os.path.dirname(index_file_path))
        with temp_file:
            json.dump(index, temp_file, indent=2)
        # Use shutil.move for cross-device compatibility
        shutil.move(temp_file.name, index_file_path)
    except Exception as e:
        try:
            os.unlink(temp_file.name)  # Clean up temp file on error
        except OSError:
            pass  # Best effort cleanup
        raise IOError(f"Error saving index: {str(e)}")
