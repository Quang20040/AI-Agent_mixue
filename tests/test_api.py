"""REST API: auth, roles, store scope, and that photo reading never saves anything."""
import pytest

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient  # noqa: E402

from src import login_sessions  # noqa: E402
from src.api.main import app  # noqa: E402

client = TestClient(app)


def bearer(username):
    return {'Authorization': f'Bearer {login_sessions.create(username)}'}


def test_health_and_openapi():
    assert client.get('/api/v1/health').json()['status'] == 'ok'
    paths = client.get('/openapi.json').json()['paths']
    assert '/api/v1/stores/{store_id}/sales' in paths and '/api/v1/stores/{store_id}/ocr/read' in paths


def test_requests_without_a_valid_token_are_refused():
    assert client.get('/api/v1/me').status_code == 401
    assert client.get('/api/v1/stores/2132/sales', headers={'Authorization': 'Bearer nope'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'username': 'quanly', 'password': 'sai-mat-khau'}).status_code == 401


def test_staff_can_look_up_sop_but_not_revenue():
    staff = bearer('nhanvien')
    assert client.get('/api/v1/me', headers=staff).json()['is_admin'] is False
    assert client.get('/api/v1/stores/2132/sales', headers=staff).status_code == 403
    assert client.get('/api/v1/stores/2132/approvals', headers=staff).status_code == 403
    hits = client.get('/api/v1/stores/2132/sop/search', params={'q': 'trân châu luộc mấy phút'}, headers=staff).json()
    assert hits and any('35 phút' in h['content'] for h in hits)


def test_manager_routes_and_store_scope():
    manager = bearer('quanly')
    assert client.get('/api/v1/stores', headers=manager).json()[0]['store_id'] == '2132'
    assert client.get('/api/v1/stores/9999/sales', headers=manager).status_code == 404
    assert client.get('/api/v1/stores/2132/sales', params={'start': '2026-10-14'}, headers=manager).status_code == 200
    matrix = client.get('/api/v1/stores/2132/stock-matrix', params={'year': 2026, 'month': 10}, headers=manager)
    assert matrix.status_code == 200 and isinstance(matrix.json()['rows'], list)
    assert isinstance(client.get('/api/v1/stores/2132/approvals', headers=manager).json(), list)
    assert client.get('/api/v1/stores/2132/ai-usage', headers=manager).status_code == 200
    assert client.post('/api/v1/stores/2132/approvals/shift/khong-co', json={'approve': True},
                       headers=manager).status_code == 404


def test_photo_reading_returns_a_suggestion_and_saves_nothing(monkeypatch):
    from src.engine import vision_ocr
    seen = {}

    def fake_extract(**kwargs):
        seen.update(kwargs)
        return {'status': 'NEEDS_REVIEW', 'fields': {'cash_vnd': 1000}}
    monkeypatch.setattr(vision_ocr, 'extract_image', fake_extract)
    res = client.post('/api/v1/stores/2132/ocr/read', headers=bearer('nhanvien'),
                      files=[('files', ('a.jpg', b'\xff\xd8fake', 'image/jpeg'))],
                      data={'business_date': '2026-10-14', 'shift': 'CA_TOI'})
    assert res.status_code == 200 and res.json()['saved'] is False
    assert res.json()['result']['status'] == 'NEEDS_REVIEW' and seen['target_date'] == '2026-10-14'
    too_many = [('files', (f'{i}.jpg', b'x', 'image/jpeg')) for i in range(6)]
    assert client.post('/api/v1/stores/2132/ocr/read', headers=bearer('nhanvien'), files=too_many,
                       data={'business_date': '2026-10-14'}).status_code == 422


def test_chat_approval_needs_a_manager():
    assert client.post('/api/v1/stores/2132/chat/approval', json={'approve': True},
                       headers=bearer('nhanvien')).status_code == 403
