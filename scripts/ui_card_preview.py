"""Stand-alone page showing the LangGraph approval card with sample data (for UI screenshots).

Query parameters: total (Tổng thu về in VND), admin=1/0.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from src.dashboard import brand_ui  # noqa: E402
from src.engine.vision_ocr import MONEY_FIELDS, MoneyReading, ShiftReading, check_ocr_consistency  # noqa: E402

st.set_page_config(layout='wide')
brand_ui.install_brand()
values = dict(cash_vnd=1_193_000, cash_diff_vnd=15_000, bank_transfer_vnd=1_126_000, shopee_food_vnd=85_000, grab_food_vnd=0,
              be_food_vnd=0, petty_cash_kept_vnd=1_000_000, expenses_vnd=0,
              total_collected_vnd=int(st.query_params.get('total', 2_389_000)))
reading = ShiftReading(document_type='handwritten_ledger', document_date='2026-11-01', signed_by='Hà', raw_text='preview',
                       fields={m: MoneyReading(value=values.get(m), status='read' if values.get(m) is not None else 'not_present',
                                               source='handwritten_ledger') for m in MONEY_FIELDS})
pending = {'plan_type': 'SHIFT_OCR_DRAFT', 'plan_id': 'DRAFT_OCR_PREVIEW', 'requested_by': 'quanly',
           'plan': {'document_type': 'composite', 'fields': {**values, 'report_date': '2026-11-01', 'shift_code': 'CA_SANG'},
                    'consistency': check_ocr_consistency(reading)}}
brand_ui.render_approval_card(None, pending, 'MANAGER', 'quanly', st.query_params.get('admin', '1') == '1')
