from fastapi import APIRouter
from pydantic import BaseModel
from config import settings
import os
import sqlite3
import json
from typing import List
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def init_db():
    db_path = settings.database_url.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            date TEXT,
            original_text TEXT,
            ai_answer TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", db_path)


init_db()


def _ensure_table(conn: sqlite3.Connection):
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            date TEXT,
            original_text TEXT,
            ai_answer TEXT
        )
        """
    )
    conn.commit()


class HistoryItem(BaseModel):
    date: str
    original: List[str]
    answer: List[str]


@router.get("/get_student_history/{name}")
def get_student_history(name: str):
    db_path = settings.database_url.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        logger.info("History requested for %s but DB not found at %s", name, db_path)
        return []
    conn = sqlite3.connect(db_path)
    _ensure_table(conn)
    c = conn.cursor()
    c.execute(
        "SELECT date, original_text, ai_answer FROM analysis_results WHERE student_name=? ORDER BY date ASC, id ASC",
        (name,),
    )
    rows = c.fetchall()
    res = []
    for date, original_text, ai_answer in rows:
        try:
            original = json.loads(original_text)
        except Exception:
            original = []
        try:
            answer = json.loads(ai_answer)
        except Exception:
            answer = []
        res.append({"date": date, "original": original, "answer": answer})
    conn.close()
    logger.info("Fetched %d history rows for %s", len(res), name)
    return res


def insert_analysis_result(student_name: str, date: str, original: str, ai_answer: str):
    db_path = settings.database_url.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    _ensure_table(conn)
    c = conn.cursor()
    c.execute(
        "INSERT INTO analysis_results (student_name, date, original_text, ai_answer) VALUES (?, ?, ?, ?)",
        (student_name, date, original, ai_answer),
    )
    conn.commit()
    conn.close()
    logger.debug("Inserted analysis result: student=%s, date=%s", student_name, date)


def delete_analysis_results_for_date(student_name: str, date: str):
    db_path = settings.database_url.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    _ensure_table(conn)
    c = conn.cursor()
    c.execute(
        "DELETE FROM analysis_results WHERE student_name=? AND date=?",
        (student_name, date),
    )
    conn.commit()
    conn.close()
    logger.debug("Deleted previous results for %s on %s", student_name, date)
