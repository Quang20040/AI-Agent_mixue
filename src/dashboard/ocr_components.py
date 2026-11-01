"""Shared presentation of the Verifiable OCR pipeline (OCR page and chat draft card).

Only renders what the OCR engine returned: the raw text read on the image, the normalized
value the verification rules accepted, and why a field still needs a human. It never
derives or fills a number itself.
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

FIELD_LABELS: dict[str, str] = {
    'pos_revenue_vnd': 'Tổng doanh thu POS',
    'pos_collected_vnd': 'Thực thu trên POS',
    'cash_vnd': 'Tiền mặt',
    'cash_diff_vnd': 'Tiền mặt dư/thiếu',
    'bank_transfer_vnd': 'Chuyển khoản',
    'shopee_food_vnd': 'ShopeeFood',
    'grab_food_vnd': 'GrabFood',
    'be_food_vnd': 'BeFood',
    'petty_cash_kept_vnd': 'Cố định két',
    'expenses_vnd': 'Khoản chi trong ca',
    'total_collected_vnd': 'Tổng thu về',
}

DOCUMENT_BADGES: dict[str, tuple[str, str]] = {
    'pos_receipt': ('🧾 Hóa đơn POS', 'pos'),
    'handwritten_ledger': ('✍️ Sổ tay viết tay', 'hw'),
    'composite': ('🧾 + ✍️ Ảnh ghép POS & sổ tay', 'mix'),
    'non_financial': ('🚫 Không phải chứng từ tiền', 'bad'),
    'unreadable': ('❌ Ảnh không đọc được', 'bad'),
    'unknown': ('❔ Chưa xác định loại chứng từ', 'unk'),
}

SOURCE_BADGES: dict[str, tuple[str, str]] = {
    'pos_receipt': ('🧾 Hóa đơn POS', 'pos'),
    'handwritten_ledger': ('✍️ Sổ tay viết tay', 'hw'),
    'both_conflicting': ('⚠️ Trộn POS & sổ tay', 'warn'),
    'not_applicable': ('—', 'unk'),
    'unknown': ('❔ Chưa rõ nguồn', 'unk'),
}

STATUS_BADGES: dict[str, tuple[str, str]] = {
    'read': ('✅ Đọc rõ · read', 'ok'),
    'uncertain': ('⚠️ Cần kiểm tra · uncertain', 'warn'),
    'unreadable': ('❌ Mờ / không đọc được', 'bad'),
    'not_present': ('❌ Không có trên ảnh', 'muted'),
}

_CSS = '''<style>
.vocr-badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap;border:1px solid transparent}
.vocr-pos{background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe}.vocr-hw{background:#f5f3ff;color:#6d28d9;border-color:#ddd6fe}
.vocr-mix{background:#ecfeff;color:#0e7490;border-color:#a5f3fc}.vocr-ok{background:#ecfdf5;color:#047857;border-color:#a7f3d0}
.vocr-warn{background:#fffbeb;color:#b45309;border-color:#fde68a}.vocr-bad{background:#fef2f2;color:#b91c1c;border-color:#fecaca}
.vocr-muted,.vocr-unk{background:#f8fafc;color:#64748b;border-color:#e2e8f0}
.vocr-table{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0 10px}
.vocr-table th{background:#fff1f2;color:#9f1239;text-align:left;padding:6px 8px;border-bottom:2px solid #fecdd3}
.vocr-table td{padding:6px 8px;border-bottom:1px solid #f1f5f9;vertical-align:top}
.vocr-table code{background:#f8fafc;padding:1px 5px;border-radius:4px}
.vocr-num{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
</style>'''


def badge(text: str, tone: str) -> str:
    return f'<span class="vocr-badge vocr-{tone}">{escape(text)}</span>'


def install_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def money(value: Any) -> str:
    return f'{int(value):,} đ'.replace(',', '.') if isinstance(value, (int, float)) else '—'


def pipeline_states(extracted: dict[str, Any] | None) -> list[tuple[str, str, str]]:
    """(title, detail, state) for the six verification stages; state is pending|done|warn|active."""
    titles = ['Chất lượng ảnh', 'Tách vùng chứng từ', 'Đọc thô', 'Quy tắc kiểm chứng', 'Đối soát số học', 'Người xác nhận']
    idle = ['Độ nét, tương phản', 'POS · sổ tay · ảnh ghép', 'Giữ nguyên chuỗi trên ảnh', 'Không nhân 1.000, không tự cộng',
            'Cộng ngang & chéo POS', 'Quản lý phê duyệt']
    extracted = extracted or {}
    if extracted.get('status') != 'NEEDS_REVIEW':
        states = ['pending'] * 6
        if extracted:
            idle = [extracted.get('message') or str(extracted.get('status')), *idle[1:]]
            states[0] = 'warn'
        return list(zip(titles, idle, states))
    quality = extracted.get('image_quality') or {}
    readings = extracted.get('field_readings') or {}
    with_text = sum(1 for r in readings.values() if r.get('raw_text'))
    flagged = sum(1 for r in readings.values() if r.get('status') in {'uncertain', 'unreadable'})
    discrepancies = (extracted.get('consistency') or {}).get('discrepancies') or []
    doc_label = DOCUMENT_BADGES.get(extracted.get('document_type') or 'unknown', DOCUMENT_BADGES['unknown'])[0]
    return [
        (titles[0], 'Ảnh mờ: mọi trường chờ xác nhận' if quality.get('is_blurry') else f"Đủ nét · tương phản {quality.get('contrast', '—')}",
         'warn' if quality.get('is_blurry') else 'done'),
        (titles[1], doc_label, 'done'),
        (titles[2], f'{with_text} trường có chữ', 'done'),
        (titles[3], f'{flagged} trường gắn cờ' if flagged else 'Không có trường mơ hồ', 'warn' if flagged else 'done'),
        (titles[4], f'{len(discrepancies)} chênh lệch' if discrepancies else 'Các khoản khớp nhau', 'warn' if discrepancies else 'done'),
        (titles[5], 'Đang chờ bạn xác nhận', 'active'),
    ]


def render_pipeline_steps(extracted: dict[str, Any] | None = None, slot=None) -> None:
    """The six verification stages in the order the engine applies them, with live state."""
    marks = {'done': '✓', 'warn': '!', 'active': '6', 'pending': ''}
    items = ''.join(
        f'<li class="vocr-step {state}"><span class="dot" aria-hidden="true">{marks[state] or index}</span>'
        f'<div><b>{escape(title)}</b>{escape(detail)}</div><i class="fill" aria-hidden="true"></i></li>'
        for index, (title, detail, state) in enumerate(pipeline_states(extracted), 1))
    html = f'<ol class="vocr-steps" aria-label="Quy trình kiểm chứng" style="list-style:none;padding:0">{items}</ol>'
    (slot or st).markdown(html, unsafe_allow_html=True)


def document_badge(document_type: str | None) -> str:
    return badge(*DOCUMENT_BADGES.get(document_type or 'unknown', DOCUMENT_BADGES['unknown']))


def field_rows(field_readings: dict[str, dict[str, Any]], form_values: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Plain rows for tables/tests. ``form_values`` are the values actually in the form."""
    form_values = form_values or {}
    rows = []
    for name, label in FIELD_LABELS.items():
        item = field_readings.get(name) or {}
        status = item.get('status', 'not_present')
        if status == 'not_present' and not item.get('raw_text') and form_values.get(name) is None:
            continue
        rows.append({
            'field': name,
            'label': label,
            'source': item.get('source', 'unknown'),
            'status': status,
            'raw_text': item.get('raw_text') or item.get('evidence') or '',
            'normalized_value': item.get('normalized_value') if status == 'read' else None,
            'form_value': form_values.get(name),
            'is_calculated': bool(item.get('is_calculated')),
            'unit_explicit': item.get('unit_explicit'),
            'review_reason': item.get('review_reason') or '',
        })
    return rows


