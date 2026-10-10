
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chain_checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                chain_id INTEGER NOT NULL,
                contract_address TEXT NOT NULL,
                block_number INTEGER NOT NULL,
                block_hash TEXT NOT NULL,
                tx_hash TEXT NOT NULL
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


def save_checkpoint(checkpoint):
    """블록체인 체크포인트 저장"""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO chain_checkpoints (
                checkpoint_id,
                chain_id,
                contract_address,
                block_number,
                block_hash,
                tx_hash
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(checkpoint_id)
            DO UPDATE SET
                chain_id = excluded.chain_id,
                contract_address = excluded.contract_address,
                block_number = excluded.block_number,
                block_hash = excluded.block_hash,
                tx_hash = excluded.tx_hash
            """,
            (
                checkpoint["checkpoint_id"],
                checkpoint["chain_id"],
                checkpoint["contract_address"],
                checkpoint["block_number"],
                checkpoint["block_hash"],
                checkpoint["tx_hash"]
            )
        )


def load_checkpoint(checkpoint_id):
    """저장된 체크포인트 조회"""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM chain_checkpoints
            WHERE checkpoint_id = ?
            """,
            (checkpoint_id,)
        ).fetchone()

    return dict(row) if row else None
