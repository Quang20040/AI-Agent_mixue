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
    
    print('Before click forecast body text:\n', page.locator('[data-testid="stMain"]').inner_text()[:400])
    
    btn = page.locator("button:has-text('Chạy Mô hình Dự báo')").first
    print('Button text:', btn.inner_text(), 'visible:', btn.is_visible())
    btn.click(force=True)
    print('Clicked! Waiting for spinner or result...')
    page.wait_for_timeout(6000)
    
    print('After click forecast body text:\n', page.locator('[data-testid="stMain"]').inner_text()[:800])
    
    alerts = page.locator('[data-testid="stAlert"]').all()
    print('Alerts count:', len(alerts))
    for a in alerts:
        print('Alert:', a.inner_text())
        
    browser.close()
