"""Ask the live assistant a few SOP questions, then read the admin AI-usage panel (shows whether the
semantic embedding call ran)."""
import json
import sys

from playwright.sync_api import sync_playwright

sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'sop_check']
import qa_live as q  # noqa: E402

QUESTIONS = ['tra tài liệu: những điểm còn cần xác nhận trong dữ liệu là gì', 'theo tài liệu, ảnh 17 là ảnh gì', 'việt quất đã có công thức trong tài liệu chưa']


def main():
    out = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = q.new_page(browser, label='sop')
        q.quick_login(page, 'quick_login_manager')
        q.nav(page, 'Tuyết Vương')
        q.idle(page, 1500)
        out['chat'] = [q.send_chat(page, m, f'sop_{i}') for i, m in enumerate(QUESTIONS)]
        q.shot(page, 'sop_chat')
        q.nav(page, 'Quản lý nhân viên')
        q.idle(page, 2000)
        panel = page.get_by_text('Mức dùng AI').first
        panel.scroll_into_view_if_needed()
        q.idle(page, 800)
        q.idle(page, 4000)
        q.shot(page, 'ai_usage_panel')
        out['usage_text'] = page.evaluate("document.body.innerText.split('Mức dùng AI')[1]?.slice(0, 3000) || ''")
        browser.close()
    (q.OUT / 'sop_check.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False)[:3000])


if __name__ == '__main__':
    main()