def render_field_table(field_readings: dict[str, dict[str, Any]], form_values: dict[str, Any] | None = None) -> None:
    rows = field_rows(field_readings, form_values)
    if not rows:
        st.caption('Chưa có trường tiền nào được đọc từ ảnh.')
        return
    body = []
    for row in rows:
        flags = []
        if row['is_calculated']:
            flags.append(badge('Σ biểu thức', 'warn'))
        if row['unit_explicit'] is False:
            flags.append(badge('đơn vị chưa rõ', 'warn'))
        body.append(
            f"<tr><td><b>{escape(row['label'])}</b><br><small><code>{escape(row['field'])}</code></small></td>"
            f"<td>{badge(*SOURCE_BADGES.get(row['source'], SOURCE_BADGES['unknown']))}</td>"
            f"<td>{badge(*STATUS_BADGES.get(row['status'], STATUS_BADGES['not_present']))}<br>{' '.join(flags)}</td>"
            f"<td><code>{escape(str(row['raw_text'])[:80]) or '—'}</code></td>"
            f"<td class='vocr-num'>{money(row['normalized_value'])}</td>"
            f"<td>{escape(row['review_reason'][:260]) or '—'}</td></tr>")
    st.markdown(
        '<table class="vocr-table"><thead><tr><th>Khoản mục</th><th>Nguồn</th><th>Trạng thái</th>'
        '<th>Đọc thô (raw_text)</th><th>Chuẩn hóa (normalized_value)</th><th>Lý do cần xác nhận (review_reason)</th>'
        '</tr></thead><tbody>' + ''.join(body) + '</tbody></table>', unsafe_allow_html=True)
    st.caption('Trường ⚠️ được để trống trong biểu mẫu: hệ thống không tự điền, không tự nhân 1.000 và không tự cộng biểu thức.')


