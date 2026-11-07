"""Admin panel: tokens and cost of the AI calls (chat, photo reading, SOP embeddings) over the last days."""
import pandas as pd
import streamlit as st

from src.engine import llm_usage

VND_PER_USD = 26_000  # rough rate, only to give a feel for the amount
FEATURES = {'chat': 'Trợ lý chat', 'ocr': 'Đọc ảnh', 'embedding': 'Tra cứu SOP (vector)'}


def render_ai_usage_panel(days: int = 7):
    st.markdown("#### 📊 Mức dùng AI (token & chi phí)")
    rows = llm_usage.summary(days)
    if not rows:
        st.caption("Chưa có lượt gọi AI nào được ghi lại.")
        return
    df = pd.DataFrame(rows)
    today = df[df['day'] == df['day'].max()]
    c1, c2, c3 = st.columns(3)
    c1.metric("Token hôm nay", f"{int(today.input_tokens.sum() + today.output_tokens.sum()):,}".replace(',', '.'))
    c2.metric(f"Token {days} ngày", f"{int(df.input_tokens.sum() + df.output_tokens.sum()):,}".replace(',', '.'))
    cost = df.cost_usd.dropna().sum()
    c3.metric(f"Chi phí {days} ngày (nếu trả phí)", f"{cost:.3f} USD", help=f"≈ {cost * VND_PER_USD:,.0f} đ".replace(',', '.'))
    table = pd.DataFrame({
        'Ngày': df.day, 'Chức năng': df.feature.map(lambda f: FEATURES.get(f, f)), 'Model': df.model,
        'Lượt gọi': df.calls, 'Lỗi': df.failed, 'Token vào': df.input_tokens, 'Token ra': df.output_tokens,
        'Trong đó suy nghĩ': df.thinking_tokens,
        'Chi phí (USD)': df.cost_usd.map(lambda v: '—' if pd.isna(v) else f'{v:.4f}'),
    })
    st.dataframe(table, hide_index=True, width='stretch')
    notes = ["Gói miễn phí của Gemini không bị tính tiền; cột chi phí là số tiền nếu bật trả phí, theo giá niêm yết."]
    if df.cost_usd.isna().any():
        notes.append("“—”: model chưa có trong bảng giá.")
    if df.estimated.any():
        notes.append("Token của tra cứu vector là ước tính (API không trả số token).")
    st.caption(' '.join(notes))
