from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    
    # Login as Staff
    page.locator("button:has-text('NV Chính Thức')").first.click()
    page.wait_for_timeout(3000)
    
    # Try logout
    logout_btn = page.locator("button:has-text('Đăng xuất')").first
    print("Logout button exists:", logout_btn.count(), "visible:", logout_btn.is_visible())
    if logout_btn.is_visible():
        logout_btn.click()
        page.wait_for_timeout(2000)
        print("Logged out! Login visible:", page.locator("button:has-text('Đăng nhập')").first.is_visible())
    else:
        # Look for expand button
        for sel in ["[data-testid='stSidebarCollapseButton']", "[data-testid='collapsedControl']", "button[kind='header']"]:
            loc = page.locator(sel)
            print(f"Selector {sel}: count={loc.count()}")
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click()
                page.wait_for_timeout(1000)
                break
        print("After toggle, logout visible:", logout_btn.is_visible())
        if logout_btn.is_visible():
            logout_btn.click()
            page.wait_for_timeout(2000)
            print("Logged out! Login visible:", page.locator("button:has-text('Đăng nhập')").first.is_visible())
            
    browser.close()
