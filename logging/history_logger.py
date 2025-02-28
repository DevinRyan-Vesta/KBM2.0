from datetime import datetime
import sqlite3
import json

def log_history(action, item_type, item_id, name_address, user, details):
    """
    Logs a transaction to the HISTORY table in SQLite database.
    :param action: Action performed (e.g., "Checked Out", "Returned", "Assigned", "Added").
    :param item_type: Type of item (e.g., "Keys", "LockBoxes", "Signs").
    :param item_id: ID of the item.
    :param name_address: Address/Name of the item.
    :param user: The user performing the action.
    :param details: Additional details about the transaction.
    """
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect('history.db')
        cursor = conn.cursor()

        # Create the HISTORY table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS HISTORY (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                action TEXT,
                item_type TEXT,
                item_id TEXT,
                name_address TEXT,
                user TEXT,
                details TEXT
            )
        ''')

        # Prepare the log entry with JSON format
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = (
            timestamp,
            json.dumps(action),
            json.dumps(item_type),
            json.dumps(item_id),
            json.dumps(name_address),
            json.dumps(user),
            json.dumps(details)
        )

        # Insert the log entry into the HISTORY table
        cursor.execute('''
            INSERT INTO HISTORY (timestamp, action, item_type, item_id, name_address, user, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', log_entry)

        # Commit the transaction and close the connection
        conn.commit()
        conn.close()

        print(f"Logged history: {log_entry}")
    except Exception as e:
        print(f"Error logging history: {e}")
