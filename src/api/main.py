"""BeverageOps REST API (FastAPI) — the backend for any frontend (web, mobile, POS integration).

Run:   uvicorn src.api.main:app --port 8000   (standalone)  ·  or inside the app server: uvicorn serve:app
       docs: /api/docs (Swagger), /api/openapi.json

It calls the same engine as the Streamlit app (same database, rules and AI), so both can run side by side.
Every business route is scoped to a store: /api/v1/stores/{store_id}/... Today the deployment serves one store
(STORE_ID, default 2132); the store check is one dependency, so serving a chain means mapping users to their
stores there — no route changes.

Rules kept from the app:
* identity and role come only from the bearer token (login session), never from the request body;
* photo reading only returns a suggestion: nothing is written until a manager approves the submission;
* approvals (shift revenue, stock slips, purchase plans) need a manager/owner account.
"""
from __future__ import annotations

import json
import os
import threading
from collections import OrderedDict
from datetime import date
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Path, Query, UploadFile
from pydantic import BaseModel, Field

from src.auth import is_admin_role, verify_user
from src import login_sessions

API_VERSION = '1.0.0'
STORE_ID = os.environ.get('STORE_ID', '2132')
STORES = {STORE_ID: {'store_id': STORE_ID, 'code': f'MX-{STORE_ID}', 'name': 'Mixue 39 Tôn Quang Phiệt'}}
MAX_PHOTOS, MAX_PHOTO_BYTES = 5, 25 * 1024 * 1024

# `api` is mounted at /api: inside the Streamlit server (serve.py) or by `app` below for a standalone run.
api = FastAPI(title='BeverageOps AI API', version=API_VERSION, docs_url='/docs', openapi_url='/openapi.json',
              description='REST API cho vận hành cửa hàng Mixue: doanh thu, kho, dự báo, tra cứu SOP, '
                          'đọc ảnh chốt ca (gợi ý), phê duyệt và trợ lý AI.')


def _plain(value: Any) -> Any:
    """Tool results hold dates, Decimals, numpy numbers and DataFrames: make them JSON."""
    try:
        import pandas as pd
        if isinstance(value, pd.DataFrame):
            value = value.where(pd.notna(value), None).to_dict(orient='records')
    except ImportError:  # pragma: no cover
        pass
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


# --- identity ---------------------------------------------------------------------------------------------

class User(BaseModel):
    username: str
    name: str
    role: str
    is_admin: bool


def current_user(authorization: str | None = Header(default=None)) -> User:
    token = (authorization or '').removeprefix('Bearer ').strip()
    user = login_sessions.restore(token) if token else None
    if not user:
        raise HTTPException(401, 'Chưa đăng nhập hoặc phiên đã hết hạn.', headers={'WWW-Authenticate': 'Bearer'})
    if user.get('must_change_password'):
        raise HTTPException(403, 'Tài khoản cần đổi mật khẩu trên ứng dụng trước khi dùng API.')
    return User(username=user['username'], name=user['name'], role=user['role'], is_admin=is_admin_role(user['role']))


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, 'Chỉ Quản lý / Chủ quán được dùng chức năng này.')
    return user


def store_access(store_id: str = Path(..., description='Mã cửa hàng, ví dụ 2132'),
                 user: User = Depends(current_user)) -> str:
    """The one place that decides which stores a user may see (single store today)."""
    if store_id not in STORES:
        raise HTTPException(404, f'Không có cửa hàng {store_id}.')
    return store_id


# --- one operations agent per user (it holds that user's conversation) ---------------------------------------

_AGENTS: OrderedDict[str, Any] = OrderedDict()
_AGENTS_LOCK = threading.Lock()


def agent_for(user: User):
    from src.agent.config import AgentSettings
    from src.agent.mixue_agent import MixueOperationsAgent
    with _AGENTS_LOCK:
        agent = _AGENTS.pop(user.username, None) or MixueOperationsAgent(settings=AgentSettings.from_env())
        _AGENTS[user.username] = agent
        while len(_AGENTS) > 32:
            _AGENTS.popitem(last=False)[1].close()
    return agent


# --- auth ----------------------------------------------------------------------------------------------------

class LoginIn(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=128)


@api.get('/v1/health', tags=['system'])
def health():
    return {'status': 'ok', 'version': API_VERSION}


@api.post('/v1/auth/login', tags=['auth'])
def login(body: LoginIn):
    user = verify_user(body.username, body.password)
    if not user:
        raise HTTPException(401, 'Sai tên đăng nhập hoặc mật khẩu (hoặc đang tạm khóa do nhập sai nhiều lần).')
    token = login_sessions.create(user['username'])
    return {'token': token, 'token_type': 'bearer', 'must_change_password': bool(user.get('must_change_password')),
            'user': {'username': user['username'], 'name': user['name'], 'role': user['role'],
                     'is_admin': is_admin_role(user['role'])}}


