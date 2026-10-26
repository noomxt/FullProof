
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

import database

with tempfile.TemporaryDirectory() as temp_dir:
    db_path = Path(temp_dir) / "test.db"

    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE cases (case_id TEXT PRIMARY KEY, data TEXT)"
    )
    conn.execute("""
        CREATE TABLE chain_checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            chain_id INTEGER,
            contract_address TEXT,
            block_number INTEGER,
            block_hash TEXT,
            tx_hash TEXT
        )
    """)
    conn.commit()
    conn.close()

    
    def test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection



    test_case = {
        "case_id": "ATOMIC_TEST_001",
        "title": "SQLite 통합 저장 테스트",
        "steps": []
    }

    checkpoint = {
        "chain_id": 31337,
        "contract_address": "0xTEST",
        "block_number": 100,
        "block_hash": "test_block_hash",
        "tx_hash": "test_tx_hash"
    }

    history = {
        **checkpoint,
        "checkpoint_id": "CASE_ATOMIC_TEST_001_STEP_0_PROOF_1"
    }

    latest = {
        **checkpoint,
        "checkpoint_id": "CASE_ATOMIC_TEST_001_LATEST"
    }

    with patch.object(database, "get_connection", test_connection):
        database.save_proof_result_atomic(
            test_case, history, latest
        )

    with closing(test_connection()) as conn:
        case_count = conn.execute(
            "SELECT COUNT(*) FROM cases"
        ).fetchone()[0]

        checkpoint_count = conn.execute(
            "SELECT COUNT(*) FROM chain_checkpoints"
        ).fetchone()[0]

        saved_case = json.loads(
            conn.execute(
                "SELECT data FROM cases"
            ).fetchone()[0]
        )

    assert case_count == 1
    assert checkpoint_count == 2
    assert saved_case["case_id"] == "ATOMIC_TEST_001"

    print("SQLite 통합 저장 테스트 성공!")
    print("사건 저장:", case_count, "건")
    print("체크포인트 저장:", checkpoint_count, "건")


    # 저장 중 오류 발생 시 전체 롤백 테스트
    failed_case = {
        "case_id": "ATOMIC_ROLLBACK_TEST",
        "title": "롤백 테스트",
        "steps": []
    }

    failed_history = {
        **checkpoint,
        "checkpoint_id": "ROLLBACK_HISTORY"
    }

    failed_latest = {
        **checkpoint,
        "checkpoint_id": "ROLLBACK_LATEST",
        "block_number": None
    }

    # block_number에 NULL을 허용하지 않도록 임시 트리거 생성
    with closing(test_connection()) as conn:
        conn.execute("""
            CREATE TRIGGER reject_null_block
            BEFORE INSERT ON chain_checkpoints
            WHEN NEW.block_number IS NULL
            BEGIN
                SELECT RAISE(ABORT, 'block_number cannot be NULL');
            END;
        """)
        conn.commit()

    try:
        with patch.object(database, "get_connection", test_connection):
            database.save_proof_result_atomic(
                failed_case,
                failed_history,
                failed_latest
            )
        raise AssertionError("오류가 발생하지 않았습니다")

    except sqlite3.IntegrityError:
        print("의도한 SQLite 저장 오류 발생")

    with closing(test_connection()) as conn:
        rollback_case_count = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE case_id = ?",
            ("ATOMIC_ROLLBACK_TEST",)
        ).fetchone()[0]

        rollback_checkpoint_count = conn.execute(
            """
            SELECT COUNT(*) FROM chain_checkpoints
            WHERE checkpoint_id IN (?, ?)
            """,
            ("ROLLBACK_HISTORY", "ROLLBACK_LATEST")
        ).fetchone()[0]

    assert rollback_case_count == 0
    assert rollback_checkpoint_count == 0

    print("SQLite 롤백 테스트 성공!")
    print("실패한 사건 저장:", rollback_case_count, "건")
    print("실패한 체크포인트 저장:", rollback_checkpoint_count, "건")
