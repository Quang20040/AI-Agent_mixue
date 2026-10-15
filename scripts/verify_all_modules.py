from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator("button:has-text('Quản Lý (Admin)')").first.click()
    page.wait_for_timeout(3000)
    
    # 1. Test clicking tabs in Báo cáo & kho
    print("Testing Báo cáo & kho tabs...")
    page.locator("div[aria-label='Điều hướng'] label:has-text('Báo cáo & kho')").first.click(force=True)
    page.wait_for_timeout(2000)
    
    # Click Matrix
    matrix_tab = page.locator("div[role='tab']:has-text('Sổ Thẻ Kho Ma Trận')").first
    matrix_tab.click(force=True)
    page.wait_for_timeout(2000)
    print(" - Sổ Thẻ Kho Ma Trận table visible:", page.is_visible("div[data-testid='stDataFrame']"))
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_stock_matrix.png")
    
    # Click Shift Closing
    shift_tab = page.locator("div[role='tab']:has-text('Chốt Ca Bằng Ảnh')").first
    shift_tab.click(force=True)
    page.wait_for_timeout(2000)
    print(" - Chốt Ca Bằng Ảnh KPI visible:", page.is_visible("text=Tổng Thực Thu Về"))
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_shift_closing.png")
    
    # Click Sales
    sales_tab = page.locator("div[role='tab']:has-text('Báo Cáo Doanh Thu')").first
    sales_tab.click(force=True)
    page.wait_for_timeout(2000)
    print(" - Báo Cáo Doanh Thu charts visible:", page.is_visible("text=Tổng doanh thu 30 ngày") or page.is_visible("div[data-testid='stDataFrame']"))
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_sales_report.png")
    
    # Click Loss Recon
    recon_tab = page.locator("div[role='tab']:has-text('Đối Soát Thất Thoát Kho')").first
    recon_tab.click(force=True)
    page.wait_for_timeout(2000)
    print(" - Đối Soát Thất Thoát Kho visible:", page.is_visible("div[data-testid='stDataFrame']"))
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_reconciliation.png")
    
    # 2. Test Forecasting
    print("\nTesting Dự báo...")
    page.locator("div[aria-label='Điều hướng'] label:has-text('Dự báo')").first.click(force=True)
    page.wait_for_timeout(2000)
    btn_fc = page.locator("button:has-text('Chạy Mô hình Dự báo')").first
    btn_fc.click(force=True)
    page.wait_for_timeout(6000)
    print(" - Bảng Dự báo visible:", page.is_visible("text=Bảng Dự báo Sản lượng Menu"))
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_forecast.png")
    
    # 3. Test Prep
    print("\nTesting Sơ chế...")
    page.locator("div[aria-label='Điều hướng'] label:has-text('Sơ chế')").first.click(force=True)
    page.wait_for_timeout(2000)
    btn_prep = page.locator("button:has-text('Tính toán Kế hoạch Sơ chế')").first
    btn_prep.click(force=True)
    page.wait_for_timeout(4000)
    print(" - Kế hoạch sơ chế thẩm định visible:", page.is_visible("text=KẾ HOẠCH ĐÃ THẨM ĐỊNH HỢP LỆ"))
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_prep_plan.png")
    
    # 4. Test PO
    print("\nTesting Nhập hàng...")
    page.locator("div[aria-label='Điều hướng'] label:has-text('Nhập hàng')").first.click(force=True)
    page.wait_for_timeout(2000)
    btn_po = page.locator("button:has-text('Tạo Dự thảo Đơn Đặt hàng')").first
    btn_po.click(force=True)
    page.wait_for_timeout(4000)
    print(" - Dự thảo đơn hàng visible:", page.is_visible("text=Dự thảo Đơn Hàng"))
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_po_draft.png")
    
    # 5. Test Staff Management tabs
    print("\nTesting Quản lý nhân viên tabs...")
    page.locator("div[aria-label='Điều hướng'] label:has-text('Quản lý nhân viên')").first.click(force=True)
    page.wait_for_timeout(2000)
    create_tab = page.locator("div[role='tab']:has-text('Đăng ký Nhân viên Mới')").first
    create_tab.click(force=True)
    page.wait_for_timeout(2000)
    print(" - Form Đăng ký NV Mới visible:", page.is_visible("input[placeholder*='thuha_barista']"))
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_create_emp_tab.png")
    
    reset_tab = page.locator("div[role='tab']:has-text('Reset Mật khẩu')").first
    reset_tab.click(force=True)
    page.wait_for_timeout(2000)
    print(" - Reset Mật khẩu container visible:", page.is_visible("text=Reset Mật khẩu Nhân viên về Mặc định"))
    page.screenshot(path="blackbox-qa/evidence/screenshots/verified_reset_pw_tab.png")

    browser.close()
    print("\nAll core verification steps completed!")
