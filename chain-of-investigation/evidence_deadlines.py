"""Evidence tracking routes for the FullProof demonstration workspace."""
import json
from contextlib import closing
from datetime import datetime, timezone, timedelta
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

import database
from verification import evidence_warning

KST = timezone(timedelta(hours=9))


class EvidenceDeadline(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    evidence_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    agency: str = Field(min_length=1, max_length=120)
    evidence_expires_at: AwareDatetime | None = None
    expected_at: AwareDatetime | None = None
    deadline_source: str = Field(default='', max_length=500)
    preservation_status: Literal['NOT_SECURED', 'REQUESTED', 'SECURED'] = 'NOT_SECURED'
    preservation_ref: str = Field(default='', max_length=500)

    @model_validator(mode='after')
    def check_sources(self):
        if self.evidence_expires_at and not self.deadline_source:
            raise ValueError('보존기한을 입력할 때 확인 출처를 함께 기록해 주세요.')
        if self.preservation_status == 'SECURED' and not self.preservation_ref:
            raise ValueError('확보 완료의 확인 근거를 입력해 주세요.')
        return self


def evaluate(record, now):
    warning = evidence_warning(record, now.isoformat(), threshold_hours=168)
    expires = record.get('evidence_expires_at')
    expected = record.get('expected_at')
    secured = warning['preservation_status'] == 'SECURED'
    def days_from_today(value):
        return (datetime.fromisoformat(value).astimezone(KST).date()
                - now.astimezone(KST).date()).days

    overdue = bool(expected and not secured and datetime.fromisoformat(expected) < now)
    return {**record, **warning, 'evaluated_at': now.isoformat(),
            'days_until_expiry': days_from_today(expires) if expires else None,
            'acquisition_overdue': overdue,
            'acquisition_delay_days': max(0, -days_from_today(expected)) if overdue else None}


def make_router(cases, namespace):
    router = APIRouter(prefix='/api/v1/frontend')

    def connection():
        db = database.get_connection()
        db.execute('''CREATE TABLE IF NOT EXISTS evidence_deadlines (
            namespace TEXT NOT NULL, case_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
            payload TEXT NOT NULL, PRIMARY KEY(namespace, case_id, evidence_id))''')
        return db

    def list_records(case_id=None):
        scope = namespace()
        now = datetime.now(timezone.utc)
        with closing(connection()) as db:
            rows = db.execute(
                'SELECT case_id,payload FROM evidence_deadlines WHERE namespace=?'
                ' AND (? IS NULL OR case_id=?) ORDER BY rowid DESC', (scope, case_id, case_id)
            ).fetchall()
        return [evaluate(json.loads(row['payload']), now) for row in rows
                if row['case_id'] in cases]

    @router.get('/evidence-deadlines')
    def active_warnings():
        return [row for row in list_records() if row['action_required'] or row['acquisition_overdue']]

    @router.get('/cases/{case_id}/evidence-deadlines')
    def case_deadlines(case_id: str):
        if case_id not in cases:
            raise HTTPException(404, '사건을 찾을 수 없습니다.')
        return list_records(case_id)

    @router.post('/cases/{case_id}/evidence-deadlines')
    def save_deadline(case_id: str, data: EvidenceDeadline):
        if case_id not in cases:
            raise HTTPException(404, '사건을 찾을 수 없습니다.')
        scope = namespace()
        evidence_id = data.evidence_id or uuid4().hex
        with closing(connection()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute(
                'SELECT payload FROM evidence_deadlines WHERE namespace=? AND case_id=? AND evidence_id=?',
                (scope, case_id, evidence_id)).fetchone()
            if data.evidence_id and not existing:
                raise HTTPException(404, '증거 확보 기록을 찾을 수 없습니다.')
            now = datetime.now(timezone.utc)
            record = data.model_dump(mode='json')
            previous = json.loads(existing['payload']) if existing else {}
            record.update(case_id=case_id, evidence_id=evidence_id,
                          deadline_version=previous.get('deadline_version', 0) + 1,
                          updated_at=now.isoformat())
            db.execute('''INSERT INTO evidence_deadlines VALUES (?,?,?,?)
                       ON CONFLICT(namespace,case_id,evidence_id) DO UPDATE SET payload=excluded.payload''',
                       (scope, case_id, evidence_id, json.dumps(record, ensure_ascii=False)))
        return evaluate(record, now)

    return router
