import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple, Any

DB_PATH = '/mlcv2/WorkingSpace/Personal/quannh/Project/Project/TRNS-AI/ntmkim/Work/docsqa-dev_local/sql-agent-master/data/data.db'

def get_connection():
    """Get a database connection."""
    try:
        return sqlite3.connect(DB_PATH)
    except sqlite3.Error as e:
        raise Exception(f"Failed to connect to database: {e}")

def execute_query(query: str) -> str:
    """
    Execute a SQL query with comprehensive error handling.
    
    Args:
        query (str): The SQL query to execute
        
    Returns:
        str: Query results as string
        
    Raises:
        Exception: If there's an error during query execution or if query modifies database
    """
    if not query or not query.strip():
        raise Exception("Query cannot be empty or None")
    
    query = query.strip()
    
    # Only allow SELECT queries for security
    if not query.lower().startswith('select'):
        raise Exception("Cannot process query that modifies the database. Only SELECT queries are allowed.")
    
    conn = None
    cursor = None
    
    try:
        # Get database connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Execute the query
        cursor.execute(query)
        
        # Fetch all results
        result = cursor.fetchall()
        
        # Convert results to string format
        if not result:
            return "No results found"
        
        # Format results as a table-like structure
        formatted_result = []
        for i, row in enumerate(result, 1):
            formatted_result.append(f"Row {i}: {row}")
        
        return "\n".join(formatted_result)
        
    except sqlite3.OperationalError as e:
        # Handle SQL syntax errors, table doesn't exist, etc.
        error_msg = str(e)
        if "no such table" in error_msg.lower():
            raise Exception(f"Table not found: {error_msg}")
        elif "no such column" in error_msg.lower():
            raise Exception(f"Column not found: {error_msg}")
        elif "syntax error" in error_msg.lower():
            raise Exception(f"SQL syntax error: {error_msg}")
        else:
            raise Exception(f"Database operation error: {error_msg}")
            
    except sqlite3.IntegrityError as e:
        # Handle constraint violations
        raise Exception(f"Data integrity error: {e}")
        
    except sqlite3.DatabaseError as e:
        # Handle database-level errors
        raise Exception(f"Database error: {e}")
        
    except sqlite3.Error as e:
        # Handle other SQLite-specific errors
        raise Exception(f"SQLite error: {e}")
        
    except Exception as e:
        # Handle any other unexpected errors
        raise Exception(f"Unexpected error during query execution: {e}")
        
    finally:
        # Always close cursor and connection
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def execute_query_safe(query: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Execute a query safely and return a tuple of (success, result, error_message).
    
    Args:
        query (str): The SQL query to execute
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: 
            - success: True if query executed successfully
            - result: Query results if successful, None otherwise
            - error_message: Error message if failed, None otherwise
    """
    try:
        result = execute_query(query)
        return True, result, None
    except Exception as e:
        return False, None, str(e)