@api.post('/v1/auth/logout', tags=['auth'])
def logout(authorization: str | None = Header(default=None)):
    login_sessions.revoke((authorization or '').removeprefix('Bearer ').strip())
    return {'ok': True}


@api.get('/v1/me', tags=['auth'])
def me(user: User = Depends(current_user)):
    return {**user.model_dump(), 'stores': list(STORES.values())}


@api.get('/v1/stores', tags=['stores'])
def stores(user: User = Depends(current_user)):
    return list(STORES.values())


# --- data (manager) ------------------------------------------------------------------------------------------

@api.get('/v1/stores/{store_id}/sales', tags=['sales'])
def sales(start: date | None = None, end: date | None = None, store_id: str = Depends(store_access),
          user: User = Depends(admin_user)):
    return _plain(agent_for(user).tool_get_daily_sales(start and start.isoformat(), (end or start) and (end or start).isoformat()))


@api.get('/v1/stores/{store_id}/sales/daily', tags=['sales'])
def sales_daily(days: int = Query(7, ge=1, le=92), end: date | None = None, store_id: str = Depends(store_access),
                user: User = Depends(admin_user)):
    """One recorded revenue figure per day (approved shift closing, else POS) — the same numbers as the app."""
    from datetime import timedelta
    from src.dashboard.sales_view import business_today
    from src.engine.revenue import daily_revenue
    last = end or business_today()
    frame = daily_revenue(last - timedelta(days=days - 1), last)
    return {'days': _plain(frame)}


@api.get('/v1/stores/{store_id}/shift-revenue', tags=['sales'])
def shift_revenue(q: str = Query('hôm nay', description='Ví dụ: "ca tối 14/10"'), store_id: str = Depends(store_access),
                  user: User = Depends(admin_user)):
    return _plain(agent_for(user).tool_get_shift_revenue(q))


@api.get('/v1/stores/{store_id}/inventory', tags=['inventory'])
def inventory(store_id: str = Depends(store_access), user: User = Depends(admin_user)):
    return _plain(agent_for(user).tool_get_inventory_position())


@api.get('/v1/stores/{store_id}/stock-matrix', tags=['inventory'])
def stock_matrix(year: int = Query(..., ge=2020, le=2100), month: int = Query(..., ge=1, le=12),
                 store_id: str = Depends(store_access), user: User = Depends(admin_user)):
    from src.engine.daily_stock_service import get_stock_matrix_df
    return {'year': year, 'month': month, 'rows': _plain(get_stock_matrix_df(year, month))}


@api.get('/v1/stores/{store_id}/forecast', tags=['forecast'])
def forecast(target_date: date | None = None, horizon_days: int = Query(1, ge=1, le=14),
             store_id: str = Depends(store_access), user: User = Depends(admin_user)):
    return _plain(agent_for(user).tool_forecast_demand(target_date and target_date.isoformat(), horizon_days))


@api.get('/v1/stores/{store_id}/ai-usage', tags=['system'])
def ai_usage(days: int = Query(7, ge=1, le=90), store_id: str = Depends(store_access), user: User = Depends(admin_user)):
    from src.engine import llm_usage
    return llm_usage.summary(days)


@api.get('/v1/stores/{store_id}/backup', tags=['system'])
def backup(store_id: str = Depends(store_access), user: User = Depends(admin_user)):
    """Zip of all shop data (database, shift reports, photos, chats, audit, AI usage) with SHA-256 manifest."""
    from starlette.background import BackgroundTask
    from starlette.responses import FileResponse
    from src.engine.data_export import build_export
    path = build_export()
    return FileResponse(path, media_type='application/zip', filename=f'beverageops_backup_{date.today():%Y%m%d}.zip',
                        background=BackgroundTask(path.unlink, missing_ok=True))


class PurgeIn(BaseModel):
    confirm: bool = Field(False, description='true để xóa thật; false chỉ xem số dòng sẽ xóa')


@api.post('/v1/stores/{store_id}/sample-data/purge', tags=['system'])
def purge_sample(body: PurgeIn, store_id: str = Depends(store_access), user: User = Depends(admin_user)):
    """Remove the simulated history (sales 16/07–15/10 except 14/10, purchases, stock counts, topping log,
    development plans). Backup zip first, one transaction, audit line. confirm=false only previews."""
    from src.engine import sample_purge
    if not body.confirm:
        return {'preview': sample_purge.preview(), 'real_from': sample_purge.REAL_FROM.isoformat()}
    return sample_purge.apply(user.username)


# --- knowledge (all staff) -----------------------------------------------------------------------------------

