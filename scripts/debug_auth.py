from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    
    # Check AUTH-02: Empty submit
    print("Testing empty submit...")
    btn_sub = page.locator("button:has-text('Đăng nhập')").first
    print("Login btn text:", btn_sub.inner_text())
    btn_sub.click()
    page.wait_for_timeout(2000)
    # Check what messages appeared
    print("Alerts / errors on page:")
    for el in page.locator(".stAlert, [data-testid='stAlert']").all():
        print("Alert:", el.inner_text())
    
    # Check AUTH-05: quick login probation
    print("\nTesting probation login...")
    page.locator("button:has-text('NV Thử Việc')").first.click()
    page.wait_for_timeout(3000)
    print("Page text after probation click:\n", page.locator("body").inner_text()[:400])
    
    # Check cancel button
    btn_cancel = page.locator("button:has-text('Hủy bỏ & Đăng xuất')").first
    print("Cancel btn visible:", btn_cancel.is_visible())
    if btn_cancel.is_visible():
        btn_cancel.click()
        page.wait_for_timeout(2000)
        
    # Check quick login staff
    print("\nTesting staff login & logout...")
    page.locator("button:has-text('NV Chính Thức')").first.click()
    page.wait_for_timeout(3000)
    print("Radio options for staff:", page.locator("div[role='radiogroup']").inner_text())
    
    # Click logout
    btn_logout = page.locator("button:has-text('Đăng xuất khỏi Hệ thống')").first
    print("Logout btn visible:", btn_logout.is_visible())
    btn_logout.click()
    page.wait_for_timeout(3000)
    print("After logout, on login screen:", page.locator("button:has-text('Đăng nhập')").is_visible())
    
    browser.close()
