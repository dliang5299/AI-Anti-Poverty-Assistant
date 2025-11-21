"""
Metrics Tracking Module for BenefitsFlow
Tracks conversations, downloads, and performance metrics
All code in UI folder - does not impact other members' code
"""

import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Dict, Any

# Database path - use /tmp in Docker/EC2, or local path for development
DB_DIR = Path("/tmp") if os.path.exists("/tmp") else Path(__file__).parent
DB_PATH = DB_DIR / "benefitsflow_metrics.db"


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    """Initialize database tables - run once on first deployment"""
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                message_count INTEGER DEFAULT 1
            );
            
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                programs TEXT
            );
            
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                response_time_ms INTEGER,
                rag_time_ms INTEGER,
                error_type TEXT,
                accuracy REAL,
                actionability REAL,
                simplicity REAL,
                empathy REAL
            );
            
            -- Create indexes for faster queries
            CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_downloads_timestamp ON downloads(timestamp);
            CREATE INDEX IF NOT EXISTS idx_downloads_type ON downloads(type);
            CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance(timestamp);
        ''')
        print(f"✅ Metrics database initialized at: {DB_PATH}")


def log_conversation(message_count: int = 1):
    """Log a conversation event"""
    try:
        with get_db() as conn:
            conn.execute(
                'INSERT INTO conversations (timestamp, message_count) VALUES (?, ?)',
                (datetime.utcnow().isoformat(), message_count)
            )
    except Exception as e:
        print(f"⚠️ Error logging conversation: {e}")


def log_download(download_type: str, programs: Optional[List[str]] = None):
    """
    Log a download event (checklist or calendar)
    
    Args:
        download_type: 'checklist' or 'calendar'
        programs: List of program names mentioned
    """
    try:
        programs_json = json.dumps(programs) if programs else None
        with get_db() as conn:
            conn.execute(
                'INSERT INTO downloads (timestamp, type, programs) VALUES (?, ?, ?)',
                (datetime.utcnow().isoformat(), download_type, programs_json)
            )
    except Exception as e:
        print(f"⚠️ Error logging download: {e}")


def log_performance(
    response_time_ms: Optional[int] = None,
    rag_time_ms: Optional[int] = None,
    error_type: Optional[str] = None,
    accuracy: Optional[float] = None,
    actionability: Optional[float] = None,
    simplicity: Optional[float] = None,
    empathy: Optional[float] = None
):
    """
    Log performance metrics
    
    Args:
        response_time_ms: Total response time in milliseconds
        rag_time_ms: RAG service call time in milliseconds
        error_type: Error type if any (e.g., 'HTTPStatusError', 'TimeoutError')
        accuracy: Evaluation score (0-1) - RESERVED FOR FUTURE USE (Godsee/Deric)
        actionability: Evaluation score (0-1) - RESERVED FOR FUTURE USE (Godsee/Deric)
        simplicity: Evaluation score (0-1) - RESERVED FOR FUTURE USE (Godsee/Deric)
        empathy: Evaluation score (0-1) - RESERVED FOR FUTURE USE (Godsee/Deric)
    
    Note: Evaluation scores (accuracy, actionability, simplicity, empathy) are not
    currently being logged. The database schema supports them for future implementation.
    """
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT INTO performance 
                (timestamp, response_time_ms, rag_time_ms, error_type, 
                 accuracy, actionability, simplicity, empathy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.utcnow().isoformat(),
                response_time_ms,
                rag_time_ms,
                error_type,
                accuracy,
                actionability,
                simplicity,
                empathy
            ))
    except Exception as e:
        print(f"⚠️ Error logging performance: {e}")


def get_monthly_stats(days: int = 30) -> Dict[str, Any]:
    """
    Get monthly statistics
    
    Args:
        days: Number of days to look back (default 30)
    
    Returns:
        Dictionary with statistics
    """
    try:
        with get_db() as conn:
            # Total conversations
            conversations_result = conn.execute('''
                SELECT COUNT(*) as total, SUM(message_count) as total_messages
                FROM conversations 
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
            ''', (days,)).fetchone()
            
            # Downloads by type
            downloads_result = conn.execute('''
                SELECT type, COUNT(*) as count
                FROM downloads 
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
                GROUP BY type
            ''', (days,)).fetchall()
            
            # Performance averages
            perf_result = conn.execute('''
                SELECT 
                    AVG(response_time_ms) as avg_response_time,
                    AVG(rag_time_ms) as avg_rag_time,
                    COUNT(CASE WHEN error_type IS NOT NULL THEN 1 END) as error_count
                FROM performance
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
            ''', (days,)).fetchone()
            
            # Program popularity from downloads
            programs_result = conn.execute('''
                SELECT programs
                FROM downloads
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
                  AND programs IS NOT NULL
            ''', (days,)).fetchall()
            
            # Count program mentions
            program_counts = {}
            for row in programs_result:
                try:
                    programs = json.loads(row['programs'])
                    if isinstance(programs, list):
                        for prog in programs:
                            program_counts[prog] = program_counts.get(prog, 0) + 1
                except:
                    pass
            
            return {
                'period_days': days,
                'conversations': {
                    'total': conversations_result['total'] or 0,
                    'total_messages': conversations_result['total_messages'] or 0
                },
                'downloads': {
                    row['type']: row['count'] for row in downloads_result
                },
                'performance': {
                    'avg_response_time_ms': round(perf_result['avg_response_time'] or 0, 2),
                    'avg_rag_time_ms': round(perf_result['avg_rag_time'] or 0, 2),
                    'error_count': perf_result['error_count'] or 0
                },
                'program_popularity': dict(sorted(
                    program_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10])  # Top 10 programs
            }
    except Exception as e:
        print(f"⚠️ Error getting monthly stats: {e}")
        return {}


def export_to_csv(output_dir: Optional[Path] = None) -> List[str]:
    """
    Export database tables to CSV files
    
    Args:
        output_dir: Directory to save CSV files (default: same as DB)
    
    Returns:
        List of created CSV file paths
    """
    try:
        import csv
        
        if output_dir is None:
            output_dir = DB_PATH.parent
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        files_created = []
        
        with get_db() as conn:
            tables = ['conversations', 'downloads', 'performance']
            
            for table in tables:
                cursor = conn.execute(f'SELECT * FROM {table}')
                columns = [description[0] for description in cursor.description]
                
                csv_path = output_dir / f'{table}.csv'
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(columns)
                    writer.writerows(cursor.fetchall())
                
                files_created.append(str(csv_path))
        
        return files_created
    except Exception as e:
        print(f"⚠️ Error exporting to CSV: {e}")
        return []


# Initialize database on import (only creates tables if they don't exist)
try:
    init_db()
except Exception as e:
    print(f"⚠️ Could not initialize metrics database: {e}")

