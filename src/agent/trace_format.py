"""Agent trace → plain Vietnamese steps (guardrail, model, permission check, tool calls, approval).

Used by the chat in Streamlit and by the REST API, so the explanation of what the agent did is the same everywhere.
"""


EFFECT_VI = {'read': 'chỉ đọc', 'draft': 'tạo bản nháp', 'approval': 'cần Quản lý duyệt'}


GUARD_VI = {'PROMPT_INJECTION_DEFENSE': 'cố đổi hướng dẫn của trợ lý (prompt injection)',
            'CREDENTIAL_EXFILTRATION_DEFENSE': 'đòi mật khẩu / API key',
            'PRIVILEGE_ESCALATION_DEFENSE': 'đòi nâng quyền tài khoản'}


def trace_steps(trace, mode=None) -> list[str]:
    """The agent's run as plain-language steps: guardrail, model, permission check, tools, approval."""
    def fmt_args(args):
        if not args:
            return ''
        return ', '.join(f'{k}={v}' for k, v in args.items())
    steps = []
    for ev in trace or []:
        node = ev.get('node')
        if node == 'guard':
            if ev.get('result') == 'blocked':
                steps.append(f"🛡️ **Guardrail chặn** — {GUARD_VI.get(ev.get('category'), ev.get('category', 'vi phạm quy định'))}; không gọi AI, không gọi tool.")
            elif ev.get('result') == 'direct_reply':
                steps.append('🛡️ **Guardrail:** câu chào hỏi / hỏi danh tính → trả lời trực tiếp, không gọi AI.')
            elif ev.get('forced_tool'):
                steps.append(f"🛡️ **Guardrail:** hợp lệ · máy chủ chọn sẵn tool `{ev['forced_tool']}` (không để AI tự chọn).")
            else:
                steps.append('🛡️ **Guardrail:** câu hỏi hợp lệ (không chứa prompt injection, đòi bí mật hay nâng quyền).')
        elif node == 'model':
            tokens = f" · {ev.get('input_tokens', 0):,} → {ev.get('output_tokens', 0):,} token".replace(',', '.') if ev.get('input_tokens') else ''
            if ev.get('requested'):
                steps.append(f"🧠 **Mô hình `{ev.get('model', 'AI')}`** quyết định gọi tool: " + ', '.join(f'`{t}`' for t in ev['requested']) + tokens)
            else:
                steps.append(f"🧠 **Mô hình `{ev.get('model', 'AI')}`** soạn câu trả lời từ kết quả tool{tokens}")
        elif node == 'authorize':
            if ev.get('result') == 'denied':
                steps.append(f"🔐 **Kiểm tra quyền:** vai trò `{ev.get('role')}` không được dùng `{ev.get('tool')}` → dừng.")
            else:
                for call in ev.get('calls') or []:
                    steps.append(f"🔐 **Kiểm tra quyền** (`{ev.get('role')}`): cho phép `{call['tool']}` — quyền {call.get('permission')}, "
                                 f"{EFFECT_VI.get(call.get('effect'), call.get('effect'))}; tham số đã kiểm tra kiểu.")
                if ev.get('result') == 'invalid_args':
                    steps.append('🔐 Tham số AI đưa sai kiểu → trả lỗi lại cho mô hình, không chạy tool.')
        elif node == 'tools':
            args = fmt_args(ev.get('args'))
            extra = ' · '.join(x for x in (ev.get('summary'), f"{ev['sources']} nguồn" if ev.get('sources') else '') if x)
            steps.append(f"🔧 **Tool `{ev.get('tool')}`**({args}) → `{ev.get('status')}` · {ev.get('duration_ms', 0)} ms" + (f' · {extra}' if extra else ''))
        elif node == 'approval':
            steps.append(f"⏸️ **Chờ duyệt:** thao tác ghi sổ dừng lại cho Quản lý xác nhận → `{ev.get('status')}`.")
        elif node == 'grounded_response':
            steps.append('📌 **Trả lời theo đúng số liệu tool trả về** (không để mô hình tự viết lại con số).')
        elif node == 'router':
            steps.append(f"🧭 **Bộ định tuyến:** xử lý trực tiếp bằng `{ev.get('tool')}`.")
        elif node == 'offline_rules':
            steps.append(f"📴 **Chế độ offline** ({ev.get('result')}) → bộ luật tra cứu cục bộ `{ev.get('tool') or '—'}` trả lời.")
    if not steps and mode:
        steps.append(f'Chế độ: `{mode}`.')
    return steps
