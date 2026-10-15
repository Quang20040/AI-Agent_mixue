from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator("button:has-text('Quản Lý (Admin)')").first.click()
    page.wait_for_timeout(3000)
    page.locator("div[aria-label='Điều hướng'] label:has-text('Dự báo')").first.click(force=True)
    page.wait_for_timeout(2000)
    
    btn = page.locator("button:has-text('Chạy Mô hình Dự báo')").first
    btn.click(force=True)
    print("Clicked button! Waiting for spinner to disappear...")
    page.wait_for_selector("text=Đang tính toán", state="detached", timeout=30000)
    page.wait_for_timeout(2000)
    
    print("Spinner detached! Result visible:")
    print("Success text:", page.is_visible("text=Đã lập dự báo thành công"))
    print("Table header visible:", page.is_visible("text=Bảng Dự báo Sản lượng Menu"))
    print("Dataframe visible:", page.locator("div[data-testid='stDataFrame']").count())
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_forecast_complete.png")
    
    browser.close()
