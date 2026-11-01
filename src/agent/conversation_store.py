"""Account-scoped chat index, visible messages, server-issued attachments, OCR drafts, verified summaries, and user preferences."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.engine.shift_service import REQUIRED_SHIFT_MONEY_FIELDS
from src.engine.vision_ocr import MONEY_FIELDS

ALLOWED_PREFERENCE_KEYS = {
    'response_style': 'Phong cách trả lời (ngắn gọn / chi tiết)',
    'pearl_yield_g': 'Giả định thành phẩm trân châu (g/1kg hạt khô)',
    'default_shift': 'Ca làm việc mặc định khi tra cứu',
    'note_format': 'Định dạng trình bày ghi chú',
}

FORBIDDEN_PREFERENCE_PATTERNS = re.compile(
    r'\b(admin|manager|owner|quản lý|chủ quán|chủ cửa hàng|quyền|role|permission|bypass|'
    r'bỏ qua duyệt|tự động duyệt|xem lương|mật khẩu|password|store_id)\b',
    re.IGNORECASE,
)


def _compute_draft_consistency(fields: dict[str, Any], field_readings: dict[str, Any]) -> dict[str, Any]:
    """Check arithmetic consistency of current draft values without auto-modifying any field."""
    discrepancies: list[dict[str, Any]] = []
    comp_keys = ('cash_vnd', 'bank_transfer_vnd', 'shopee_food_vnd', 'grab_food_vnd', 'be_food_vnd')
    present_comps = {k: int(fields[k]) for k in comp_keys if fields.get(k) is not None}
    expenses = int(fields['expenses_vnd']) if fields.get('expenses_vnd') is not None else 0
    total_collected = int(fields['total_collected_vnd']) if fields.get('total_collected_vnd') is not None else None

    if total_collected is not None and len(present_comps) == len(comp_keys):
        comp_sum = sum(present_comps.values()) - expenses
        diff = comp_sum - total_collected
        if diff != 0:
            discrepancies.append({
                'scope': 'shift_draft',
                'component_sum_vnd': comp_sum,
                'expected_total_vnd': total_collected,
                'difference_vnd': diff,
                'message': (
                    f'Tổng các khoản trong dự thảo ({comp_sum:,} đ) lệch {diff:+,} đ '
                    f'so với Tổng thu về ({total_collected:,} đ). Hệ thống không tự sửa số để khớp.'
                ),
            })

    pos_collected = int(fields['pos_collected_vnd']) if fields.get('pos_collected_vnd') is not None else None
    if pos_collected is not None and total_collected is not None:
        pos_diff = total_collected - pos_collected
        if abs(pos_diff) > 1000:
            discrepancies.append({
                'scope': 'pos_vs_shift_draft',
                'component_sum_vnd': total_collected,
                'expected_total_vnd': pos_collected,
                'difference_vnd': pos_diff,
                'message': (
                    f'Tổng thu về của ca ({total_collected:,} đ) lệch {pos_diff:+,} đ '
                    f'so với Thực thu POS ({pos_collected:,} đ).'
                ),
            })

    return {
        'is_consistent': len(discrepancies) == 0,
        'discrepancies': discrepancies,
    }


def _missing_draft_fields(fields: dict[str, Any], business_date: str | None, shift_code: str | None) -> list[str]:
    missing: list[str] = []
    if not business_date:
        missing.append('business_date')
    if not shift_code:
        missing.append('shift_code')
    for k in REQUIRED_SHIFT_MONEY_FIELDS:
        if fields.get(k) is None:
            missing.append(k)
    return missing


class ConversationStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.uploads_dir = self.path.parent / 'chat_uploads'
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS conversations_owner ON conversations(owner, updated_at);
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL, evidence TEXT NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS messages_conversation ON chat_messages(conversation_id, id);
                CREATE TABLE IF NOT EXISTS chat_feedback (
                    message_id INTEGER PRIMARY KEY, rating INTEGER NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chat_attachments (
                    file_id TEXT PRIMARY KEY, owner TEXT NOT NULL, user_id TEXT NOT NULL,
                    store_id TEXT NOT NULL, conversation_id TEXT NOT NULL, filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL, sha256 TEXT NOT NULL, storage_path TEXT NOT NULL,
                    document_type TEXT NOT NULL DEFAULT 'unknown',
                    ocr_result_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS attachments_conv ON chat_attachments(owner, conversation_id, created_at);
                CREATE TABLE IF NOT EXISTS ocr_shift_drafts (
                    draft_id TEXT PRIMARY KEY, owner TEXT NOT NULL, user_id TEXT NOT NULL,
                    store_id TEXT NOT NULL, conversation_id TEXT NOT NULL, file_id TEXT NOT NULL,
                    image_sha256 TEXT NOT NULL, document_type TEXT NOT NULL DEFAULT 'unknown',
                    business_date TEXT, shift_code TEXT, status TEXT NOT NULL DEFAULT 'DRAFT',
                    fields_json TEXT NOT NULL, field_readings_json TEXT NOT NULL,
                    edits_json TEXT NOT NULL DEFAULT '[]', warnings_json TEXT NOT NULL DEFAULT '[]',
                    consistency_json TEXT NOT NULL DEFAULT '{}', signed_by TEXT NOT NULL DEFAULT '',
                    bank_transfer_formula TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ocr_drafts_conv ON ocr_shift_drafts(owner, conversation_id, updated_at);
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    conversation_id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    summary_text TEXT NOT NULL, evidence_refs_json TEXT NOT NULL,
                    summarized_up_to_id INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS user_preferences (
                    owner TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                    updated_at TEXT NOT NULL, PRIMARY KEY (owner, key));
            ''')
            # Migration for stores created before draft metadata existed.
            columns = {row[1] for row in db.execute('PRAGMA table_info(ocr_shift_drafts)')}
            if 'meta_json' not in columns:
                db.execute("ALTER TABLE ocr_shift_drafts ADD COLUMN meta_json TEXT NOT NULL DEFAULT '{}'")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA busy_timeout=5000')
            with db:
                yield db
        finally:
            db.close()

    def create(self, owner: str) -> str:
        ident = uuid.uuid4().hex
        stamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                'INSERT INTO conversations VALUES (?, ?, ?, ?, ?)',
                (ident, owner, 'Cuộc trò chuyện mới', stamp, stamp),
            )
        return ident

    def list(self, owner: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in db.execute(
                    'SELECT id,title,created_at,updated_at FROM conversations WHERE owner=? ORDER BY updated_at DESC LIMIT 100',
                    (owner,),
                )
            ]

    def owns(self, owner: str, ident: str) -> bool:
        with self.connect() as db:
            return db.execute('SELECT 1 FROM conversations WHERE id=? AND owner=?', (ident, owner)).fetchone() is not None

    def require_owned(self, owner: str, ident: str) -> None:
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM conversations WHERE id=? AND owner=?', (ident, owner)).fetchone():
                raise PermissionError('Conversation not available for this account')

    def messages(self, owner: str, ident: str) -> list[dict[str, Any]]:
        self.require_owned(owner, ident)
        with self.connect() as db:
            return [
                {
                    'message_id': mid,
                    'role': role,
                    'content': content,
                    'evidence': json.loads(refs),
                    'rating': rating,
                }
                for mid, role, content, refs, rating in db.execute(
                    '''SELECT m.id,m.role,m.content,m.evidence,f.rating FROM chat_messages m
                       LEFT JOIN chat_feedback f ON f.message_id=m.id WHERE m.conversation_id=? ORDER BY m.id''',
                    (ident,),
                )
            ]

    def feedback(self, owner: str, ident: str, message_id: int, rating: int) -> None:
        self.require_owned(owner, ident)
        if rating not in (0, 1):
            raise ValueError('Rating must be 0 or 1')
        with self.connect() as db:
            if not db.execute(
                "SELECT 1 FROM chat_messages WHERE id=? AND conversation_id=? AND role='assistant'",
                (message_id, ident),
            ).fetchone():
                raise PermissionError('Message not available in this conversation')
            db.execute(
                'INSERT OR REPLACE INTO chat_feedback VALUES (?,?,?)',
                (message_id, rating, datetime.now(timezone.utc).isoformat()),
            )

    def touch(self, owner: str, ident: str) -> None:
        self.require_owned(owner, ident)
        with self.connect() as db:
            db.execute(
                'UPDATE conversations SET updated_at=? WHERE id=? AND owner=?',
                (datetime.now(timezone.utc).isoformat(), ident, owner),
            )

    def append(self, owner: str, ident: str, role: str, content: str, evidence: list[str] | None = None) -> int:
        self.require_owned(owner, ident)
        if role not in {'user', 'assistant'}:
            raise ValueError('Unsupported message role')
        stamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            cursor = db.execute(
                'INSERT INTO chat_messages (conversation_id,role,content,evidence,created_at) VALUES (?,?,?,?,?)',
                (ident, role, content, json.dumps(evidence or [], ensure_ascii=False), stamp),
            )
            msg_id = int(cursor.lastrowid)
            if role == 'user':
                title = ' '.join(content.split())[:70]
                db.execute(
                    "UPDATE conversations SET title=? WHERE id=? AND title='Cuộc trò chuyện mới'",
                    (title, ident),
                )
            db.execute('UPDATE conversations SET updated_at=? WHERE id=?', (stamp, ident))
        # Trigger rolling verified summary when conversation grows long (> 12 messages)
        self.build_verified_summary(owner, ident)
        return msg_id

    # --- ATTACHMENT & OCR SHIFT DRAFT METHODS (PROMPT 2) ---

    def register_attachment(
        self,
        owner: str,
        ident: str,
        *,
        user_id: str,
        store_id: str,
        image_bytes: bytes | None = None,
        storage_path: str | None = None,
        filename: str = 'shift_photo.png',
        mime_type: str = 'image/png',
        sha256: str | None = None,
        size_bytes: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Issue a server-generated file_id and store attachment bound to account, store, and conversation."""
        self.require_owned(owner, ident)
        file_id = f"FILE_{uuid.uuid4().hex[:16].upper()}"
        suffix = Path(filename).suffix.lower()
        if suffix not in {'.jpg', '.jpeg', '.png', '.webp'}:
            suffix = '.png'

        if image_bytes is not None:
            if not image_bytes or len(image_bytes) > 10 * 1024 * 1024:
                raise ValueError('Invalid or oversized attachment')
            calc_sha = hashlib.sha256(image_bytes).hexdigest()
            target_path = self.uploads_dir / f"{file_id}{suffix}"
            target_path.write_bytes(image_bytes)
            storage_path = str(target_path)
            sha256 = calc_sha
        elif storage_path is not None:
            path_obj = Path(storage_path)
            if not sha256 and path_obj.is_file():
                sha256 = hashlib.sha256(path_obj.read_bytes()).hexdigest()
        else:
            raise ValueError('Either image_bytes or storage_path must be provided')

        stamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                '''INSERT INTO chat_attachments
                   (file_id, owner, user_id, store_id, conversation_id, filename, mime_type, sha256, storage_path, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (file_id, owner, user_id, store_id, ident, filename, mime_type, sha256 or '', str(storage_path), stamp),
            )
        return {
            'file_id': file_id,
            'owner': owner,
            'user_id': user_id,
            'store_id': store_id,
            'conversation_id': ident,
            'filename': filename,
            'mime_type': mime_type,
            'sha256': sha256 or '',
            'storage_path': str(storage_path),
            'created_at': stamp,
        }

    def get_attachment(
        self,
        owner: str,
        ident: str,
        file_id: str,
        *,
        store_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch attachment metadata and bytes strictly scoped to (owner, conversation_id, file_id)."""
        self.require_owned(owner, ident)
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            query = '''SELECT file_id, owner, user_id, store_id, conversation_id, filename, mime_type,
                              sha256, storage_path, document_type, ocr_result_json, created_at
                       FROM chat_attachments WHERE file_id=? AND owner=? AND conversation_id=?'''
            params: list[Any] = [file_id, owner, ident]
            if store_id:
                query += ' AND store_id=?'
                params.append(store_id)
            if user_id:
                query += ' AND user_id=?'
                params.append(user_id)
            row = db.execute(query, tuple(params)).fetchone()
        if not row:
            raise PermissionError('Mã tệp ảnh không thuộc tài khoản hoặc cuộc trò chuyện hiện tại.')
        item = dict(row)
        p = Path(item['storage_path'])
        item['image_bytes'] = p.read_bytes() if p.is_file() else b''
        item['ocr_result'] = json.loads(item.pop('ocr_result_json') or '{}')
        return item

    def latest_attachment_id(self, owner: str, ident: str) -> str | None:
        self.require_owned(owner, ident)
        with self.connect() as db:
            row = db.execute(
                'SELECT file_id FROM chat_attachments WHERE owner=? AND conversation_id=? ORDER BY created_at DESC LIMIT 1',
                (owner, ident),
            ).fetchone()
        return row[0] if row else None

    def update_attachment_ocr(self, owner: str, ident: str, file_id: str, ocr_result: dict[str, Any]) -> None:
        self.require_owned(owner, ident)
        doc_type = str(ocr_result.get('document_type', 'unknown'))
        with self.connect() as db:
            db.execute(
                'UPDATE chat_attachments SET document_type=?, ocr_result_json=? WHERE file_id=? AND owner=? AND conversation_id=?',
                (doc_type, json.dumps(ocr_result, ensure_ascii=False), file_id, owner, ident),
            )

    def save_ocr_draft(
        self,
        owner: str,
        ident: str,
        user_id: str | None = None,
        store_id: str | None = None,
        file_id: str | None = None,
        extracted: dict[str, Any] | None = None,
        *,
        draft_data: dict[str, Any] | None = None,
        business_date: str | None = None,
        shift_code: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a new OCR draft from `extracted` or `draft_data`, superseding any older draft so results never mix across images."""
        self.require_owned(owner, ident)
        u_id = user_id or kwargs.get('user_id') or 'SYSTEM'
        s_id = store_id or kwargs.get('store_id') or 'MIXUE_TON_QUANG_PHIET'
        f_id = file_id or kwargs.get('file_id') or ''
        data = draft_data or extracted or kwargs.get('draft_data') or kwargs.get('extracted') or {}

        f_ids = data.get('file_ids') or ([f_id] if f_id else [])
        primary_fid = f_ids[0] if f_ids else f_id
        stored_file_id = ','.join(f_ids) if f_ids else f_id

        att = None
        if primary_fid:
            try:
                att = self.get_attachment(owner, ident, primary_fid)
            except Exception:
                att = None

        for fid in f_ids:
            if fid:
                try:
                    self.update_attachment_ocr(owner, ident, fid, data)
                except Exception:
                    pass

        stamp = datetime.now(timezone.utc).isoformat()
        draft_id = f"DRAFT_OCR_{uuid.uuid4().hex[:12].upper()}"
        nested = data.get('fields') if isinstance(data.get('fields'), dict) else {}
        b_date = business_date or data.get('business_date') or data.get('report_date') or data.get('document_date') or nested.get('report_date')
        s_code = shift_code or data.get('shift_code') or nested.get('shift_code')

        # Strictly copy only confirmed 'read' fields from THIS image; uncertain/missing stay None
        fields_in = data.get('fields') if isinstance(data.get('fields'), dict) else data
        fields = {k: fields_in.get(k) for k in MONEY_FIELDS}
        readings = data.get('field_readings', {})
        warnings = list(data.get('warnings', []))
        consistency = data.get('consistency') or _compute_draft_consistency(fields, readings)
        if not isinstance(consistency, dict):
            consistency = _compute_draft_consistency(fields, readings)

        with self.connect() as db:
            # Supersede any prior draft in this conversation so a new image never mixes with an old image!
            db.execute(
                '''UPDATE ocr_shift_drafts SET status='SUPERSEDED', updated_at=?
                   WHERE owner=? AND conversation_id=? AND status IN ('DRAFT', 'PENDING_CONFIRMATION')''',
                (stamp, owner, ident),
            )
            sha = data.get('image_sha256') or (att['sha256'] if att else '')
            db.execute(
                '''INSERT INTO ocr_shift_drafts
                   (draft_id, owner, user_id, store_id, conversation_id, file_id, image_sha256,
                    document_type, business_date, shift_code, status, fields_json, field_readings_json,
                    edits_json, warnings_json, consistency_json, signed_by, bank_transfer_formula, notes,
                    created_at, updated_at, meta_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, '[]', ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    draft_id,
                    owner,
                    u_id,
                    s_id,
                    ident,
                    stored_file_id,
                    sha,
                    data.get('document_type', 'unknown'),
                    b_date,
                    s_code,
                    json.dumps(fields, ensure_ascii=False),
                    json.dumps(readings, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False),
                    json.dumps(consistency, ensure_ascii=False),
                    str(data.get('signed_by') or ''),
                    str(data.get('bank_transfer_formula') or ''),
                    str(data.get('notes') or ''),
                    stamp,
                    stamp,
                    json.dumps(data.get('meta') or {}, ensure_ascii=False),
                ),
            )
        return self.get_active_ocr_draft(owner, ident, store_id=s_id, user_id=u_id)  # type: ignore[return-value]

    def _deserialize_draft(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        fields = json.loads(item.pop('fields_json') or '{}')
        fields.update(report_date=item.get('business_date'), shift_code=item.get('shift_code'),
                      signed_by=item.get('signed_by', ''), notes=item.get('notes', ''),
                      bank_transfer_formula=item.get('bank_transfer_formula', ''))
        readings = json.loads(item.pop('field_readings_json') or '{}')
        edits = json.loads(item.pop('edits_json') or '[]')
        warnings = json.loads(item.pop('warnings_json') or '[]')
        consistency = json.loads(item.pop('consistency_json') or '{}')
        meta = json.loads(item.pop('meta_json', None) or '{}')
        missing = _missing_draft_fields(fields, item.get('business_date'), item.get('shift_code'))
        raw_file_id = item.get('file_id', '')
        file_ids = [f.strip() for f in raw_file_id.split(',') if f.strip()]
        primary_file_id = file_ids[0] if file_ids else raw_file_id
        return {
            **item,
            'file_id': primary_file_id,
            'file_ids': file_ids,
            'fields': fields,
            'field_readings': readings,
            'edits': edits,
            'warnings': warnings,
            'consistency': consistency,
            'meta': meta,
            'missing_fields': missing,
            'is_complete': len(missing) == 0,
        }

    def get_active_ocr_draft(
        self,
        owner: str,
        ident: str,
        *,
        store_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        self.require_owned(owner, ident)
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            query = '''SELECT * FROM ocr_shift_drafts
                       WHERE owner=? AND conversation_id=? AND status IN ('DRAFT', 'PENDING_CONFIRMATION')'''
            params: list[Any] = [owner, ident]
            if store_id:
                query += ' AND store_id=?'
                params.append(store_id)
            if user_id:
                query += ' AND user_id=?'
                params.append(user_id)
            query += ' ORDER BY updated_at DESC LIMIT 1'
            row = db.execute(query, tuple(params)).fetchone()
        return self._deserialize_draft(row) if row else None

    def update_ocr_draft(
        self,
        owner: str,
        ident: str,
        updates: dict[str, Any] | None = None,
        *,
        updated_by: str = 'user',
        edit_source: str = 'chat',
        draft_id: str | None = None,
        store_id: str | None = None,
        user_id: str | None = None,
        consistency: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Update specific fields on the active OCR draft and record every user edit."""
        self.require_owned(owner, ident)
        current = self.get_active_ocr_draft(owner, ident, store_id=store_id, user_id=user_id)
        if not current:
            raise ValueError('Không có dự thảo OCR đang chờ trong cuộc trò chuyện này.')

        if draft_id and current['draft_id'] != draft_id:
            raise ValueError(f"Dự thảo `{draft_id}` không khớp dự thảo hiện hành `{current['draft_id']}`.")

        updates = dict(updates or {})
        fields = dict(current['fields'])
        edits = list(current['edits'])
        b_date = current['business_date']
        s_code = current['shift_code']
        signed_by = current['signed_by']
        formula = current['bank_transfer_formula']
        notes = current['notes']
        stamp = datetime.now(timezone.utc).isoformat()

        if 'report_date' in updates and 'business_date' not in updates:
            updates['business_date'] = updates['report_date']

        if 'business_date' in updates and updates['business_date']:
            val_str = str(updates['business_date']).strip()
            date.fromisoformat(val_str)
            if val_str != b_date:
                edits.append({'field': 'business_date', 'old_value': b_date, 'new_value': val_str,
                              'source': edit_source, 'by': updated_by, 'at': stamp})
                b_date = val_str

        if 'shift_code' in updates and updates['shift_code']:
            sc = str(updates['shift_code']).strip().upper()
            if sc not in {'CA_SANG', 'CA_CHIEU', 'CA_TOI'}:
                raise ValueError(f"Mã ca '{sc}' không hợp lệ.")
            if sc != s_code:
                edits.append({'field': 'shift_code', 'old_value': s_code, 'new_value': sc,
                              'source': edit_source, 'by': updated_by, 'at': stamp})
                s_code = sc

        if 'signed_by' in updates and updates['signed_by'] is not None:
            new_sig = str(updates['signed_by']).strip()
            if new_sig != signed_by:
                edits.append({'field': 'signed_by', 'old_value': signed_by, 'new_value': new_sig,
                              'source': edit_source, 'by': updated_by, 'at': stamp})
                signed_by = new_sig

        if 'bank_transfer_formula' in updates and updates['bank_transfer_formula'] is not None:
            formula = str(updates['bank_transfer_formula']).strip()

        if 'notes' in updates and updates['notes'] is not None:
            notes = str(updates['notes']).strip()

        for money_key in MONEY_FIELDS:
            if money_key in updates and updates[money_key] is not None:
                new_val = int(updates[money_key])
                if money_key != 'cash_diff_vnd' and new_val < 0:
                    raise ValueError(f'Số tiền {money_key} không được âm.')
                old_val = fields.get(money_key)
                if old_val != new_val:
                    edits.append({
                        'field': money_key,
                        'old_value': old_val,
                        'new_value': new_val,
                        'source': edit_source,
                        'by': updated_by,
                        'at': stamp,
                    })
                    fields[money_key] = new_val

        comp_consistency = consistency or _compute_draft_consistency(fields, current['field_readings'])
        warnings = [w for w in current['warnings'] if not w.startswith('Tổng các khoản trong dự thảo')]
        for disc in comp_consistency.get('discrepancies', []):
            if disc['message'] not in warnings:
                warnings.append(disc['message'])

        with self.connect() as db:
            db.execute(
                '''UPDATE ocr_shift_drafts
                   SET business_date=?, shift_code=?, fields_json=?, edits_json=?,
                       warnings_json=?, consistency_json=?, signed_by=?, bank_transfer_formula=?,
                       notes=?, updated_at=?
                   WHERE draft_id=? AND owner=? AND conversation_id=?''',
                (
                    b_date,
                    s_code,
                    json.dumps(fields, ensure_ascii=False),
                    json.dumps(edits, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False),
                    json.dumps(comp_consistency, ensure_ascii=False),
                    signed_by,
                    formula,
                    notes,
                    stamp,
                    current['draft_id'],
                    owner,
                    ident,
                ),
            )
        return self.get_active_ocr_draft(owner, ident, store_id=store_id, user_id=user_id)  # type: ignore[return-value]

    def update_ocr_draft_fields(
        self,
        owner: str,
        ident: str,
        *,
        field_updates: dict[str, Any],
        draft_id: str | None = None,
        store_id: str | None = None,
        user_id: str | None = None,
        consistency: dict[str, Any] | None = None,
        uncertain_fields: list[str] | None = None,
        updated_by: str = 'user',
        edit_source: str = 'chat',
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.update_ocr_draft(
            owner,
            ident,
            updates=field_updates,
            updated_by=updated_by or user_id or 'user',
            edit_source=edit_source,
            draft_id=draft_id,
            store_id=store_id,
            user_id=user_id,
            consistency=consistency,
        )

    def set_ocr_draft_status(self, owner: str, ident: str, status: str) -> dict[str, Any] | None:
        self.require_owned(owner, ident)
        current = self.get_active_ocr_draft(owner, ident)
        if not current:
            return None
        stamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                'UPDATE ocr_shift_drafts SET status=?, updated_at=? WHERE draft_id=? AND owner=? AND conversation_id=?',
                (status, stamp, current['draft_id'], owner, ident),
            )
            db.row_factory = sqlite3.Row
            row = db.execute(
                'SELECT * FROM ocr_shift_drafts WHERE draft_id=? AND owner=? AND conversation_id=?',
                (current['draft_id'], owner, ident),
            ).fetchone()
        return self._deserialize_draft(row) if row else None

    def resolve_ocr_draft(
        self,
        owner: str,
        ident: str,
        *,
        new_status: str,
        draft_id: str | None = None,
        store_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        self.require_owned(owner, ident)
        active = self.get_active_ocr_draft(owner, ident, store_id=store_id, user_id=user_id)
        if not active:
            return None
        target_id = draft_id or active['draft_id']
        stamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                'UPDATE ocr_shift_drafts SET status=?, updated_at=? WHERE draft_id=? AND owner=? AND conversation_id=?',
                (new_status, stamp, target_id, owner, ident),
            )
            db.row_factory = sqlite3.Row
            row = db.execute(
                'SELECT * FROM ocr_shift_drafts WHERE draft_id=? AND owner=? AND conversation_id=?',
                (target_id, owner, ident),
            ).fetchone()
        return self._deserialize_draft(row) if row else None

    # --- VERIFIED CONVERSATION SUMMARIZATION (PROMPT 4) ---

    def build_verified_summary(self, owner: str, ident: str, keep_recent: int = 8) -> dict[str, Any] | None:
        """Build a grounded summary of older turns with source references; never promote unverified replies to truth."""
        self.require_owned(owner, ident)
        all_msgs = self.messages(owner, ident)
        if len(all_msgs) <= keep_recent:
            return self.get_summary(owner, ident)

        older = all_msgs[:-keep_recent]
        facts: list[str] = []
        evidence_refs: list[str] = []
        last_id = 0

        for idx, msg in enumerate(older):
            last_id = max(last_id, int(msg.get('message_id') or 0))
            role = msg.get('role')
            content = (msg.get('content') or '').strip()
            refs = msg.get('evidence') or []
            if role == 'user':
                short_q = ' '.join(content.split())[:120]
                facts.append(f"- Người dùng hỏi: \"{short_q}\"")
            elif role == 'assistant':
                first_line = ' '.join(content.splitlines()[0].split())[:140] if content else ''
                if refs:
                    for r in refs:
                        if r not in evidence_refs:
                            evidence_refs.append(r)
                    facts.append(f"  → Đã trả lời (có nguồn {', '.join(refs[:2])}): {first_line}")
                else:
                    # Explicitly mark unreferenced assistant replies so unverified/error replies never become confirmed truth
                    facts.append(f"  → Phản hồi hội thoại (chưa có nguồn dữ liệu xác nhận): {first_line}")

        summary_text = "Tóm tắt ngữ cảnh trước đó (chỉ các mục có nguồn mới là dữ liệu đã kiểm chứng):\n" + "\n".join(facts[-16:])
        stamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                '''INSERT OR REPLACE INTO conversation_summaries
                   (conversation_id, owner, summary_text, evidence_refs_json, summarized_up_to_id, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (ident, owner, summary_text, json.dumps(evidence_refs, ensure_ascii=False), last_id, stamp),
            )
        return {
            'conversation_id': ident,
            'summary_text': summary_text,
            'evidence_refs': evidence_refs,
            'summarized_up_to_id': last_id,
            'updated_at': stamp,
        }

    def get_summary(self, owner: str, ident: str) -> dict[str, Any] | None:
        self.require_owned(owner, ident)
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                'SELECT conversation_id, summary_text, evidence_refs_json, summarized_up_to_id, updated_at FROM conversation_summaries WHERE conversation_id=? AND owner=?',
                (ident, owner),
            ).fetchone()
        if not row:
            return None
        return {
            'conversation_id': row['conversation_id'],
            'summary_text': row['summary_text'],
            'evidence_refs': json.loads(row['evidence_refs_json'] or '[]'),
            'summarized_up_to_id': row['summarized_up_to_id'],
            'updated_at': row['updated_at'],
        }

    # --- CROSS-CONVERSATION USER PREFERENCES (PROMPT 4) ---

    def get_preferences(
        self, owner: str, *, store_id: str | None = None, user_id: str | None = None, **kwargs
    ) -> dict[str, str]:
        with self.connect() as db:
            return {
                k: v
                for k, v in db.execute(
                    'SELECT key, value FROM user_preferences WHERE owner=? ORDER BY key',
                    (owner,),
                )
            }

    def set_preference(
        self,
        owner: str,
        key: str | None = None,
        value: str | None = None,
        *,
        store_id: str | None = None,
        user_id: str | None = None,
        pref_key: str | None = None,
        pref_value: str | None = None,
        **kwargs
    ) -> dict[str, str]:
        """Save an allowed user preference; strictly reject any role/permission/privilege claim."""
        actual_key = (key or pref_key or "").strip().lower()
        actual_val = (value or pref_value or "").strip()
        if actual_key not in ALLOWED_PREFERENCE_KEYS:
            raise ValueError(f"Chỉ hỗ trợ lưu các tùy chọn hiển thị/vận hành: {', '.join(ALLOWED_PREFERENCE_KEYS)}.")
        if not actual_val or len(actual_val) > 200:
            raise ValueError('Giá trị tùy chọn không hợp lệ.')
        if FORBIDDEN_PREFERENCE_PATTERNS.search(actual_val) or FORBIDDEN_PREFERENCE_PATTERNS.search(actual_key):
            raise PermissionError('Không được lưu quyền hạn, chức vụ hay quy tắc phê duyệt vào tùy chọn cá nhân.')
        stamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                'INSERT OR REPLACE INTO user_preferences (owner, key, value, updated_at) VALUES (?, ?, ?, ?)',
                (owner, actual_key, actual_val, stamp),
            )
        return self.get_preferences(owner, store_id=store_id, user_id=user_id)

    def delete_preference(
        self,
        owner: str,
        key: str | None = None,
        *,
        store_id: str | None = None,
        user_id: str | None = None,
        pref_key: str | None = None,
        **kwargs
    ) -> dict[str, str]:
        """Delete a specific preference or clear all preferences for this account."""
        target_key = key or pref_key
        with self.connect() as db:
            if target_key:
                db.execute('DELETE FROM user_preferences WHERE owner=? AND key=?', (owner, target_key.strip().lower()))
            else:
                db.execute('DELETE FROM user_preferences WHERE owner=?', (owner,))
        return self.get_preferences(owner, store_id=store_id, user_id=user_id)
