"""🛠️ Kỹ thuật AI — admin-only dashboard for whoever maintains the agent.

One tab per agent-engineering topic (guardrails, tool calling, human-in-the-loop, RAG, OCR, tracing/cost,
benchmarks, memory). Live numbers come from what the app records on every turn (structure only, no chat text);
offline numbers come from the benchmark files. See src/engine/ai_metrics.py.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.engine import ai_metrics

VND_PER_USD = 26_000


def _n(v, unit='', none='—', digits=0):
    if v is None:
        return none
    text = f'{v:,.{digits}f}'.replace(',', '§').replace('.', ',').replace('§', '.')
    return f'{text}{unit}'


def _ms(v):
    if v is None:
        return '—'
    return f'{v / 1000:.1f} s' if v >= 1000 else f'{v:.0f} ms'


def _table(rows, columns=None):
    if not rows:
        st.caption('Chưa có dữ liệu trong khoảng thời gian này.')
        return
    df = pd.DataFrame(rows)
    if columns:
        df = df.rename(columns=columns)[list(columns.values())]
    st.dataframe(df, hide_index=True, width='stretch')


@st.cache_data(ttl=60, show_spinner=False)
def _load(days: int):
    return ai_metrics.dashboard(days)


def render_ai_tech_page(agent):
    top = st.columns([3, 1.2], vertical_alignment='bottom')
    top[0].caption('Số liệu kỹ thuật của trợ lý AI và OCR. Chỉ ghi **cấu trúc** mỗi lượt chat (guardrail, tool, '
                   'quyền, duyệt, độ trễ, token) — không lưu nội dung câu hỏi hay câu trả lời.')
    days = top[1].segmented_control('Khoảng thời gian', [7, 14, 30], default=14, format_func=lambda d: f'{d} ngày',
                                    key='ai_tech_days') or 14
    with st.spinner('Đang tổng hợp…'):
        data = _load(days)
    a, u, o = data['agent'], data['usage'], data['ocr']

    k = st.columns(6)
    k[0].metric('Lượt chat', _n(a['chat_turns']))
    k[1].metric('Guardrail chặn', _n(a['guard']['blocked']), help='Số lượt bị chặn trước khi gọi AI')
    k[2].metric('Lượt gọi tool', _n(a['tool_calls']))
    ok = [t for t in a['tools'] if t['ok_pct'] is not None]
    k[3].metric('Tool chạy thành công', _n(sum(t['ok_pct'] * t['calls'] for t in ok) / max(1, sum(t['calls'] for t in ok)), '%', digits=1) if ok else '—')
    k[4].metric('OCR đọc đúng', _n(o['field_accuracy_pct'], '%', digits=1),
                help='So số OCR điền sẵn với số đã được nhân viên kiểm tra / Quản lý duyệt')
    k[5].metric(f'Chi phí {days} ngày', f"${u['cost_usd']:.2f}", help=f"{u['cost_usd']:.4f} USD ≈ {_n(u['cost_usd'] * VND_PER_USD)} đ (nếu trả phí)")

    tabs = st.tabs(['🛡️ Guardrail', '🧰 Tool calling', '✋ Human-in-the-loop', '📚 RAG', '📸 Vision OCR',
                    '⏱️ Tracing & chi phí', '🧪 Benchmark', '🧠 Bộ nhớ hội thoại'])

    with tabs[0]:
        st.caption('5 lớp guardrail & red teaming. Câu hỏi đi qua lớp chặn **trước** khi tới mô hình; '
                   'quyền gọi tool được kiểm lại ở máy chủ (RBAC) dù mô hình có yêu cầu.')
        g = a['guard']
        c = st.columns(4)
        c[0].metric('Lượt đã kiểm tra', _n(g['checked']))
        c[1].metric('Bị chặn', _n(g['blocked']), help='Prompt injection, đòi khóa bí mật, đòi nâng quyền…')
        c[2].metric('Tỉ lệ chặn', _n(g['blocked_pct'], '%', digits=1))
        c[3].metric('Tool bị từ chối quyền', _n(sum(a['denied_by_tool'].values())), help='Mô hình xin gọi tool mà vai trò không được dùng')
        left, right = st.columns(2)
        with left:
            st.markdown('**Lượt bị chặn theo loại**')
            _table([{'Loại': k_, 'Số lượt': v} for k_, v in g['by_category'].items()])
        with right:
            st.markdown('**RBAC từ chối theo tool**')
            _table([{'Tool': k_, 'Số lần': v} for k_, v in a['denied_by_tool'].items()])
        st.markdown('**Red team — chạy bộ câu tấn công ngay bây giờ**')
        rt = ai_metrics.redteam(agent)
        c = st.columns(3)
        c[0].metric('Chặn đúng câu tấn công', f"{_n(rt['blocked_pct'], '%', digits=0)}", help=f"{rt['attacks']} câu tấn công")
        c[1].metric('Chặn nhầm câu hỏi thường', f"{_n(rt['false_block_pct'], '%', digits=0)}", help=f"{rt['benign']} câu hỏi bình thường của quán")
        c[2].metric('Thời gian', 'không gọi AI', help='Lớp chặn chạy bằng luật trên máy chủ, vài mili-giây')
        with st.expander(f"Xem {len(rt['rows'])} câu thử"):
            st.dataframe(pd.DataFrame(rt['rows']), hide_index=True, width='stretch')

    with tabs[1]:
        st.caption('Function calling & tool contracts. Mỗi tool có schema tham số (Pydantic) và mức quyền; '
                   'tham số sai kiểu bị trả về cho mô hình sửa, không chạy.')
        auth = a['authorize']
        c = st.columns(4)
        c[0].metric('Được phép', _n(auth.get('allowed', 0)))
        c[1].metric('Từ chối quyền', _n(auth.get('denied', 0)))
        c[2].metric('Sai tham số', _n(auth.get('invalid_args', 0)))
        c[3].metric('Tool / lượt có AI', _n(a['tools_per_llm_turn'], digits=2))
        _table(a['tools'], {'tool': 'Tool', 'calls': 'Lượt gọi', 'ok_pct': 'Thành công (%)', 'p50_ms': 'Trung vị (ms)', 'p95_ms': 'p95 (ms)'})

    with tabs[2]:
        st.caption('Human-in-the-loop (maker–checker). AI chỉ soạn nháp; ghi doanh thu, duyệt đơn hàng '
                   'chỉ chạy ở bước duyệt sau khi người có quyền bấm xác nhận.')
        h, p = a['hitl'], data['plans']
        c = st.columns(4)
        c[0].metric('Lượt dừng chờ duyệt', _n(h['paused_for_approval']))
        c[1].metric('Đã duyệt', _n(h['approved_turns']))
        c[2].metric('Đã từ chối', _n(h['rejected_turns']))
        c[3].metric('Lần ghi qua bước duyệt', _n(h['writes_after_approval']), help='Bước "approval" trong trace — nơi duy nhất ghi dữ liệu')
        c = st.columns(3)
        c[0].metric('Kế hoạch / đơn tạo ra', _n(p['plans']))
        c[1].metric('Đã duyệt có tên người duyệt', f"{p['approved_with_approver']}/{p['approved_total']}")
        c[2].metric('Đơn Quản lý sửa số AI đề xuất', _n(p['edited_by_manager']))
        names = {'REPLENISHMENT_PO': 'Đơn nhập hàng', 'TOPPING_PREPARATION': 'Kế hoạch sơ chế', 'SHIFT_OCR_DRAFT': 'Chốt ca OCR'}
        _table([{'Loại': names.get(t, t), **s} for t, s in p['by_type'].items()])
        st.markdown('**Báo cáo chốt ca từ OCR theo trạng thái**')
        _table([{'Trạng thái': k_, 'Số báo cáo': v} for k_, v in o['status'].items()])

    with tabs[3]:
        st.caption('RAG & grounding. Tra SOP bằng BM25 + đặc trưng từ vựng + Gemini embedding, '
                   'gộp bằng learning-to-rank (ListNet) có ngưỡng từ chối câu ngoài phạm vi.')
        r = a['rag']
        c = st.columns(3)
        c[0].metric('Lượt tra cứu tài liệu', _n(r['calls']))
        c[1].metric('Có nguồn trả về', _n(r['with_sources_pct'], '%', digits=1))
        c[2].metric('Câu trả lời AI có dẫn chứng', _n(r['llm_answers_with_evidence_pct'], '%', digits=1))
        bench = data['retrieval']
        if bench:
            st.markdown(f"**So sánh phương pháp tìm kiếm** — {bench['questions']} câu hỏi có nhãn (offline)")
            df = pd.DataFrame(bench['rows']).rename(columns={'method': 'Phương pháp'})
            for col in ('Hit@1', 'Hit@3', 'Từ chối đúng'):
                df[col] = df[col].map(lambda v: '—' if v is None or v != v else f'{v:.1f}%')
            df['MRR'] = df['MRR'].map(lambda v: '—' if v is None else f'{v:.3f}')
            st.dataframe(df, hide_index=True, width='stretch')
            st.caption('RRF và các phương pháp đơn lẻ không có ngưỡng nên luôn trả 5 đoạn, kể cả câu ngoài phạm vi '
                       '(từ chối đúng = 0%). Learning-to-rank chấp nhận bỏ sót một ít để không trả lời bừa.')

    with tabs[4]:
        st.caption('Vision OCR — Gemini đọc sổ giao ca / hóa đơn POS và điền sẵn; nhân viên kiểm tra, Quản lý duyệt. '
                   'Độ chính xác = số OCR điền sẵn trùng với số cuối cùng được duyệt.')
        c = st.columns(4)
        c[0].metric('Báo cáo được chấm', _n(o['reports_scored']))
        c[1].metric('Ô số đọc đúng', _n(o['field_accuracy_pct'], '%', digits=1), help=f"{o['fields_checked']} ô")
        c[2].metric('Báo cáo không phải sửa ô nào', _n(o['reports_without_edit_pct'], '%', digits=1))
        c[3].metric('Một lần gọi OCR (trung vị)', '—' if u['ocr_call_p50_s'] is None else f"{u['ocr_call_p50_s']:.1f} s",
                    help='p95: ' + ('—' if u['ocr_call_p95_s'] is None else f"{u['ocr_call_p95_s']:.1f} s"))
        _table(o['per_field'], {'field': 'Ô', 'checked': 'Số lần', 'prefilled': 'OCR có điền', 'correct': 'Đúng', 'accuracy_pct': 'Đúng (%)'})
        if o['review_seconds_p50'] is not None:
            st.caption(f"Nhân viên kiểm tra một báo cáo mất trung vị {o['review_seconds_p50']:.0f} giây.")

    with tabs[5]:
        st.caption('Tracing, độ trễ, chi phí và dự phòng. Mỗi lượt có trace từng bước '
                   '(guard → model → authorize → tools → approval); khi AI lỗi, hệ thống chuyển sang luật offline.')
        c = st.columns(4)
        c[0].metric('Lượt gọi mô hình / lượt chat', _n(a['model_calls_per_llm_turn'], digits=2))
        c[1].metric('Token / lượt chat có AI', _n(a['tokens_per_llm_turn']))
        c[2].metric('Lượt chạy dự phòng', _n(a['fallback']['turns']), help=f"{_n(a['fallback']['pct'], '%', digits=1)} số lượt")
        c[3].metric('Chi phí / ngày', f"${u['cost_per_day_usd']:.3f}")
        left, right = st.columns(2)
        with left:
            st.markdown('**Độ trễ theo chế độ trả lời**')
            _table([{'Chế độ': v['label'], 'Lượt': v['turns'], 'Trung vị': _ms(v['p50_ms']), 'p95': _ms(v['p95_ms'])}
                    for v in a['latency'].values()])
            if a['fallback']['errors']:
                st.markdown('**Lỗi mô hình**')
                _table([{'Lỗi': k_, 'Số lượt': v} for k_, v in a['fallback']['errors'].items()])
        with right:
            st.markdown('**Lượt chat mỗi ngày**')
            if a['per_day']:
                st.bar_chart(pd.Series(a['per_day'], name='Lượt chat'), height=200)
            else:
                st.caption('Chưa có lượt chat.')
        st.markdown('**Token & chi phí theo chức năng**')
        names = {'chat': 'Trợ lý chat', 'ocr': 'Đọc ảnh OCR', 'embedding': 'Tra cứu vector'}
        _table([{'Chức năng': names.get(f, f), 'Lượt gọi': v['calls'], 'Lỗi': v['failed'], 'Token vào': v['input_tokens'],
                 'Token ra': v['output_tokens'], 'Chi phí (USD)': f"{v['cost_usd']:.4f}"} for f, v in u['by_feature'].items()])

    with tabs[6]:
        st.caption('Golden benchmark. 50 tình huống có đáp án (chào hỏi, công thức, doanh thu, kho, '
                   'quyền, tấn công…) chạy lại sau mỗi lần sửa để bắt lỗi hồi quy.')
        sc = data['scorecard']
        if sc:
            c = st.columns(4)
            c[0].metric('Đạt', f"{sc['passed']}/{sc['total']}", help=f"{sc['pass_rate_pct']}%")
            c[1].metric('Chế độ', 'Gemini (live)' if sc['mode'] == 'live_api' else 'Luật offline')
            c[2].metric('Độ trễ trung vị', f"{sc['median_latency_seconds']:.2f} s" if sc.get('median_latency_seconds') else '—')
            c[3].metric('Chạy lúc', sc['ran_at'].replace('T', ' ')[:16])
            _table([{'Nhóm': k_, 'Đạt': v['passed'], 'Tổng': v['total']} for k_, v in sc['categories'].items()])
        else:
            st.info('Chưa chạy bộ benchmark trên máy chủ này.')
        b = st.columns([1, 1, 2], vertical_alignment='center')
        if b[0].button('▶️ Chạy offline', key='run_scorecard_offline', help='Không gọi AI, khoảng vài giây'):
            with st.spinner('Đang chạy 50 tình huống…'):
                ai_metrics.run_scorecard(live=False)
            _load.clear()
            st.rerun()
        live_ok = b[2].checkbox('Tôi đồng ý gọi Gemini (~50 lượt chat, tốn token)', key='scorecard_live_ok')
        if b[1].button('▶️ Chạy với Gemini', key='run_scorecard_live', disabled=not live_ok):
            with st.spinner('Đang chạy 50 tình huống với Gemini (1–3 phút)…'):
                try:
                    ai_metrics.run_scorecard(live=True)
                except SystemExit as exc:
                    st.error(str(exc))
            _load.clear()
            st.rerun()

    with tabs[7]:
        st.caption('Bộ nhớ hội thoại nhiều lượt. Lịch sử dài được tóm tắt để giữ ngữ cảnh mà không '
                   'gửi lại toàn bộ cho mô hình; nhân viên chấm 👍/👎 từng câu trả lời.')
        m = data['conversations']
        c = st.columns(5)
        c[0].metric('Cuộc trò chuyện', _n(m['conversations']))
        c[1].metric('Tin nhắn', _n(m['messages']))
        c[2].metric('Bản tóm tắt hội thoại', _n(m['summaries']))
        c[3].metric('👍 / 👎', f"{m['thumbs_up']} / {m['thumbs_down']}")
        c[4].metric('Hài lòng', _n(m.get('satisfaction_pct'), '%', digits=0))
    st.caption(f"Cập nhật lúc {data['generated_at'][11:16]} · số liệu được lưu tạm 60 giây.")
