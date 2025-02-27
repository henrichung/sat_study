#!/usr/bin/env python3
"""
Database connection utilities for SAT Study application
"""
import os
import sqlite3
import logging

def dict_factory(cursor, row):
    """Convert SQLite row to dictionary"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_db_connection(db_path: str, create: bool = False) -> sqlite3.Connection:
    """
    Get a connection to the SQLite database
    
    Args:
        db_path: Path to the database file
        create: If True, create the database if it doesn't exist
    
    Returns:
        Connection to the database
    
    Raises:
        FileNotFoundError: If the database file doesn't exist and create is False
    """
    # Check if directory exists, create if needed
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # Check if file exists
    if not os.path.exists(db_path) and not create:
        raise FileNotFoundError(f"Database file not found: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    
    return conn