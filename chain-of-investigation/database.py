
import json
import sqlite3
from contextlib import closing
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


def load_latest_case_checkpoint(case_id):
    """해당 사건의 최신 블록체인 체크포인트 조회"""

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM chain_checkpoints
            WHERE checkpoint_id = ?
            """,
            (f"CASE_{case_id}_LATEST",)
        ).fetchone()

    return dict(row) if row else None


def list_case_checkpoints(case_id):
    """특정 사건의 체크포인트 목록 조회"""

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM chain_checkpoints
            WHERE checkpoint_id LIKE ?
            ORDER BY block_number ASC, checkpoint_id ASC
            """,
            (f"CASE_{case_id}_%",)
        ).fetchall()

    return [dict(row) for row in rows]

def save_proof_result_atomic(case, history_checkpoint, latest_checkpoint):
    """
    Proof 기록 이후 SQLite 상태를 한 번에 저장한다.
    중간에 실패하면 SQLite 변경 전체를 롤백한다.
    """
    with closing(get_connection()) as conn:
        try:
            conn.execute("BEGIN")

            for checkpoint in (history_checkpoint, latest_checkpoint):
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

            conn.commit()

        except Exception:
            conn.rollback()
            raise

# FullProof v1.1 - 영속 상태 저장
# ==========================================

import base64
from contextlib import closing


def _v11_json_default(value):
    # Proof 원본 바이트를 JSON에 안전하게 저장
    if isinstance(value, bytes):
        return {
            "__fullproof_bytes_b64__": base64.b64encode(
                value
            ).decode("ascii")
        }

    raise TypeError(
        f"Unsupported v1.1 storage type: {type(value)}"
    )


def _v11_json_hook(value):
    if (
        len(value) == 1
        and "__fullproof_bytes_b64__" in value
    ):
        return base64.b64decode(
            value["__fullproof_bytes_b64__"],
            validate=True
        )

    return value


def save_v11_store(store_name, store):
    """
    v1.1 메모리 딕셔너리의 스냅샷을 SQLite에 저장.
    tuple 키와 Proof 원본 bytes를 보존한다.
    """

    if store_name not in (
        "proof_drafts",
        "mapping_history",
        "verification_results",
        "verification_idempotency"
    ):
        raise ValueError("Unsupported v1.1 store")

    entries = [
        {
            "key": list(key) if isinstance(key, tuple) else key,
            "tuple_key": isinstance(key, tuple),
            "value": value
        }
        for key, value in store.items()
    ]

    serialized = json.dumps(
        entries,
        ensure_ascii=False,
        default=_v11_json_default
    )

    with closing(get_connection()) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS v11_state (
                    store_name TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
            """)

            conn.execute("""
                INSERT INTO v11_state (store_name, data)
                VALUES (?, ?)
                ON CONFLICT(store_name)
                DO UPDATE SET data = excluded.data
            """, (store_name, serialized))


def load_v11_store(store_name):
    """SQLite에서 v1.1 상태 복원"""

    with closing(get_connection()) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS v11_state (
                    store_name TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
            """)

            row = conn.execute(
                """
                SELECT data
                FROM v11_state
                WHERE store_name = ?
                """,
                (store_name,)
            ).fetchone()

    if row is None:
        return {}

    entries = json.loads(
        row["data"],
        object_hook=_v11_json_hook
    )

    restored = {}

    for entry in entries:
        key = entry["key"]

        if entry["tuple_key"]:
            key = tuple(key)

        restored[key] = entry["value"]

    return restored
