#!/usr/bin/env python3
"""
Database operations for SAT Study application
"""
import os
import logging
import uuid
from typing import List, Optional, Dict, Any

from src.core.db.connection import get_db_connection
from src.models.question import QuestionOption, QuestionExplanation, QuestionContent, Question

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def question_from_db_rows(question_row: Dict[str, Any], 
                         options_rows: List[Dict[str, Any]],
                         tags_rows: List[Dict[str, Any]],
                         explanation_row: Dict[str, Any]) -> Question:
    """Convert database rows to a Question object"""
    
    # Create question content
    content = QuestionContent(
        text=question_row.get('question_text', ''),
        image=question_row.get('question_image')
    )
    
    # Create options dictionary
    options = {}
    for option in options_rows:
        options[option['option_key']] = QuestionOption(
            text=option['option_text'],
            image=option['option_image']
        )
    
    # Get tags list
    tags = [tag['name'] for tag in tags_rows]
    
    # Create explanation
    explanation = QuestionExplanation(
        text=explanation_row.get('explanation_text', '') if explanation_row else ''
    )
    
    # Create and return Question object
    return Question(
        content=content,
        options=options,
        answer=question_row.get('answer', ''),
        difficulty=question_row.get('difficulty', ''),
        tags=tags,
        explanation=explanation,
        uid=question_row.get('uid')
    )

