"""Verify user-reported conversation examples against the local dashboard."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

out = Path('output/chat-review')
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1440, 'height':1050})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8599')
    page.locator('input[type=text]').first.fill('quanly')
    page.locator('input[type=password]').first.fill('123')
    page.keyboard.press('Enter')
    page.locator('.mx-summary-grid').wait_for(timeout=60000)
    page.locator('.st-key-main_navigation [data-testid=stRadioOption]').filter(has_text='Tuyết Vương AI').click()
    page.locator('.st-key-chat_panel_box textarea').wait_for(timeout=30000)
    chat = page.locator('.st-key-chat_panel_box')
    chat.locator('textarea').fill('hi')
    chat.locator('textarea').press('Enter')
    chat.get_by_text('Xin chào! 👋', exact=True).wait_for(timeout=30000)
    assert chat.get_by_text('Nguồn dữ liệu', exact=True).count() == 0
    assert 'Tổng doanh thu' not in chat.inner_text()
    page.screenshot(path=str(out / 'greeting.png'))
    chat.locator('textarea').fill('công thức nấu trân châu')
    chat.locator('textarea').press('Enter')
    chat.get_by_text('Định lượng 1 mẻ:', exact=True).wait_for(timeout=30000)
    page.wait_for_function('document.querySelector(".stApp")?.dataset.testScriptState === "notRunning"')
    content = chat.inner_text()
    for word in ['35 phút','30 phút','10 phút','4 giờ']:
        assert word in content, word
    for irrelevant in ['docs/demo.md','lục tìm','FIFO','Maker-Checker','Định nghĩa']:
        assert irrelevant not in content, irrelevant
    assert not chat.get_by_text('Công thức sơ chế theo mẻ', exact=False).is_visible()
    chat.locator('summary').filter(has_text='Nguồn dữ liệu').click()
    assert chat.get_by_text('Công thức sơ chế theo mẻ', exact=False).is_visible()
    assert 'DU_LIEU_CAN_NHAP/' not in chat.inner_text()
    chat.locator('summary').filter(has_text='Nguồn dữ liệu').click()
    page.screenshot(path=str(out / 'pearl-guide.png'))
    chat.locator('textarea').fill('Bạn dễ thương quá')
    chat.locator('textarea').press('Enter')
    chat.get_by_text('Nghe ngọt hơn cả trà sữa rồi đó 😊', exact=True).wait_for(timeout=30000)
    chat.locator('textarea').fill('Kể chuyện cười đi')
    chat.locator('textarea').press('Enter')
    chat.get_by_text('Trân châu hỏi trà sữa:', exact=False).wait_for(timeout=30000)
    page.wait_for_function('document.querySelector(".stApp")?.dataset.testScriptState === "notRunning"')
    assert 'ngoài phạm vi' not in chat.locator('[data-testid=stChatMessage]').last.inner_text().lower()
    page.screenshot(path=str(out / 'casual-chat.png'))
    assert not errors, errors
    report = {'greeting_short_without_evidence':True, 'cooking_guide_focused':True,
              'source_names_collapsed_by_default':True, 'casual_chat_not_blocked':True, 'browser_errors':errors}
    (out / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    browser.close()
