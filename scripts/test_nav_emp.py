from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator("button:has-text('Quản Lý (Admin)')").first.click()
    page.wait_for_timeout(3000)
    
    # Try exact label
    lbl = page.locator("div[aria-label='Điều hướng'] label:has-text('Quản lý nhân viên')").first
    print("Found count:", lbl.count(), "text:", repr(lbl.inner_text()))
    lbl.click(force=True)
    page.wait_for_timeout(2000)
    print("Has metrics:", page.is_visible("text=Tổng số nhân sự"))
    
    # Try chat
    lbl_chat = page.locator("div[aria-label='Điều hướng'] label:has-text('Tuyết Vương AI')").first
    print("Found chat count:", lbl_chat.count(), "text:", repr(lbl_chat.inner_text()))
    lbl_chat.click(force=True)
    page.wait_for_timeout(2000)
    print("Has chat input:", page.is_visible("textarea[placeholder*='Hỏi Tuyết Vương']") or page.is_visible("input[placeholder*='Hỏi Tuyết Vương']"))
    
    browser.close()
