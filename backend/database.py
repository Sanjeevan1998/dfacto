import sqlite3
import json
from datetime import datetime

DB_FILE = "crawler.db"

def get_connection():
    return sqlite3.connect(DB_FILE, timeout=15.0, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Table for configuration (keywords, timer_interval in minutes)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY DEFAULT 1,
            keywords TEXT,
            timer_interval INTEGER
        )
    ''')
    # Pre-populate with default config if not exists
    cursor.execute('INSERT OR IGNORE INTO config (id, keywords, timer_interval) VALUES (1, "AI, Technology", 60)')
    
    # Table for headlines
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS headlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source TEXT,
            url TEXT,
            snippet TEXT,
            associated_keyword TEXT,
            verdict TEXT DEFAULT 'N/A',
            confidence_score REAL DEFAULT 0.0,
            explanation TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Try to add the columns for backwards compatibility
    try:
        cursor.execute('ALTER TABLE headlines ADD COLUMN associated_keyword TEXT')
    except sqlite3.OperationalError:
        pass # Column already exists
    try:
        cursor.execute("ALTER TABLE headlines ADD COLUMN verdict TEXT DEFAULT 'N/A'")
        cursor.execute('ALTER TABLE headlines ADD COLUMN confidence_score REAL DEFAULT 0.0')
        cursor.execute('ALTER TABLE headlines ADD COLUMN explanation TEXT')
    except sqlite3.OperationalError:
        pass # Columns already exist

    conn.commit()
    conn.close()

def get_config():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT keywords, timer_interval FROM config WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"keywords": row[0], "timer_interval": row[1]}
    return {"keywords": "", "timer_interval": 60}

def update_config(keywords: str, timer_interval: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE config SET keywords = ?, timer_interval = ? WHERE id = 1
    ''', (keywords, timer_interval))
    conn.commit()
    conn.close()

def clear_headlines():
    """Clear all old headlines from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM headlines')
    conn.commit()
    conn.close()

def save_headlines(headlines: list, associated_keyword: str = ""):
    """
    Saves a list of headlines to the database.
    headlines format: [{"title": "...", "source": "...", "url": "...", "snippet": "...", "verdict": "...", "confidence": 0.0, "explanation": "..."}, ...]
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    for hl in headlines:
        cursor.execute('''
            INSERT INTO headlines (title, source, url, snippet, associated_keyword, verdict, confidence_score, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            hl.get("title", ""), 
            hl.get("source", ""), 
            hl.get("url", ""), 
            hl.get("snippet", ""), 
            associated_keyword,
            hl.get("verdict", "N/A"),
            hl.get("confidence_score", 0.0), # fallback to default if not returned
            hl.get("explanation", "")
        ))
    conn.commit()
    conn.close()

def get_headlines(limit=50):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM headlines ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Initialize db on module import
init_db()