def render_image_quality(quality: dict[str, Any] | None) -> None:
    if not quality:
        return
    tone = 'bad' if quality.get('is_blurry') else 'ok'
    sharp = 'Ảnh mờ / tương phản thấp' if quality.get('is_blurry') else 'Ảnh đủ nét'
    layout = '2 cột (có thể là ảnh ghép)' if quality.get('has_dual_columns') else '1 vùng chính'
    st.markdown(
        f"{badge(sharp, tone)} {badge('Bố cục: ' + layout, 'unk')} "
        f"<small>tương phản {quality.get('contrast', '—')} · cạnh max {quality.get('edge_max', '—')} · "
        f"{quality.get('width', '—')}×{quality.get('height', '—')} px</small>", unsafe_allow_html=True)


def render_benchmark(report: dict[str, Any], images: dict[str, bytes] | None = None) -> None:
    """Show the raw-vs-verified error taxonomy produced by ``run_ocr_benchmark``."""
    verified, raw = report['verified_summary'], report['raw_summary']
    m1, m2, m3 = st.columns(3)
    m1.metric('Trường được chấm', verified.get('fields_evaluated', 0))
    m2.metric('Lỗi lọt vào biểu mẫu · bản đọc thô', raw.get('errors_reaching_form', 0))
    m3.metric('Lỗi lọt vào biểu mẫu · có kiểm chứng', verified.get('errors_reaching_form', 0),
              delta=verified.get('errors_reaching_form', 0) - raw.get('errors_reaching_form', 0), delta_color='inverse')
    labels = report['taxonomy_labels']
    top = max([1, *raw['taxonomy_7'].values(), *verified['taxonomy_7'].values()])
    bars = ''.join(
        f"<div class='vocr-bar-row'><span>{escape(labels[key])}</span><div class='vocr-bar-pair'>"
        f"<div class='vocr-bar-line'><span class='vocr-bar raw' style='--w:{raw['taxonomy_7'].get(key, 0) / top * 100:.0f}%'></span>{raw['taxonomy_7'].get(key, 0)}</div>"
        f"<div class='vocr-bar-line'><span class='vocr-bar ver' style='--w:{verified['taxonomy_7'].get(key, 0) / top * 100:.0f}%'></span>{verified['taxonomy_7'].get(key, 0)}</div>"
        "</div></div>" for key in report['taxonomy_order'])
    st.markdown("<div class='vocr-legend'><span><i style='background:#f4a3ab'></i>Bản đọc thô</span>"
                "<span><i style='background:#c4000f'></i>Có kiểm chứng</span></div>"
                f"<div class='vocr-bars'>{bars}</div>", unsafe_allow_html=True)
    rows = ''.join(
        f"<tr><td><code>{key}</code></td><td>{escape(labels[key])}</td>"
        f"<td class='vocr-num'>{raw['taxonomy_7'].get(key, 0)}</td><td class='vocr-num'>{verified['taxonomy_7'].get(key, 0)}</td></tr>"
        for key in report['taxonomy_order'])
    other_raw = ', '.join(f'{k}: {v}' for k, v in raw.get('other_counts', {}).items()) or '—'
    other_ver = ', '.join(f'{k}: {v}' for k, v in verified.get('other_counts', {}).items()) or '—'
    rows += f"<tr><td colspan='2'><i>Khác (không có trên ảnh, ảnh mờ không cảnh báo…)</i></td><td>{escape(other_raw)}</td><td>{escape(other_ver)}</td></tr>"
    with st.expander('Bảng số liệu 7 nhóm lỗi', expanded=False):
        st.markdown('<table class="vocr-table"><thead><tr><th>Nhóm lỗi</th><th>Ý nghĩa</th><th>Bản đọc thô (tin số mô hình)</th>'
                    '<th>Pipeline có kiểm chứng</th></tr></thead><tbody>' + rows + '</tbody></table>', unsafe_allow_html=True)
    st.caption(report.get('note', ''))

    cases = report.get('cases', [])
    tabs = st.tabs([c['title'] for c in cases])
    for tab, case in zip(tabs, cases):
        with tab:
            if case.get('note'):
                st.caption('📝 ' + case['note'])
            if case.get('reading_meta'):
                meta = case['reading_meta']
                st.caption(f"Bản đọc của `{meta.get('model') or 'mô hình'}` · ghi lúc {meta.get('recorded_at') or '—'} · {meta.get('latency_s') or '—'} s")
            if case.get('skipped_reason'):
                st.warning(f"Bỏ qua: {case['skipped_reason']}")
                continue
            left, right = st.columns([1, 2.2])
            with left:
                if images and images.get(case['image_key']):
                    st.image(images[case['image_key']], caption=case['image_key'], use_container_width=True)
                st.markdown(document_badge(case.get('document_type')), unsafe_allow_html=True)
                render_image_quality(case.get('image_quality'))
                for disc in case.get('discrepancies', []):
                    st.error(disc.get('message', ''))
            with right:
                lines = ''.join(
                    f"<tr><td><code>{escape(name)}</code></td><td>{escape(case['raw']['field_results'][name]['outcome'])}</td>"
                    f"<td>{escape(res['outcome'])}</td><td>{escape(res['detail'][:160])}</td></tr>"
                    for name, res in case['verified']['field_results'].items()
                    if not (res['outcome'] == 'correct_not_present' and case['raw']['field_results'][name]['outcome'] == 'correct_not_present'))
                consistency = case['verified']['consistency_check_passed']
                st.markdown('<table class="vocr-table"><thead><tr><th>Trường</th><th>Bản đọc thô</th><th>Có kiểm chứng</th><th>Chi tiết</th>'
                            '</tr></thead><tbody>' + lines + '</tbody></table>', unsafe_allow_html=True)
                st.caption(('✅' if consistency else '❌') + ' Kiểm tra số học: '
                           + ('đã phát hiện đúng chênh lệch / số khớp.' if consistency else 'chưa phát hiện chênh lệch.'))
