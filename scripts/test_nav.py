from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    
    # Login as admin
    page.locator("button:has-text('Quản Lý (Admin)')").first.click()
    page.wait_for_timeout(3000)
    
    print("Logged in as admin. Current text:")
    # Print radio buttons
    radio_labels = page.locator("div[aria-label='Điều hướng'] label").all()
    print("Found navigation labels:", len(radio_labels))
    for lbl in radio_labels:
        print(" - Label:", repr(lbl.inner_text()))
        
    # Try clicking 'Báo cáo & kho'
    print("\nAttempting to click 'Báo cáo & kho'...")
    target = page.locator("div[aria-label='Điều hướng'] label:has-text('Báo cáo & kho')").first
    print("Target count:", target.count(), "visible:", target.is_visible())
    target.click(force=True)
    page.wait_for_timeout(3000)
    
    print("After click, page contains 'Sổ Thẻ Kho Ma Trận':", page.is_visible("text=Sổ Thẻ Kho Ma Trận"))
    print("After click, page contains 'Duyệt Lệnh Kho':", page.is_visible("text=Duyệt Lệnh Kho"))
    print("After click, page contains 'Quản Lý Chốt Ca Bằng Ảnh':", page.is_visible("text=Chốt Ca Bằng Ảnh"))
    
    # Try clicking 'Dự báo'
    print("\nAttempting to click 'Dự báo'...")
    target_fc = page.locator("div[aria-label='Điều hướng'] label:has-text('Dự báo')").first
    target_fc.click(force=True)
    page.wait_for_timeout(3000)
    print("After click, page contains 'Kiểm chứng Backtest':", page.is_visible("text=Kiểm chứng Backtest"))
    
    browser.close()
