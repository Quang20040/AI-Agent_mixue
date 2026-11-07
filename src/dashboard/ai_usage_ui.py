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


def render_backup_panel():
    st.markdown("#### 💾 Sao lưu dữ liệu")
    st.caption("Một file .zip gồm cơ sở dữ liệu, báo cáo chốt ca, ảnh chứng từ, lịch sử chat, nhật ký kiểm toán và "
               "chi phí AI. Nên tải về trước mỗi lần nâng cấp / chuyển máy chủ.")
    if st.button("Tạo bản sao lưu", key="make_backup"):
        from src.engine.data_export import export_bytes
        with st.spinner("Đang đóng gói dữ liệu…"):
            st.session_state["backup_zip"] = export_bytes()
    if st.session_state.get("backup_zip"):
        data, name = st.session_state["backup_zip"]
        st.download_button(f"⬇️ Tải {name} ({len(data) / 1024 / 1024:.1f} MB)", data, file_name=name,
                           mime="application/zip", key="download_backup")


def render_sample_purge_panel(username: str):
    """Owner/manager: remove the simulated history (backup first, one transaction, audit line)."""
    from src.engine import sample_purge
    st.markdown("#### 🧹 Xóa dữ liệu mô phỏng")
    counts = sample_purge.preview()
    total = sum(counts.values())
    if not total:
        st.caption(f"Không còn dữ liệu mô phỏng. Cơ sở dữ liệu chỉ chứa dữ liệu thật (từ {sample_purge.REAL_FROM:%d/%m/%Y}).")
        return
    st.caption(f"Lịch sử sinh ra để chạy thử dự báo, trước {sample_purge.REAL_FROM:%d/%m/%Y}. Giữ nguyên: tài khoản, thực đơn, "
               "nguyên liệu, công thức, phiếu kho, báo cáo chốt ca đã duyệt và ngày 14/10 (số POS thật).")
    st.dataframe(pd.DataFrame([{"Dữ liệu": sample_purge.LABELS[k], "Bảng": k, "Số dòng sẽ xóa": v} for k, v in counts.items()]),
                 hide_index=True, width='stretch')
    sure = st.checkbox(f"Tôi hiểu thao tác này xóa vĩnh viễn {total:,} dòng (có tự sao lưu trước)".replace(",", "."), key="purge_sure")
    if st.button("Xóa dữ liệu mô phỏng", type="primary", disabled=not sure, key="purge_go"):
        with st.spinner("Đang sao lưu rồi xóa…"):
            result = sample_purge.apply(username)
        st.cache_data.clear()
        st.success(f"Đã xóa {sum(result['deleted'].values()):,} dòng. Bản sao lưu trước khi xóa: {result['backup']}".replace(",", "."))
