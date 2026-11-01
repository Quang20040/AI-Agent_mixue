# -*- coding: utf-8 -*-
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def add_final_mixue_data():
    master_path = r"c:\Users\Admin\OneDrive\Desktop\DATN\AI-Agent_mixue\Bang_Du_Lieu_Mixue.xlsx"
    wb = openpyxl.load_workbook(master_path)

    # Styles
    font_family = "Segoe UI"
    title_font = Font(name=font_family, size=14, bold=True, color="FFFFFF")
    section_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
    tbl_header_font = Font(name=font_family, size=10, bold=True, color="FFFFFF")
    bold_font = Font(name=font_family, size=10, bold=True, color="000000")
    regular_font = Font(name=font_family, size=10, color="000000")
    italic_font = Font(name=font_family, size=9, italic=True, color="4B5563")
    code_font = Font(name="Consolas", size=10, bold=True, color="9C0006")

    mixue_red = PatternFill(start_color="D92525", end_color="D92525", fill_type="solid")
    dark_red = PatternFill(start_color="A81818", end_color="A81818", fill_type="solid")
    header_red = PatternFill(start_color="E04343", end_color="E04343", fill_type="solid")
    blue_header = PatternFill(start_color="1E88E5", end_color="1E88E5", fill_type="solid")
    blue_light = PatternFill(start_color="29B6F6", end_color="29B6F6", fill_type="solid")
    light_pink = PatternFill(start_color="FDEDEC", end_color="FDEDEC", fill_type="solid")
    light_gray = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFF9E6", end_color="FFF9E6", fill_type="solid")
    orange_fill = PatternFill(start_color="FFEAD2", end_color="FFEAD2", fill_type="solid")
    sub_title_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")

    thin_side = Side(style='thin', color='C4C4C4')
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    def set_sheet_defaults(ws):
        ws.views.sheetView[0].showGridLines = True

    # =========================================================================
    # 1. UPDATE Tong_Hop_San_Sau (Add formulas 8 and 9)
    # =========================================================================
    if "Tong_Hop_San_Sau" in wb.sheetnames:
        ws_sum = wb["Tong_Hop_San_Sau"]
        new_summary_rows = [
            ("⑧", "Cà Phê Cô Đặc Sân Sau", "1 phần", "Cà phê hòa tan: 50g", "Nước nóng 95°C: 300g", "Đá sạch: 300g", "Khuấy tan 1 phút + tan đá", "6 cốc"),
            ("⑧", "Cà Phê Cô Đặc Sân Sau", "2 phần", "Cà phê hòa tan: 100g", "Nước nóng 95°C: 600g", "Đá sạch: 600g", "Khuấy tan 1 phút + tan đá", "13 cốc"),
            ("⑨", "Trân Châu Nguyên Vị Sân Sau", "0.5 phần", "Trân châu: 500g", "Nước nóng 95°C: 3000ml", "Đường mật: 250g", "Nấu 35p + Ủ 30p + Ủ đường 10p", "11 cốc"),
            ("⑨", "Trân Châu Nguyên Vị Sân Sau", "1 phần", "Trân châu: 1000g", "Nước nóng 95°C: 4000ml", "Đường mật: 500g", "Nấu 35p + Ủ 30p + Ủ đường 10p", "22 cốc")
        ]
        curr_r = ws_sum.max_row + 1
        for row in new_summary_rows:
            for c_i, val in enumerate(row, 1):
                cell = ws_sum.cell(row=curr_r, column=c_i, value=val)
                cell.font = bold_font if c_i in (1, 2) else regular_font
                cell.border = cell_border
                if c_i in (1, 3, 8):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                if curr_r % 2 == 1:
                    cell.fill = light_gray
            ws_sum.row_dimensions[curr_r].height = 22
            curr_r += 1

    # =========================================================================
    # 2. CREATE SHEET: Huong_Dan_Doc_Tem_Mat_Ma
    # =========================================================================
    if "Huong_Dan_Doc_Tem_Mat_Ma" in wb.sheetnames:
        wb.remove(wb["Huong_Dan_Doc_Tem_Mat_Ma"])
    ws_tem = wb.create_sheet(title="Huong_Dan_Doc_Tem_Mat_Ma", index=1)
    set_sheet_defaults(ws_tem)

    ws_tem.merge_cells("A1:G1")
    ws_tem["A1"] = "HƯỚNG DẪN ĐỌC TEM NHÃN & GIẢI MÃ MẬT MÃ SẢN PHẨM MIXUE (06.2025)"
    ws_tem["A1"].font = title_font
    ws_tem["A1"].fill = mixue_red
    ws_tem["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_tem.row_dimensions[1].height = 38

    # Section 1: Cấu trúc tem nhãn 11 thành phần
    ws_tem.merge_cells("A3:G3")
    ws_tem["A3"] = "I. Ý NGHĨA 11 THÀNH PHẦN TRÊN TEM IN DÁN CỐC SẢN PHẨM"
    ws_tem["A3"].font = section_font
    ws_tem["A3"].fill = blue_header
    ws_tem["A3"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws_tem.row_dimensions[3].height = 26

    headers_tem = ["STT", "Thành phần trên tem", "Vị trí thể hiện", "Nội dung & Mục đích thao tác", "Quy định quầy bar", "Lưu ý chống sai sót", "Ví dụ thực tế"]
    for c_idx, h in enumerate(headers_tem, 1):
        cell = ws_tem.cell(row=4, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = blue_light
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_tem.row_dimensions[4].height = 25

    tem_parts = [
        (1, "Loại đơn hàng", "Góc trên bên trái tem", "Phân biệt 'Bán tại chỗ / Ăn tại chỗ' và 'Đơn ship app'", "Lấy cốc đúng luồng phục vụ", "Đơn mang về/ship cần đóng nắp/dán miệng cẩn thận", "Bán tại chỗ / Ăn tại chỗ"),
        (2, "Tên sản phẩm & loại cốc", "Dưới loại đơn hàng", "Xác định chính xác tên món và loại dáng cốc cần lấy", "Lấy đúng cốc 500ml, 700ml hoặc cốc U", "Lấy nhầm dáng cốc dẫn đến sai định lượng cốt/đá", "Trà đào BigSize (Cốc 700)"),
        (3, "Thuộc tính sản phẩm", "Bên dưới tên sản phẩm", "Ghi chú lượng đá (đúng đá/ít đá/ấm) và lượng đường (100%/70%/50%/30%/không đường)", "Pha chế chuẩn xác theo yêu cầu khách chọn", "Nhìn kỹ mức đường đá trước khi rót siro/đá", "Đúng đá, 70% đường"),
        (4, "Thêm topping", "Dưới thuộc tính sản phẩm", "Hiển thị các loại topping khách mua thêm trong dấu ngoặc đơn", "Múc đúng loại và số lượng topping thêm", "Tuyệt đối không bỏ sót topping khách trả thêm tiền", "(Thêm Trân châu trắng 1)"),
        (5, "Thời gian đặt hàng", "Góc dưới bên trái tem", "Thời điểm khách thanh toán/đơn hàng đẩy về máy in", "Kiểm soát thời gian phục vụ món cho khách", "Đảm bảo xuất đồ trong vòng 3 phút", "19:10:25"),
        (6, "Mã cửa hàng", "Chân tem nhãn", "Mã số định danh của cửa hàng trong hệ thống Mixue", "Quản lý dữ liệu hệ thống", "Dùng khi đối soát hệ thống", "VN0102001"),
        (7, "Số điện thoại cửa hàng", "Chân tem nhãn", "Số hotline liên hệ của cửa hàng", "Để khách hàng liên hệ khi cần hỗ trợ đơn hàng", "In rõ ràng, không bị mất nét mực", "098x xxx xxx"),
        (8, "Mật mã sản phẩm", "Chính giữa tem nhãn", "Chuỗi ký hiệu mã hóa rút gọn toàn bộ công thức pha chế của món", "Nhìn mật mã để thao tác rót nguyên liệu chuẩn xác", "Giúp pha chế thần tốc không cần mở sách công thức", "/40/ T.đào3, Đ.vàng4/ H100/"),
        (9, "Giá sản phẩm", "Bên phải tem nhãn", "Đơn giá tiền của sản phẩm", "Thu ngân & kiểm tra tính tiền", "Đối chiếu với hóa đơn thanh toán", "25,000 đ"),
        (10, "Thứ tự món / Tổng món", "Góc trên bên phải tem", "Số thứ tự của ly trong toàn bộ đơn hàng (Ví dụ: 1/4 = ly thứ 1 trên tổng 4 ly)", "Chọn túi mang về phù hợp (túi đơn, túi đôi, túi 4)", "Đủ số lượng ly mới bàn giao cho khách/shipper", "#101 01/04"),
        (11, "Số hóa đơn / Số thứ tự", "Đỉnh tem nhãn", "Số thứ tự đơn hàng để gọi loa/gọi khách nhận đồ", "Gọi khách theo đúng thứ tự số hóa đơn", "Tránh giao nhầm đồ uống giữa các khách hàng", "Hóa đơn #101")
    ]

    r_idx = 5
    for item in tem_parts:
        for c_idx, val in enumerate(item, 1):
            cell = ws_tem.cell(row=r_idx, column=c_idx, value=val)
            cell.font = bold_font if c_idx in (2, 8) else regular_font
            cell.border = cell_border
            if c_idx in (1, 3, 5, 7):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if r_idx % 2 == 1:
                cell.fill = light_gray
        ws_tem.row_dimensions[r_idx].height = 24
        r_idx += 1

    # Section 2: Nguyên tắc giải mã mật mã sản phẩm
    r_idx += 1
    ws_tem.merge_cells(f"A{r_idx}:G{r_idx}")
    ws_tem[f"A{r_idx}"] = "II. NGUYÊN TẮC CẤU TRÚC VÀ GIẢI MÃ MẬT MÃ SẢN PHẨM"
    ws_tem[f"A{r_idx}"].font = section_font
    ws_tem[f"A{r_idx}"].fill = mixue_red
    ws_tem[f"A{r_idx}"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws_tem.row_dimensions[r_idx].height = 26
    r_idx += 1

    headers_rules = ["Nhóm sản phẩm", "Cấu trúc định dạng mã", "Quy tắc ký hiệu cụ thể", "Ý nghĩa chi tiết các thành phần", "Ví dụ mẫu trên tem", "Giải mã thao tác thực tế quầy Bar", "Ghi chú bắt buộc"]
    for c_idx, h in enumerate(headers_rules, 1):
        cell = ws_tem.cell(row=r_idx, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = header_red
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_tem.row_dimensions[r_idx].height = 25
    r_idx += 1

    rules_data = [
        (
            "1. Dấu phân tách nhóm",
            "Dấu gạch chéo '/'",
            "Dấu '/' chia công thức thành 3 hoặc 4 khoang độc lập: /Đường/ Liệu (Topping/Mứt)/ Trà (hoặc Sữa/Cốt)/",
            "Giúp mắt nhân viên quét nhanh thứ tự rót nguyên liệu từ trái sang phải mà không bị lẫn lộn giữa đường, topping và trà.",
            "/Đường/ Liệu/ Trà/",
            "Thao tác theo thứ tự: Rót nhóm Đường -> Múc nhóm Topping/Mứt -> Rót nhóm Trà/Cốt nước.",
            "Bắt buộc rót đúng tuần tự từ trái qua phải."
        ),
        (
            "2. Nhóm Đường & Chất tạo ngọt",
            "/ [Số] hoặc [Chữ+Số] /",
            "• Nếu CHỈ GHI SỐ: Mặc định là Đường Mật (ví dụ /40/ = 40ml đường mật)\n• 'Q' = Đường Quả (ví dụ Q20)\n• 'Đ' = Đường Đen (Đ10, Đ30)\n• 'S' = Sốt Socola (S10, S40)\n• 'HD' = Syrup Hạt Dẻ Bơ (HD40)",
            "Số đứng sau chữ cái thể hiện số ml hoặc gram đường/syrup cần bơm vào cốc.",
            "/40, Q20/\nhoặc /Đ30/",
            "• Bơm 40ml đường mật + 20ml đường quả vào cốc.\n• Đ30: Bơm 30ml đường đen và quét đều quanh thành cốc.",
            "Lượng đường thực tế sẽ tự động giảm nếu khách chọn mức đường thấp hoặc thêm topping."
        ),
        (
            "3. Nhóm Trái cây tươi",
            "/ [C + Số] /",
            "Khối lượng trái cây tươi sẽ được đặt trước phần /Đường/.\n• Chanh tươi cắt lát ký hiệu là 'C' (ví dụ /C40/).",
            "C40 thể hiện 40g chanh tươi cắt lát.",
            "/C40/ Q55 / - / - /",
            "Cân 40g chanh lát bỏ vào cốc, giã lấy nước cốt (riêng Trà chanh lô hội KHÔNG GIÃ), sau đó thêm 55ml đường quả.",
            "Ký hiệu '/ - /' biểu thị nhóm đó không có nguyên liệu, trên tem sẽ để trống."
        ),
        (
            "4. Nhóm Kem tươi",
            "/ (Số trong ngoặc) /",
            "Kem tươi được ký hiệu bằng số đặt trong dấu ngoặc đơn '(xxx)'.\n• (180) = 180g kem\n• (120) = 120g kem\n• (90) = 90g kem",
            "Số trong ngoặc là khối lượng gram kem tươi cần chiết từ máy làm kem.",
            "/(180)/ Kiwi1, L.hội2/\nhoặc /(90)/",
            "Chiết đúng 180g kem tươi vào cốc chữ U, sau đó thêm 1 thìa mứt kiwi và 2 thìa lô hội lên trên bề mặt.",
            "Cần cân thực tế để đảm bảo trọng lượng kem, số vòng xoay chỉ mang tính tham khảo."
        ),
        (
            "5. Nhóm Liệu (Topping & Mứt)",
            "/ [Tên viết tắt + Số] /",
            "Chữ cái viết tắt tên nguyên liệu + Số thể hiện số thìa nhựa hoặc số muôi thủng múc.\n• T.dừa: Thạch dừa\n• T.đào: Thạch đào\n• TC.đen: Trân châu đen\n• D.tây: Mứt dâu\n• Đ.vàng: Mứt đào vàng",
            "Ví dụ:\n• T.dừa 2: 2 thìa thạch dừa\n• T.đào 1: 1 muôi thạch đào\n• Kiwi 3: 3 thìa mứt kiwi",
            "/T.dừa2, T.đào1, Kiwi3/",
            "Lấy muôi/thìa tương ứng múc đúng định lượng: 2 thìa gạt bằng thạch dừa + 1 muôi gạt bằng thạch đào + 3 thìa mứt kiwi cho vào cốc.",
            "Thìa nhựa dùng cho thạch dừa, mứt, trân châu trắng; Muôi thủng dùng cho thạch đào, thạch đen, trân châu đen."
        ),
        (
            "6. Nhóm Trà & Bán thành phẩm",
            "/ [Mã cốt + Số] /",
            "• 'X' = Trà xanh sân sau\n• 'H' = Hồng trà sân sau\n• 'TS' = Trà sữa pha sẵn\n• 'S.đặc' = Sữa đặc\n• 'Latte' = Cốt cà phê latte\n• 'M.cha' = Cốt matcha\nSố sau chữ: Thể hiện số ml hoặc vạch mức bình lắc.",
            "Ví dụ:\n• X120 = 120ml trà xanh\n• H100 = 100ml hồng trà\n• X0.8 / TS0.8 = Rót trà/trà sữa đến vạch 0.8 bình lắc",
            "/X120/\nhoặc /TS0.8/\nhoặc /S.đặc100/",
            "• Đong 120ml cốt trà xanh rót vào ly.\n• Rót trà sữa lạnh từ bình đong trực tiếp đến vạch 0.8 của bình lắc.",
            "Đảm bảo nhiệt độ trà và trà sữa đạt chuẩn lạnh sân sau trước khi sử dụng."
        )
    ]

    for item in rules_data:
        for c_idx, val in enumerate(item, 1):
            cell = ws_tem.cell(row=r_idx, column=c_idx, value=val)
            cell.font = bold_font if c_idx == 1 else regular_font
            cell.border = cell_border
            if c_idx in (1, 2):
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            elif c_idx == 5:
                cell.font = code_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if r_idx % 2 == 1:
                cell.fill = light_gray
        ws_tem.row_dimensions[r_idx].height = 42
        r_idx += 1

    ws_tem.column_dimensions['A'].width = 18
    ws_tem.column_dimensions['B'].width = 24
    ws_tem.column_dimensions['C'].width = 34
    ws_tem.column_dimensions['D'].width = 38
    ws_tem.column_dimensions['E'].width = 26
    ws_tem.column_dimensions['F'].width = 44
    ws_tem.column_dimensions['G'].width = 34

    # =========================================================================
    # 3. CREATE SHEET: 8_Ca_Phe_Co_Dac
    # =========================================================================
    if "8_Ca_Phe_Co_Dac" in wb.sheetnames:
        wb.remove(wb["8_Ca_Phe_Co_Dac"])
    ws_cf_sau = wb.create_sheet(title="8_Ca_Phe_Co_Dac")
    set_sheet_defaults(ws_cf_sau)

    ws_cf_sau.merge_cells("A1:F1")
    ws_cf_sau["A1"] = "CÔNG THỨC CÀ PHÊ CÔ ĐẶC SÂN SAU ⑧ (02.07.2025)"
    ws_cf_sau["A1"].font = title_font
    ws_cf_sau["A1"].fill = mixue_red
    ws_cf_sau["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_cf_sau.row_dimensions[1].height = 38

    ws_cf_sau.merge_cells("A3:F3")
    ws_cf_sau["A3"] = "1. QUY CHUẨN CÂN ĐO ĐONG ĐẾM"
    ws_cf_sau["A3"].font = bold_font
    ws_cf_sau["A3"].fill = light_pink
    ws_cf_sau["A3"].border = cell_border
    
    ws_cf_sau.merge_cells("A4:F4")
    ws_cf_sau["A4"] = "• Tiêu chuẩn cân đồ: ≤ 500g được sai số ± 5g  |  > 500g được sai số ± 10g  |  ≥ 3000g được sai số ± 20g"
    ws_cf_sau["A4"].font = regular_font
    ws_cf_sau["A4"].border = cell_border

    ws_cf_sau.merge_cells("A5:F5")
    ws_cf_sau["A5"] = "• Cân nặng và đo lường: Ghi chú bằng gam (g) thì dùng CÂN, ghi chú bằng mililit (ml) thì dùng BÌNH ĐONG."
    ws_cf_sau["A5"].font = regular_font
    ws_cf_sau["A5"].border = cell_border

    ws_cf_sau.cell(row=7, column=1, value="Dụng cụ").font = bold_font
    ws_cf_sau.cell(row=7, column=1).fill = sub_title_fill
    ws_cf_sau.cell(row=7, column=1).border = cell_border
    ws_cf_sau.merge_cells("B7:F7")
    ws_cf_sau["B7"] = "Cân điện tử, bình đong 2500ml, thìa khuấy"
    ws_cf_sau["B7"].font = regular_font
    ws_cf_sau["B7"].border = cell_border

    ws_cf_sau.cell(row=8, column=1, value="Nguyên liệu").font = bold_font
    ws_cf_sau.cell(row=8, column=1).fill = sub_title_fill
    ws_cf_sau.cell(row=8, column=1).border = cell_border
    ws_cf_sau.merge_cells("B8:F8")
    ws_cf_sau["B8"] = "Nước nóng 95°C, cà phê hòa tan, đá viên"
    ws_cf_sau["B8"].font = regular_font
    ws_cf_sau["B8"].border = cell_border

    # Ratio Table
    ws_cf_sau.merge_cells("A10:F10")
    ws_cf_sau["A10"] = "2. TIÊU CHUẨN KHỐI LƯỢNG ĐỊNH LƯỢNG CÀ PHÊ CÔ ĐẶC"
    ws_cf_sau["A10"].font = tbl_header_font
    ws_cf_sau["A10"].fill = header_red
    ws_cf_sau["A10"].alignment = Alignment(horizontal="center", vertical="center")
    ws_cf_sau.row_dimensions[10].height = 25

    headers_cf_ratio = ["Số phần", "Nước nóng 95°C (g)", "Cà phê hòa tan (g)", "Đá (g)", "Thời gian khuấy", "Số cốc ước tính"]
    for c_idx, h in enumerate(headers_cf_ratio, 1):
        cell = ws_cf_sau.cell(row=11, column=c_idx, value=h)
        cell.font = bold_font
        cell.fill = light_pink
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_cf_sau.row_dimensions[11].height = 25

    cf_ratios = [
        ("1 phần", 300, 50, 300, "1 phút", "6 cốc"),
        ("2 phần", 600, 100, 600, "1 phút", "13 cốc")
    ]
    for r_i, r_data in enumerate(cf_ratios, 12):
        for c_i, val in enumerate(r_data, 1):
            cell = ws_cf_sau.cell(row=r_i, column=c_i, value=val)
            cell.font = regular_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = cell_border
        ws_cf_sau.row_dimensions[r_i].height = 22

    # Steps Table
    ws_cf_sau.merge_cells("A15:F15")
    ws_cf_sau["A15"] = "3. CÁC BƯỚC THAO TÁC PHA CHẾ (VÍ DỤ 1 PHẦN)"
    ws_cf_sau["A15"].font = tbl_header_font
    ws_cf_sau["A15"].fill = header_red
    ws_cf_sau["A15"].alignment = Alignment(horizontal="center", vertical="center")
    ws_cf_sau.row_dimensions[15].height = 25

    headers_cf_steps = ["Bước", "Tên bước thao tác", "Nội dung chi tiết thao tác", "Dụng cụ / Thiết bị", "Thời gian / Lưu ý", "Hạn dùng & Bảo quản"]
    for c_idx, h in enumerate(headers_cf_steps, 1):
        cell = ws_cf_sau.cell(row=16, column=c_idx, value=h)
        cell.font = bold_font
        cell.fill = light_pink
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_cf_sau.row_dimensions[16].height = 25

    steps_cf = [
        ("Bước 1", "Cân nước nóng 95°C", "Cân đúng 300g nước nóng (từ máy nước nóng 95°C) vào bình đong 2500ml.", "Cân điện tử, bình đong 2500ml", "Nhiệt độ chuẩn 95°C", "-"),
        ("Bước 2", "Thêm bột cà phê", "Thêm đúng 50g bột cà phê hòa tan vào bình đong có sẵn nước nóng.", "Cân điện tử, bột cà phê hòa tan", "-", "Đổ nhẹ tay tránh bay bụi cà phê."),
        ("Bước 3", "Khuấy tan cà phê", "Khuấy đều liên tục bằng thìa khuấy cho đến khi bột cà phê hoàn toàn tan hết (khoảng 1 phút).", "Thìa khuấy dài", "Khuấy đều 1 phút", "Khuấy sát đáy tránh vón cục."),
        ("Bước 4", "Thêm đá sốc nhiệt", "Thêm đúng 300g đá sạch vào bình đong.", "Cân điện tử, xẻng xúc đá", "-", "-"),
        ("Bước 5", "Khuấy tan đá", "Khuấy đều liên tục bằng thìa khuấy cho đến khi đá tan hoàn toàn.", "Thìa khuấy dài", "Khuấy tan hết đá", "Giúp cà phê nguội nhanh và thơm đậm."),
        ("Bước 6", "Bảo quản & Dán tem", "Đóng kín nắp bình đong, in và dán tem hạn sử dụng, bảo quản trong tủ lạnh chờ dùng.", "Nắp bình đong, máy in tem, tủ lạnh", "Trong ngày", "• Bình đong đậy nắp bảo quản lạnh: ĐỔ BỎ CUỐI NGÀY")
    ]
    for r_i, step in enumerate(steps_cf, 17):
        for c_i, val in enumerate(step, 1):
            cell = ws_cf_sau.cell(row=r_i, column=c_i, value=val)
            cell.font = regular_font
            if c_i in (1, 4, 5):
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            cell.border = cell_border
        ws_cf_sau.row_dimensions[r_i].height = 36

    ws_cf_sau.merge_cells("A24:F24")
    ws_cf_sau["A24"] = "4. LƯU Ý QUAN TRỌNG KHI PHA CHẾ CÀ PHÊ CÔ ĐẶC"
    ws_cf_sau["A24"].font = bold_font
    ws_cf_sau["A24"].fill = yellow_fill
    ws_cf_sau["A24"].border = cell_border
    ws_cf_sau.row_dimensions[24].height = 24

    ws_cf_sau.merge_cells("A25:F25")
    ws_cf_sau["A25"] = "1. CẦN THAO TÁC THEO ĐÚNG THỨ TỰ TRONG BẢNG CÔNG THỨC: Nước nóng 95°C -> Bột cà phê -> Khuấy tan -> Đá -> Khuấy tan đá. Tránh đổ bột trước đổ nước sau làm bột cà phê vón cục dưới đáy bình dẫn đến việc khuấy không tan đều."
    ws_cf_sau["A25"].font = regular_font
    ws_cf_sau["A25"].border = cell_border
    ws_cf_sau.row_dimensions[25].height = 28

    ws_cf_sau.column_dimensions['A'].width = 12
    ws_cf_sau.column_dimensions['B'].width = 24
    ws_cf_sau.column_dimensions['C'].width = 46
    ws_cf_sau.column_dimensions['D'].width = 28
    ws_cf_sau.column_dimensions['E'].width = 24
    ws_cf_sau.column_dimensions['F'].width = 44

    # =========================================================================
    # 4. CREATE SHEET: 9_Tran_Chau_Nguyen_Vi
    # =========================================================================
    if "9_Tran_Chau_Nguyen_Vi" in wb.sheetnames:
        wb.remove(wb["9_Tran_Chau_Nguyen_Vi"])
    ws_tc_sau = wb.create_sheet(title="9_Tran_Chau_Nguyen_Vi")
    set_sheet_defaults(ws_tc_sau)

    ws_tc_sau.merge_cells("A1:G1")
    ws_tc_sau["A1"] = "CÔNG THỨC TRÂN CHÂU NGUYÊN VỊ SÂN SAU (NỒI TRÂN CHÂU) ⑨ (17.07.2025)"
    ws_tc_sau["A1"].font = title_font
    ws_tc_sau["A1"].fill = mixue_red
    ws_tc_sau["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_tc_sau.row_dimensions[1].height = 38

    ws_tc_sau.merge_cells("A3:G3")
    ws_tc_sau["A3"] = "1. QUY CHUẨN CÂN ĐO ĐONG ĐẾM & THIẾT BỊ"
    ws_tc_sau["A3"].font = bold_font
    ws_tc_sau["A3"].fill = light_pink
    ws_tc_sau["A3"].border = cell_border

    ws_tc_sau.merge_cells("A4:G4")
    ws_tc_sau["A4"] = "• Tiêu chuẩn cân đồ: ≤ 500g sai số ±5g | > 500g sai số ±10g | ≥ 3000g sai số ±20g. Đơn vị gam (g) dùng cân, mililit (ml) dùng bình đong."
    ws_tc_sau["A4"].font = regular_font
    ws_tc_sau["A4"].border = cell_border

    ws_tc_sau.cell(row=6, column=1, value="Dụng cụ").font = bold_font
    ws_tc_sau.cell(row=6, column=1).fill = sub_title_fill
    ws_tc_sau.cell(row=6, column=1).border = cell_border
    ws_tc_sau.merge_cells("B6:G6")
    ws_tc_sau["B6"] = "Cân điện tử, bình đong 5000ml, bình đong 2500ml, nồi nấu trân châu tự động, muôi đen cán dài, máy đếm giờ, lưới lọc trân châu"
    ws_tc_sau["B6"].font = regular_font
    ws_tc_sau["B6"].border = cell_border

    ws_tc_sau.cell(row=7, column=1, value="Nguyên liệu").font = bold_font
    ws_tc_sau.cell(row=7, column=1).fill = sub_title_fill
    ws_tc_sau.cell(row=7, column=1).border = cell_border
    ws_tc_sau.merge_cells("B7:G7")
    ws_tc_sau["B7"] = "Nước nóng 95°C, trân châu nguyên vị (sống), đường mật"
    ws_tc_sau["B7"].font = regular_font
    ws_tc_sau["B7"].border = cell_border

    # Ratio Table
    ws_tc_sau.merge_cells("A9:G9")
    ws_tc_sau["A9"] = "2. TIÊU CHUẨN KHỐI LƯỢNG ĐỊNH LƯỢNG TRÂN CHÂU"
    ws_tc_sau["A9"].font = tbl_header_font
    ws_tc_sau["A9"].fill = header_red
    ws_tc_sau["A9"].alignment = Alignment(horizontal="center", vertical="center")
    ws_tc_sau.row_dimensions[9].height = 24

    headers_tc_ratio = ["Quy cách", "Nước nóng 95°C", "Trân châu sống", "Đường mật", "Thời gian nấu nồi", "Thời gian ủ nồi", "Số cốc ước tính"]
    for c_idx, h in enumerate(headers_tc_ratio, 1):
        cell = ws_tc_sau.cell(row=10, column=c_idx, value=h)
        cell.font = bold_font
        cell.fill = light_pink
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_tc_sau.row_dimensions[10].height = 24

    tc_ratios = [
        ("0.5 phần", "3000ml", "500g", "250g", "35 phút", "30 phút", "11 cốc"),
        ("1 phần", "4000ml", "1000g", "500g", "35 phút", "30 phút", "22 cốc")
    ]
    for r_i, r_data in enumerate(tc_ratios, 11):
        for c_i, val in enumerate(r_data, 1):
            cell = ws_tc_sau.cell(row=r_i, column=c_i, value=val)
            cell.font = regular_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = cell_border
        ws_tc_sau.row_dimensions[r_i].height = 22

    # Nồi trân châu: Giới thiệu & Cài đặt
    ws_tc_sau.merge_cells("A14:G14")
    ws_tc_sau["A14"] = "3. HƯỚNG DẪN CÀI ĐẶT THÔNG SỐ NỒI NẤU TRÂN CHÂU TỰ ĐỘNG"
    ws_tc_sau["A14"].font = section_font
    ws_tc_sau["A14"].fill = blue_header
    ws_tc_sau["A14"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws_tc_sau.row_dimensions[14].height = 25

    noi_intro = [
        ("Phím ①: 'Bắt đầu / Hủy'", "Ấn nút này để bắt đầu một nhiệm vụ. Khi đang chạy, ấn và giữ 3 giây là có thể hủy nhiệm vụ đang thực hiện."),
        ("Phím ②: 'Điều chỉnh tiến độ'", "Ấn nút này để chuyển đổi linh hoạt qua lại giữa các trạng thái: Đun nước -> Nấu trân châu -> Ủ trân châu."),
        ("Phím ③: 'Điều chỉnh thời gian'", "Ấn nút '+' để tăng thời gian cài đặt, ấn nút '-' để giảm thời gian cài đặt."),
        ("Bước cài đặt 1 (Nấu)", "Ấn nút 'Điều chỉnh tiến độ', chuyển tiến độ sang trạng thái 'Nấu trân châu', ấn '+' hoặc '-' để chỉnh thời gian thành đúng 35 PHÚT."),
        ("Bước cài đặt 2 (Ủ)", "Ấn nút 'Điều chỉnh tiến độ', chuyển tiến độ sang trạng thái 'Ủ trân châu', ấn '+' hoặc '-' để chỉnh thời gian thành đúng 30 PHÚT."),
        ("Bước cài đặt 3 (Đun)", "Sau khi cho nước nóng vào nồi, ấn nút 'Điều chỉnh tiến độ', chuyển sang trạng thái 'Đun nước', ấn 'Bắt đầu' để nồi đun sôi nước.")
    ]
    r_noi = 15
    for k, v in noi_intro:
        ws_tc_sau.merge_cells(f"A{r_noi}:B{r_noi}")
        ws_tc_sau[f"A{r_noi}"] = k
        ws_tc_sau[f"A{r_noi}"].font = bold_font
        ws_tc_sau[f"A{r_noi}"].fill = orange_fill
        ws_tc_sau[f"A{r_noi}"].border = cell_border
        ws_tc_sau[f"A{r_noi}"].alignment = Alignment(horizontal="center", vertical="center")

        ws_tc_sau.merge_cells(f"C{r_noi}:G{r_noi}")
        ws_tc_sau[f"C{r_noi}"] = v
        ws_tc_sau[f"C{r_noi}"].font = regular_font
        ws_tc_sau[f"C{r_noi}"].border = cell_border
        ws_tc_sau[f"C{r_noi}"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws_tc_sau.row_dimensions[r_noi].height = 22
        r_noi += 1

    # Steps Table
    r_noi += 1
    ws_tc_sau.merge_cells(f"A{r_noi}:G{r_noi}")
    ws_tc_sau[f"A{r_noi}"] = "4. CÁC BƯỚC THAO TÁC NẤU TRÂN CHÂU (QUY TRÌNH 1000g TRÂN CHÂU)"
    ws_tc_sau[f"A{r_noi}"].font = tbl_header_font
    ws_tc_sau[f"A{r_noi}"].fill = header_red
    ws_tc_sau[f"A{r_noi}"].alignment = Alignment(horizontal="center", vertical="center")
    ws_tc_sau.row_dimensions[r_noi].height = 25
    r_noi += 1

    headers_tc_steps = ["Bước", "Tên bước thao tác", "Nội dung chi tiết thao tác", "Dụng cụ / Thiết bị", "Thời gian thao tác", "Yêu cầu kỹ thuật & Bảo quản", "Cảnh báo an toàn"]
    for c_idx, h in enumerate(headers_tc_steps, 1):
        cell = ws_tc_sau.cell(row=r_noi, column=c_idx, value=h)
        cell.font = bold_font
        cell.fill = light_pink
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_tc_sau.row_dimensions[r_noi].height = 25
    r_noi += 1

    steps_tc = [
        ("Bước 1", "Cài đặt nồi", "Cài đặt thời gian nấu trân châu 35 phút, thời gian ủ trân châu 30 phút.", "Bảng điều khiển nồi trân châu", "Cài đặt ban đầu", "Đúng thông số 35p nấu / 30p ủ", "-"),
        ("Bước 2", "Cân nước & Đun", "Cân 4000ml nước nóng 95°C vào nồi trân châu, chuyển tiến độ sang 'Đun nước', ấn 'Bắt đầu' đun nước.", "Nồi trân châu, bình đong", "Chờ nồi báo sôi", "Đậy kín nắp nồi khi đun", "-"),
        ("Bước 3", "Lọc bỏ vụn trân châu", "Cân 1000g trân châu, bỏ gói hút ẩm, đổ vào lưới lọc trân châu rồi lắc trái phải cho tơi hạt, sàng lọc bỏ sạch vụn bột.", "Lưới lọc trân châu, cân điện tử", "Trước khi nồi sôi", "Không nấu cả vụn để tránh làm cháy dính đáy nồi", "Bỏ gói hút ẩm!"),
        ("Bước 4", "Thả trân châu & Nấu", "Sau khi nồi báo nước sôi bùng, đổ trân châu vào nồi, dùng muôi đen cán dài khuấy đều 30 giây, đóng chặt nắp nồi.", "Nồi trân châu, muôi đen cán dài", "Khuấy 30s + Nấu 35p", "Khuấy tan không để dính chùm", "TUYỆT ĐỐI KHÔNG MỞ NẮP KHI NẤU (Tránh cháy nổ)"),
        ("Bước 5", "Hết giờ ủ & Khuấy", "Sau khi nồi tự động chuyển sang ủ và báo hết giờ ủ (30p), mở nắp nồi, dùng muôi đen cán dài khuấy đều trân châu.", "Muôi đen cán dài", "Khuấy đều 30s", "Khuấy nhẹ từ đáy nồi lên", "Cẩn thận hơi nóng bốc lên"),
        ("Bước 6", "Lọc nước nóng & Hạ nhiệt", "Dùng lưới lọc lọc bỏ toàn bộ nước luộc, trút trân châu vào bình đong chứa sẵn 2000ml nước lọc, khuấy đều hạ nhiệt khoảng 30 giây.", "Lưới lọc trân châu, bình đong chứa 2000ml nước", "Hạ nhiệt 30 giây", "Chỉ hạ nhiệt đúng 1 lần duy nhất bằng nước lọc sạch", "-"),
        ("Bước 7", "Lọc ráo nước", "Đổ trân châu vào lưới lọc, lắc cho róc hết nước rồi trút vào bình đong 2500ml sạch (không lặp lại bước rửa).", "Lưới lọc, bình đong 2500ml", "Lọc ráo 30 giây", "Không rửa nhiều lần tránh mất độ dai và giảm HSD", "-"),
        ("Bước 8", "Thêm đường mật", "Thêm đúng 500g đường mật vào bình đong chứa trân châu, dùng muôi khuấy đều tay cho đường bao bọc quanh hạt trân châu.", "Đường mật, cân điện tử, muôi", "Khuấy đều 1 phút", "Trân châu ngấm đều vị ngọt bóng mịn", "-"),
        ("Bước 9", "Ủ đường & Dán tem", "Đậy nắp bình đong để ủ đường trong 10 phút, in và dán tem hạn sử dụng chuẩn.", "Bình đong có nắp, tem nhãn", "Ủ đường 10 phút", "• Đậy nắp ở nhiệt độ thường: HSD 4 GIỜ\n• Hết 4 giờ trân châu bị lại hạt, bắt buộc ĐỔ BỎ", "Quá 4 giờ bỏ ngay")
    ]

    for step in steps_tc:
        for c_i, val in enumerate(step, 1):
            cell = ws_tc_sau.cell(row=r_noi, column=c_i, value=val)
            cell.font = regular_font
            cell.border = cell_border
            if c_i in (1, 4, 5):
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            elif c_i == 7:
                cell.font = Font(name=font_family, size=9, bold=True, color="9C0006")
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if r_noi % 2 == 1:
                cell.fill = light_gray
        ws_tc_sau.row_dimensions[r_noi].height = 36
        r_noi += 1

    # Lưu ý nồi trân châu
    r_noi += 1
    ws_tc_sau.merge_cells(f"A{r_noi}:G{r_noi}")
    ws_tc_sau[f"A{r_noi}"] = "5. CÁC LƯU Ý SỐNG CÒN KHI NẤU TRÂN CHÂU SÂN SAU"
    ws_tc_sau[f"A{r_noi}"].font = bold_font
    ws_tc_sau[f"A{r_noi}"].fill = yellow_fill
    ws_tc_sau[f"A{r_noi}"].border = cell_border
    ws_tc_sau.row_dimensions[r_noi].height = 24
    r_noi += 1

    notes_tc = [
        "1. KHI ĐỔ TRÂN CHÂU VÀO LƯỚI LỌC CẦN LẮC ĐỂ LỌC BỎ VỤN: Tránh nấu cả vụn dẫn đến trân châu bị vón cục và dính cháy khét đáy nồi.",
        "2. TRONG THỜI GIAN NẤU TRÂN CHÂU SẼ CÓ HIỆN TƯỢNG XẢ KHÍ 1-2 PHÚT: Đây là hiện tượng van áp suất xả hơi hoàn toàn bình thường, TUYỆT ĐỐI KHÔNG ĐƯỢC MỞ NẮP NỒI trong khi nấu tránh gây bỏng và cháy nổ.",
        "3. SAU KHI Ủ VÀ LỌC HẾT NƯỚC, CHỈ HẠ NHIỆT 1 LẦN BẰNG NƯỚC LỌC: Tránh xả/rửa nước nhiều lần làm trôi lớp tinh bột ngoài, ảnh hưởng trực tiếp đến độ dai dẻo và làm trân châu nhanh hỏng.",
        "4. NẤU 0.5 PHẦN: Dùng 3000ml nước nóng 95°C + 500g trân châu sống + 250g đường mật, quy trình thao tác và thời gian cài đặt hoàn toàn tương tự."
    ]
    for n in notes_tc:
        ws_tc_sau.merge_cells(f"A{r_noi}:G{r_noi}")
        ws_tc_sau[f"A{r_noi}"] = n
        ws_tc_sau[f"A{r_noi}"].font = regular_font
        ws_tc_sau[f"A{r_noi}"].border = cell_border
        ws_tc_sau.row_dimensions[r_noi].height = 24
        r_noi += 1

    ws_tc_sau.column_dimensions['A'].width = 12
    ws_tc_sau.column_dimensions['B'].width = 22
    ws_tc_sau.column_dimensions['C'].width = 46
    ws_tc_sau.column_dimensions['D'].width = 28
    ws_tc_sau.column_dimensions['E'].width = 20
    ws_tc_sau.column_dimensions['F'].width = 38
    ws_tc_sau.column_dimensions['G'].width = 34

    # Save
    wb.save(master_path)
    print(f"Master workbook successfully updated! Total sheets: {len(wb.sheetnames)}")
    for i, s in enumerate(wb.sheetnames, 1):
        print(f"  {i}. {s}")

if __name__ == "__main__":
    add_final_mixue_data()
