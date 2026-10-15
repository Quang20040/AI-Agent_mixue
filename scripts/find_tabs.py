from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator("button:has-text('Quản Lý (Admin)')").first.click()
    page.wait_for_timeout(3000)
    page.locator("div[aria-label='Điều hướng'] label:has-text('Báo cáo & kho')").first.click(force=True)
    page.wait_for_timeout(3000)
    
    # inspect all elements with role='tab' or tabs
    tabs = page.locator('[role="tab"]').all()
    print('Found role=tab count:', len(tabs))
    for t in tabs:
        print('Tab tag:', t.evaluate('el => el.tagName'), 'text:', repr(t.inner_text()), 'data-baseweb:', t.get_attribute('data-baseweb'))
        
    # Also check if there are buttons with tab text
    print("\nAll buttons on page with 'Kho' or 'Báo Cáo':")
    for b in page.locator("button").all():
        txt = b.inner_text().strip()
        if any(w in txt for w in ["Kho", "Chốt Ca", "Doanh Thu", "Thất Thoát"]):
            print(" - Btn:", repr(txt))
            
    browser.close()
