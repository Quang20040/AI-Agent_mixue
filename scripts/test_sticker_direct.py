from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator("button:has-text('Quản Lý (Admin)')").first.click()
    page.wait_for_timeout(3000)
    
    page.locator("div[aria-label='Điều hướng'] label:has-text('Tem & công thức')").first.click(force=True)
    page.wait_for_timeout(2000)
    
    code_box = page.locator("input[aria-label='Nhập mã tem ly']").first
    btn = page.locator("button:has-text('Giải mã Tem dán')").first
    print("code_box count:", code_box.count(), "btn count:", btn.count())
    code_box.fill('24101')
    btn.click(force=True)
    page.wait_for_timeout(2000)
    print('Sticker 24101 visible:', page.is_visible('div.cup-sticker'))
    
    code_box.fill('ABC')
    btn.click(force=True)
    page.wait_for_timeout(2000)
    print('Error visible for ABC:', page.is_visible('text=không hợp lệ') or page.is_visible('text=Mã tem dán ly phải có đúng 5 chữ số'))
    
    browser.close()
