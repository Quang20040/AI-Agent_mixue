from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.on("console", lambda m: print(f"BROWSER CONSOLE [{m.type}]: {m.text}"))
    page.on("pageerror", lambda e: print(f"PAGE ERROR: {e}"))
    
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator("button:has-text('Quản Lý (Admin)')").first.click()
    page.wait_for_timeout(3000)
    page.locator("div[aria-label='Điều hướng'] label:has-text('Dự báo')").first.click(force=True)
    page.wait_for_timeout(2000)
    
    btn = page.locator("button:has-text('Chạy Mô hình Dự báo')").first
    btn.click()
    print("Clicked button! Waiting for up to 20 seconds...")
    for i in range(20):
        page.wait_for_timeout(1000)
        has_table = page.is_visible("text=Bảng Dự báo Sản lượng")
        if has_table:
            print(f"Table appeared at {i+1} seconds!")
            break
        is_spinning = page.is_visible("text=Đang tính toán")
        print(f"Second {i+1}: is_spinning={is_spinning}")
        
    page.screenshot(path="blackbox-qa/evidence/screenshots/debug_forecast_20s.png")
    browser.close()