def get_question_by_uid(db_path: str, uid: str) -> Optional[Question]:
    """Get a question by its UID"""
    conn = None
    try:
        conn = get_db_connection(db_path)
        
        # Get question
        question_query = """
        SELECT uid, question_text, question_image, answer, difficulty
        FROM questions
        WHERE uid = ?
        """
        question_row = conn.execute(question_query, (uid,)).fetchone()
        
        if not question_row:
            return None
        
        # Get options
        options_query = """
        SELECT option_key, option_text, option_image
        FROM options
        WHERE question_uid = ?
        """
        options_rows = conn.execute(options_query, (uid,)).fetchall()
        
        # Get tags
        tags_query = """
        SELECT t.name
        FROM tags t
        JOIN question_tags qt ON t.id = qt.tag_id
        WHERE qt.question_uid = ?
        """
        tags_rows = conn.execute(tags_query, (uid,)).fetchall()
        
        # Get explanation
        explanation_query = """
        SELECT explanation_text
        FROM explanations
        WHERE question_uid = ?
        """
        explanation_row = conn.execute(explanation_query, (uid,)).fetchone()
        
        return question_from_db_rows(question_row, options_rows, tags_rows, explanation_row)
    
    except Exception as e:
        logging.error(f"Error getting question {uid}: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def load_questions(db_path: str, limit: int = None, offset: int = 0, 
                  tags: List[str] = None, difficulty: str = None) -> List[Question]:
    """Load questions from the database with optional filtering"""
    conn = None
    try:
        conn = get_db_connection(db_path)
        
        # Build query based on filters
        query_parts = ["SELECT uid FROM questions"]
        query_params = []
        
        where_clauses = []
        
        # Add tag filter if provided
        if tags and len(tags) > 0:
            placeholders = ", ".join(["?"] * len(tags))
            where_clauses.append(f"""
            uid IN (
                SELECT question_uid 
                FROM question_tags 
                JOIN tags ON question_tags.tag_id = tags.id 
                WHERE tags.name IN ({placeholders})
            )
            """)
            query_params.extend(tags)
        
        # Add difficulty filter if provided
        if difficulty:
            where_clauses.append("difficulty = ?")
            query_params.append(difficulty)
        
        # Combine where clauses
        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))
        
        # Add pagination
        query_parts.append("ORDER BY created_at DESC")
        
        if limit is not None:
            query_parts.append("LIMIT ?")
            query_params.append(limit)
        
        if offset > 0:
            query_parts.append("OFFSET ?")
            query_params.append(offset)
        
        # Execute query to get UIDs
        uids_query = " ".join(query_parts)
        uids_rows = conn.execute(uids_query, query_params).fetchall()
        
        # Load each question
        questions = []
        for row in uids_rows:
            uid = row['uid']
            question = get_question_by_uid(db_path, uid)
            if question:
                questions.append(question)
        
        return questions
    
    except Exception as e:
        logging.error(f"Error loading questions: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def save_question(db_path: str, question: Question, is_new: bool = False) -> bool:
    """Save a question to the database (insert or update)"""
    conn = None
    try:
        conn = get_db_connection(db_path)
        
        # Start transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Generate UID if this is a new question
        if is_new and not question.uid:
            question.uid = str(uuid.uuid4())
        
        # Insert or update question
        question_query = """
        INSERT OR REPLACE INTO questions 
        (uid, question_text, question_image, answer, difficulty) 
        VALUES (?, ?, ?, ?, ?)
        """
        conn.execute(question_query, (
            question.uid,
            question.content.text,
            question.content.image,
            question.answer,
            question.difficulty
        ))
        
        # Delete existing options (will be replaced)
        conn.execute("DELETE FROM options WHERE question_uid = ?", (question.uid,))
        
        # Insert options
        for option_key, option in question.options.items():
            options_query = """
            INSERT INTO options 
            (question_uid, option_key, option_text, option_image) 
            VALUES (?, ?, ?, ?)
            """
            conn.execute(options_query, (
                question.uid,
                option_key,
                option.text,
                option.image
            ))
        
        # Handle tags (more complex)
        # First, remove existing tag relationships for this question
        conn.execute("DELETE FROM question_tags WHERE question_uid = ?", (question.uid,))
        
        # Then add the new tags
        for tag in question.tags:
            # Ensure tag exists
            conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            
            # Get tag ID
            tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()['id']
            
            # Create relationship
            conn.execute("""
            INSERT OR IGNORE INTO question_tags (question_uid, tag_id) 
            VALUES (?, ?)
            """, (question.uid, tag_id))
        
        # Update explanation
        explanation_query = """
        INSERT OR REPLACE INTO explanations 
        (question_uid, explanation_text) 
        VALUES (?, ?)
        """
        conn.execute(explanation_query, (
            question.uid,
            question.explanation.text
        ))
        
        # Commit transaction
        conn.commit()
        return True
    
    except Exception as e:
        logging.error(f"Error saving question {question.uid}: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def delete_question(db_path: str, uid: str) -> bool:
    """Delete a question from the database"""
    conn = None
    try:
        conn = get_db_connection(db_path)
        
        # Start transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Delete question (will cascade to related tables due to foreign key constraints)
        conn.execute("DELETE FROM questions WHERE uid = ?", (uid,))
        
        # Commit transaction
        conn.commit()
        return True
    
    except Exception as e:
        logging.error(f"Error deleting question {uid}: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_all_tags(db_path: str) -> List[str]:
    """Get a list of all tags in the database"""
    conn = None
    try:
        conn = get_db_connection(db_path)
        
        # Get all tags
        tags_query = "SELECT name FROM tags ORDER BY name"
        tags_rows = conn.execute(tags_query).fetchall()
        
        return [row['name'] for row in tags_rows]
    
    except Exception as e:
        logging.error(f"Error getting tags: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def get_question_count(db_path: str, tags: List[str] = None, difficulty: str = None) -> int:
    """Get the count of questions matching the filters"""
    conn = None
    try:
        conn = get_db_connection(db_path)
        
        # Build query based on filters
        query_parts = ["SELECT COUNT(*) as count FROM questions"]
        query_params = []
        
        where_clauses = []
        
        # Add tag filter if provided
        if tags and len(tags) > 0:
            placeholders = ", ".join(["?"] * len(tags))
            where_clauses.append(f"""
            uid IN (
                SELECT question_uid 
                FROM question_tags 
                JOIN tags ON question_tags.tag_id = tags.id 
                WHERE tags.name IN ({placeholders})
            )
            """)
            query_params.extend(tags)
        
        # Add difficulty filter if provided
        if difficulty:
            where_clauses.append("difficulty = ?")
            query_params.append(difficulty)
        
        # Combine where clauses
        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))
        
        # Execute query to get count
        count_query = " ".join(query_parts)
        count_row = conn.execute(count_query, query_params).fetchone()
        
        return count_row['count']
    
    except Exception as e:
        logging.error(f"Error getting question count: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def search_questions(db_path: str, search_text: str, limit: int = None, offset: int = 0) -> List[Question]:
    """Search questions by text, options, tags, or explanation"""
    conn = None
    try:
        conn = get_db_connection(db_path)
        
        # Build query
        query = """
        SELECT DISTINCT q.uid
        FROM questions q
        LEFT JOIN options o ON q.uid = o.question_uid
        LEFT JOIN explanations e ON q.uid = e.question_uid
        LEFT JOIN question_tags qt ON q.uid = qt.question_uid
        LEFT JOIN tags t ON qt.tag_id = t.id
        WHERE 
            q.question_text LIKE ? OR
            o.option_text LIKE ? OR
            e.explanation_text LIKE ? OR
            t.name LIKE ? OR
            q.difficulty LIKE ?
        ORDER BY q.created_at DESC
        """
        
        # Add pagination
        if limit is not None:
            query += " LIMIT ?"
        
        if offset > 0:
            query += " OFFSET ?"
        
        # Prepare parameters
        search_param = f"%{search_text}%"
        query_params = [search_param, search_param, search_param, search_param, search_param]
        
        if limit is not None:
            query_params.append(limit)
        
        if offset > 0:
            query_params.append(offset)
        
        # Execute query to get UIDs
        uids_rows = conn.execute(query, query_params).fetchall()
        
        # Load each question
        questions = []
        for row in uids_rows:
            uid = row['uid']
            question = get_question_by_uid(db_path, uid)
            if question:
                questions.append(question)
        
        return questions
    
    except Exception as e:
        logging.error(f"Error searching questions: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def export_questions_to_list(db_path: str, question_uids: List[str]) -> List[Dict]:
    """Export specific questions as dictionaries for worksheet generation"""
    conn = None
    try:
        conn = get_db_connection(db_path)
        
        # Get questions
        questions = []
        for uid in question_uids:
            question = get_question_by_uid(db_path, uid)
            if question:
                questions.append(question.to_dict())
        
        return questions
    
    except Exception as e:
        logging.error(f"Error exporting questions: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()