@api.get('/v1/stores/{store_id}/sop/search', tags=['knowledge'])
def sop_search(q: str = Query(..., min_length=1, max_length=300), top_k: int = Query(3, ge=1, le=10),
               store_id: str = Depends(store_access), user: User = Depends(current_user)):
    hits = agent_for(user).multi_agent.docs_agent.search(q, top_k=top_k, category_filter='SOP_QUY_CHUAN')
    return [{'title': h['title'], 'content': h['content'], 'score': h['score'], 'citation': h['citation']} for h in hits]


@api.get('/v1/stores/{store_id}/recipes/{code}', tags=['knowledge'])
def recipe(code: str = Path(..., max_length=40), store_id: str = Depends(store_access), user: User = Depends(current_user)):
    return _plain(agent_for(user).tool_decode_recipe_or_sticker(code))


# --- photo reading (suggestion only) -------------------------------------------------------------------------

@api.post('/v1/stores/{store_id}/ocr/read', tags=['shift closing'])
async def ocr_read(files: list[UploadFile] = File(..., description='1–5 ảnh sổ / phiếu POS'),
                   business_date: date = Form(...), shift: str | None = Form(None, description='CA_SANG | CA_CHIEU | CA_TOI'),
                   store_id: str = Depends(store_access), user: User = Depends(current_user)):
    """Reads the photos and returns the suggested figures. Nothing is saved: staff check the numbers and
    submit the shift in the app, then a manager approves it."""
    if not 1 <= len(files) <= MAX_PHOTOS:
        raise HTTPException(422, f'Gửi từ 1 đến {MAX_PHOTOS} ảnh.')
    images = []
    for f in files:
        data = await f.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(413, f'Ảnh {f.filename} quá lớn.')
        images.append(data)
    from starlette.concurrency import run_in_threadpool
    from src.engine.vision_ocr import extract_image
    result = await run_in_threadpool(extract_image, images=images, shift_hint=shift, target_date=business_date.isoformat())
    return {'saved': False, 'note': 'Chỉ là gợi ý; nhân viên kiểm tra và gửi trên ứng dụng, Quản lý duyệt mới ghi doanh thu.',
            'result': _plain(result)}


# --- approvals (manager) -------------------------------------------------------------------------------------

@api.get('/v1/stores/{store_id}/approvals', tags=['approvals'])
def approvals(store_id: str = Depends(store_access), user: User = Depends(admin_user)):
    from src.dashboard.approval_center import pending_items
    return _plain(pending_items(agent_for(user), user.role, user.name, user.username))


class DecisionIn(BaseModel):
    approve: bool


@api.post('/v1/stores/{store_id}/approvals/{kind}/{item_id}', tags=['approvals'])
def decide(body: DecisionIn, kind: str = Path(..., pattern='^(shift|stock|plan)$'), item_id: str = Path(..., max_length=80),
           store_id: str = Depends(store_access), user: User = Depends(admin_user)):
    from src.dashboard.approval_center import _decide, pending_items
    agent = agent_for(user)
    items = [i for i in pending_items(agent, user.role, user.name, user.username) if i['kind'] == kind and i['id'] == item_id]
    if not items:
        raise HTTPException(404, 'Không có mục chờ duyệt này (có thể đã được xử lý).')
    return {'messages': _decide(agent, items, body.approve, user.role, user.name, user.username)}


# --- assistant -----------------------------------------------------------------------------------------------

class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


@api.post('/v1/stores/{store_id}/chat', tags=['assistant'])
def chat(body: ChatIn, store_id: str = Depends(store_access), user: User = Depends(current_user)):
    """Ask the assistant. A reply with `pending_approval` waits for POST .../chat/approval (manager accounts)."""
    result = agent_for(user).process_query(body.message, user.role, user.name, user_id=user.username)
    from src.dashboard.brand_ui import trace_steps
    out = {k: result.get(k) for k in ('text', 'tool_called', 'evidence_refs', 'pending_approval', 'execution_mode', 'trace')}
    out['steps'] = trace_steps(result.get('trace'), result.get('execution_mode'))
    return _plain(out)


@api.post('/v1/stores/{store_id}/chat/approval', tags=['assistant'])
def chat_approval(body: DecisionIn, store_id: str = Depends(store_access), user: User = Depends(admin_user)):
    result = agent_for(user).resume_approval(body.approve, user.role, user.name, user_id=user.username)
    from src.dashboard.brand_ui import trace_steps
    return _plain({**{k: result.get(k) for k in ('text', 'tool_called', 'evidence_refs', 'trace')},
                   'steps': trace_steps(result.get('trace'), result.get('execution_mode'))})


app = FastAPI(title='BeverageOps AI API (standalone)', docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/api', api)
