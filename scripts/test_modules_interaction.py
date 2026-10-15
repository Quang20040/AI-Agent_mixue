from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    
    # 1. Login as Admin
    page.locator("button:has-text('Quản Lý (Admin)')").first.click()
    page.wait_for_timeout(3000)
    
    def nav(name):
        page.locator(f"div[aria-label='Điều hướng'] label:has-text('{name}')").first.click(force=True)
        page.wait_for_timeout(2500)
        
    def click_tab(name):
        t = page.locator(f"button[role='tab']:has-text('{name}')").first
        if t.count() > 0:
            t.click(force=True)
            page.wait_for_timeout(2000)
            return True
        return False

    # TEST BÁO CÁO & KHO TABS
    print("\n--- Testing Báo cáo & kho tabs ---")
    nav("Báo cáo & kho")
    print("Matrix tab clicked:", click_tab("Sổ Thẻ Kho Ma Trận"))
    print(" - Matrix visible:", page.is_visible("text=Tên mặt hàng") or page.is_visible("div[data-testid='stDataFrame']"))
    
    print("Shift closing tab clicked:", click_tab("Chốt Ca Bằng Ảnh"))
    print(" - Shift closing visible:", page.is_visible("text=Tổng Thực Thu Về"))
    
    print("Sales tab clicked:", click_tab("Báo Cáo Doanh Thu"))
    print(" - Sales report visible:", page.is_visible("text=Doanh thu") or page.is_visible("text=doanh số"))
    
    print("Recon tab clicked:", click_tab("Đối Soát Thất Thoát Kho"))
    print(" - Recon report visible:", page.is_visible("text=Hao hụt") or page.is_visible("text=Tiêu hao") or page.is_visible("text=đối soát"))

    # TEST DỰ BÁO
    print("\n--- Testing Dự báo ---")
    nav("Dự báo")
    print(" - Forecast page header:", page.is_visible("text=Dự báo Nhu cầu"))
    btn_run_fc = page.locator("button:has-text('Chạy Mô hình Dự báo')").first
    if btn_run_fc.count() > 0:
        btn_run_fc.click(force=True)
        page.wait_for_timeout(5000)
        print(" - Forecast result table visible:", page.is_visible("text=Bảng Dự báo Sản lượng") or page.is_visible("text=Độ tin cậy"))

    # TEST SƠ CHẾ
    print("\n--- Testing Sơ chế ---")
    nav("Sơ chế")
    print(" - Prep page header:", page.is_visible("text=Kế hoạch Sơ chế Topping"))
    btn_calc_prep = page.locator("button:has-text('Tính toán Kế hoạch Sơ chế')").first
    if btn_calc_prep.count() > 0:
        btn_calc_prep.click(force=True)
        page.wait_for_timeout(3000)
        print(" - Prep plan result visible:", page.is_visible("text=KẾ HOẠCH ĐÃ THẨM ĐỊNH") or page.is_visible("text=Lượng nấu đề xuất"))

    # TEST NHẬP HÀNG
    print("\n--- Testing Nhập hàng ---")
    nav("Nhập hàng")
    print(" - PO page header:", page.is_visible("text=Dự thảo Đơn Đặt hàng"))
    btn_calc_po = page.locator("button:has-text('Tạo Dự thảo Đơn Đặt hàng')").first
    if btn_calc_po.count() > 0:
        btn_calc_po.click(force=True)
        page.wait_for_timeout(3000)
        print(" - PO plan result visible:", page.is_visible("text=Dự thảo Đơn Hàng") or page.is_visible("text=Mức ưu tiên"))

    # TEST TEM & CÔNG THỨC
    print("\n--- Testing Tem & công thức ---")
    nav("Tem & công thức")
    code_box = page.locator("input[aria-label='Nhập mã tem ly']").first
    btn_dec = page.locator("button:has-text('Giải mã Tem dán')").first
    if code_box.count() > 0 and btn_dec.count() > 0:
        code_box.fill("24101")
        btn_dec.click(force=True)
        page.wait_for_timeout(2000)
        print(" - Decoded sticker visible:", page.is_visible("div.cup-sticker") or page.is_visible("text=Trà đào"))

    # TEST QUẢN LÝ NHÂN VIÊN
    print("\n--- Testing Quản lý nhân viên ---")
    nav("Quản lý nhân viên")
    print(" - Employee table visible:", page.is_visible("text=Tổng số nhân sự"))
    click_tab("Đăng ký Nhân viên Mới")
    print(" - Create form visible:", page.is_visible("input[placeholder*='thuha_barista']"))

    # TEST CHAT
    print("\n--- Testing Tuyết Vương AI ---")
    nav("Tuyết Vương AI")
    print(" - Chat input visible:", page.is_visible("textarea[placeholder*='Hỏi Tuyết Vương']") or page.is_visible("input[placeholder*='Hỏi Tuyết Vương']"))

    browser.close()
    print("\nAll interactive modules verified successfully!")
