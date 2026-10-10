
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "fullproof.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """SQLite 테이블 생성"""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)


def save_case(case):
    """사건 및 수사 단계 정보를 저장"""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cases (case_id, data)
            VALUES (?, ?)
            ON CONFLICT(case_id)
            DO UPDATE SET data = excluded.data
            """,
            (
                case["case_id"],
                json.dumps(case, ensure_ascii=False)
            )
        )


def load_cases():
    """저장된 사건 정보 전체 조회"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT case_id, data FROM cases"
        ).fetchall()

    return {
        row["case_id"]: json.loads(row["data"])
        for row in rows
    }
