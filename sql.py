import sqlite3
import json

DATABASE_FILE = "questions.db"


def create_database():
    """Creates the SQLite database and defines the tables."""

    conn = None  # Initialize conn to None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Create Question table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Question (
                uid TEXT PRIMARY KEY,
                content_id INTEGER NOT NULL,
                answer TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                tags TEXT NOT NULL,  -- Serialized JSON
                explanation_id INTEGER NOT NULL,
                FOREIGN KEY (content_id) REFERENCES QuestionContent(content_id),
                FOREIGN KEY (explanation_id) REFERENCES QuestionExplanation(explanation_id)
            )
        """)

        # Create QuestionContent table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS QuestionContent (
                content_id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                image TEXT
            )
        """)

        # Create QuestionOption table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS QuestionOption (
                option_id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id TEXT NOT NULL,
                option_key TEXT NOT NULL,
                text TEXT NOT NULL,
                image TEXT,
                FOREIGN KEY (question_id) REFERENCES Question(uid)
            )
        """)

        # Create QuestionExplanation table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS QuestionExplanation (
                explanation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL
            )
        """)

        # Create indexes for foreign key columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_question_content_id ON Question (content_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_question_explanation_id ON Question (explanation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_question_option_question_id ON QuestionOption (question_id)")

        conn.commit()
        print("Database and tables created successfully.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    create_database()