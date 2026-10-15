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
    
    # Locate the button inside the form / column
    btn = page.locator("button:has-text('Chạy Mô hình Dự báo')").first
    print("Found button:", btn.inner_text())
    
    # Click with mouse
    btn.scroll_into_view_if_needed()
    btn.click()
    print("Clicked button! Waiting for 8 seconds...")
    page.wait_for_timeout(8000)
    
    # Check all h4 elements
    h4s = page.locator("h4").all()
    print("All H4 elements on page:")
    for h in h4s:
        print(" - H4:", h.inner_text())
        
    page.screenshot(path="blackbox-qa/evidence/screenshots/debug_forecast_h4.png")
    browser.close()
