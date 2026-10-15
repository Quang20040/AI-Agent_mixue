from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    
    # Click quick login staff
    page.locator("button:has-text('NV Chính Thức')").first.click()
    page.wait_for_timeout(3000)
    
    sidebar = page.locator('[data-testid="stSidebar"]')
    print("Sidebar inner text:\n", sidebar.inner_text()[:400])
    
    logout_btns = sidebar.locator("button").all()
    print("Buttons in sidebar:", len(logout_btns))
    for b in logout_btns:
        print("Sidebar button:", repr(b.inner_text()), "is_visible:", b.is_visible())
    
    browser.close()
