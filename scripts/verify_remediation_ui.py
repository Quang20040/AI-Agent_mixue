"""Streamlit UI smoke in a fresh copy containing synthetic records only."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]

CHILD = '''
import json
from datetime import date, timedelta
from pathlib import Path
from streamlit.testing.v1 import AppTest
from src.database import Base, engine, SessionLocal
from src.models import User, Ingredient, MenuItem, SalesDaily
from src.dashboard.sales_view import business_today
from src.auth import hash_password
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add(User(username='synthetic_admin', full_name='Synthetic Admin', role='ADMIN',
                password_hash=hash_password('synthetic-ui-password'), is_active=True, must_change_password=False))
    db.add(Ingredient(ingredient_id='1', ingredient_name='Synthetic Ingredient', base_unit='g', ingredient_group='dry'))
    db.add(MenuItem(sku_id='SYN', sku_name='Synthetic Drink', selling_price_vnd=10000, effective_from=date(2026,1,1)))
    db.commit()
    db.add(SalesDaily(store_id='2132', sku_id='SYN', business_date=business_today()-timedelta(days=7), quantity_sold=1574, revenue_vnd=36455000))
    db.commit()
app = AppTest.from_file('src/dashboard/app.py', default_timeout=60).run()
assert not app.exception, str(app.exception)
assert not any('Vào nhanh' in button.label for button in app.button)
app.text_input(key='login_username').set_value('synthetic_admin')
app.text_input(key='login_password').set_value('synthetic-ui-password')
next(button for button in app.button if 'Đăng nhập' in button.label).click().run()
assert not app.exception, str(app.exception)
assert app.session_state['authenticated']
home = ' '.join(item.value for item in app.markdown)
assert 'Chưa có kết quả' in home and 'Doanh thu hôm nay' in home
assert '36.455.000' not in home
assert not any('Chat Tuyết Vương AI' in button.label for button in app.button)
with SessionLocal() as db:
    db.add(SalesDaily(store_id='2132', sku_id='SYN', business_date=business_today(), quantity_sold=0, revenue_vnd=0))
    db.commit()
app.run()
assert not app.exception, str(app.exception)
home = ' '.join(item.value for item in app.markdown)
assert '0 đ' in home
app.radio(key='main_navigation').set_value('Tem & công thức').run()
assert not app.exception, str(app.exception)
assert not any(item.label == 'Nhập mã tem ly' for item in app.text_input)
assert not any('Giải mã' in item.label for item in app.button)
app.radio(key='main_navigation').set_value('💬 Tuyết Vương AI').run()
assert not app.exception, str(app.exception)
assert len(app.chat_input) == 1
app.chat_input[0].set_value('Xin chào').run()
assert not app.exception, str(app.exception)
assert len(app.chat_message) >= 2
app.button(key='clear_chat').click().run()
assert not app.exception, str(app.exception)
app.radio(key='main_navigation').set_value('Báo cáo & kho').run()
assert not app.exception, str(app.exception)
app.date_input(key='stock_period').set_value(date(2026,11,1)).run()
assert not app.exception, str(app.exception)
assert app.date_input(key='stock_period').value.month == 11
print('UI_SMOKE_RESULT=' + json.dumps({'production_login': True, 'no_demo_shortcut': True,
                                     'stock_page': True, 'november_period': True, 'stale_sales_not_today': True,
                                     'fresh_zero_sales': True, 'no_sticker_decoder': True, 'chat_send_and_new_conversation': True}))
'''


def main():
    target = ROOT / 'output' / ('remediation-ui-' + uuid.uuid4().hex[:8])
    target.mkdir(parents=True)
    shutil.copytree(ROOT / 'src', target / 'src', ignore=shutil.ignore_patterns('__pycache__'))
    (target / 'data').mkdir()
    (target / 'data' / 'shift_reports.json').write_text('[]', encoding='utf-8')
    env = {**os.environ, 'PYTHONPATH': str(target), 'DATABASE_URL': 'sqlite:///' + (target / 'data' / 'beverageops.db').as_posix(),
           'APP_ENV': 'production', 'APP_DEMO_MODE': 'false', 'STORE_ID': '2132', 'POSTGRES_MCP_ENABLED': 'false',
           'LLM_ENABLED': 'false', 'WEATHER_ENABLED': 'false', 'OCR_ENABLED': 'false',
           'ALLOW_EXTERNAL_DATA_TRANSFER': 'false'}
    process = subprocess.run([sys.executable, '-c', CHILD], cwd=target, env=env, capture_output=True, text=True, encoding='utf-8', timeout=180)
    (target / 'result.txt').write_text(process.stdout + '\n' + process.stderr, encoding='utf-8')
    print(str(target / 'result.txt'))
    print(process.stdout[-2000:])
    if process.returncode:
        print(process.stderr[-5000:])
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
