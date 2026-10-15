# -*- coding: utf-8 -*-
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def create_mixue_workbook():
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # Styles
    font_family = "Segoe UI"
    title_font = Font(name=font_family, size=16, bold=True, color="FFFFFF")
    section_font = Font(name=font_family, size=12, bold=True, color="FFFFFF")
    tbl_header_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
    tbl_header_sub_font = Font(name=font_family, size=10, bold=True, color="1F2937")
    bold_font = Font(name=font_family, size=10, bold=True, color="000000")
    regular_font = Font(name=font_family, size=10, color="000000")
    italic_font = Font(name=font_family, size=9, italic=True, color="555555")
    code_font = Font(name="Consolas", size=10, bold=True, color="9C0006")

    # Fills
    red_title_fill = PatternFill(start_color="D92525", end_color="D92525", fill_type="solid") # Mixue Red
    dark_red_fill = PatternFill(start_color="B31B1B", end_color="B31B1B", fill_type="solid")
    red_tbl_header = PatternFill(start_color="E04343", end_color="E04343", fill_type="solid")
    blue_header = PatternFill(start_color="1E88E5", end_color="1E88E5", fill_type="solid")
    blue_light_header = PatternFill(start_color="29B6F6", end_color="29B6F6", fill_type="solid")
    light_pink_fill = PatternFill(start_color="FDEDEC", end_color="FDEDEC", fill_type="solid")
    light_gray_fill = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")
    yellow_note_fill = PatternFill(start_color="FFF9E6", end_color="FFF9E6", fill_type="solid")

    # Borders
    thin_border_side = Side(style='thin', color='B0B0B0')
    thick_border_side = Side(style='medium', color='707070')
    cell_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    bottom_double = Border(bottom=Side(style='double', color='707070'), left=thin_border_side, right=thin_border_side, top=thin_border_side)

    # -------------------------------------------------------------
    # SHEET 1: MẬT MÃ SẢN PHẨM & NGUYÊN LIỆU (Image 5)
    # -------------------------------------------------------------
    ws1 = wb.create_sheet(title="Mat_Ma_San_Pham")
    ws1.views.sheetView[0].showGridLines = True

    # Title Block
    ws1.merge_cells("A1:G1")
    ws1["A1"] = "HƯỚNG DẪN SỬ DỤNG MẬT MÃ SẢN PHẨM - MIXUE (Phiên bản: 06.2025)"
    ws1["A1"].font = title_font
    ws1["A1"].fill = red_title_fill
    ws1["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws1.row_dimensions[1].height = 40

    ws1.merge_cells("A2:G2")
    ws1["A2"] = "Mục đích: Giúp nhân viên mới ghi nhớ công thức, giảm sai sót pha chế, chuẩn hóa chất lượng & tiết kiệm chi phí nguyên vật liệu."
    ws1["A2"].font = italic_font
    ws1["A2"].fill = light_pink_fill
    ws1["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[2].height = 24

    # Table A: Bảng Ký Hiệu Mật Mã Nguyên Liệu
    ws1.merge_cells("A4:G4")
    ws1["A4"] = "I. BẢNG KÝ HIỆU VÀ MẬT MÃ NGUYÊN LIỆU"
    ws1["A4"].font = section_font
    ws1["A4"].fill = blue_header
    ws1["A4"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[4].height = 28

    headers_matma = ["Nhóm phân loại", "Tên nguyên liệu", "Mật mã viết tắt", "Giải thích / Đơn vị", "Ví dụ sử dụng", "HSD mở bao/dùng", "Ghi chú"]
    for col_idx, h in enumerate(headers_matma, 1):
        cell = ws1.cell(row=5, column=col_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = blue_light_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws1.row_dimensions[5].height = 26

    raw_mat_ma = [
        # Trái cây tươi
        ("Trái cây tươi", "Chanh tươi", "C", "Gram hoặc lát dầm", "C40 = 40g chanh", "Dùng trong ngày", "Cắt tươi hàng ngày"),
        # Đường & Chất ngọt
        ("Đường & Tạo ngọt", "Đường mật", "- (chỉ ghi số)", "ml siro đường", "40 = 40ml đường mật", "24 tháng", "Mặc định nếu chỉ ghi số là đường mật"),
        ("Đường & Tạo ngọt", "Đường quả (Fructose)", "Q", "ml siro đường quả", "Q20 = 20ml đường quả", "9 tháng", "Chai siro màu vàng"),
        ("Đường & Tạo ngọt", "Đường đen", "Đ", "ml siro đường đen", "Đ10 = 10ml đường đen, Đ30 = 30ml", "9 tháng", "Dùng cho trà sữa / sundae đường đen"),
        ("Đường & Tạo ngọt", "Sốt Socola", "S", "ml sốt socola", "S10 = 10ml, S40 = 40ml", "9 tháng", "Chai sốt socola"),
        ("Đường & Tạo ngọt", "Syrup hạt dẻ và bơ", "HD", "ml syrup caramel/hạt dẻ", "HD40 = 40ml syrup hạt dẻ bơ", "9 tháng", "Dùng tạo vị caramel"),
        # Topping
        ("Topping", "Vụn ốc quế", "Ô.quế", "Muỗng/vá đong", "Ô.quế2 = 2 muỗng vụn ốc quế", "6 tháng", "Rắc trên sundae"),
        ("Topping", "Vụn bánh Oreo", "Oreo", "Muỗng đong", "Oreo1 = 1 muỗng, Oreo2 = 2 muỗng", "12 tháng", "Bánh oreo nghiền vụn"),
        ("Topping", "Thạch dừa", "T.dừa", "Vá đong", "T.dừa1 = 1 vá, T.dừa2 = 2 vá", "Xem trên bao bì", "Topping thạch dừa giòn"),
        ("Topping", "Lô hội (Nha đam)", "L.hội", "Vá đong", "L.hội2 = 2 vá lô hội", "Xem trên bao bì", "Topping lô hội"),
        ("Topping", "Trân châu trắng", "TC.trắng", "Vá đong", "TC.trắng2 = 2 vá trân châu trắng", "Xem trên bao bì", "Trân châu 3Q giòn"),
        ("Topping", "Trân châu nguyên vị (đen)", "TC.đen", "Vá đong", "TC.đen1 = 1 vá, TC.đen2 = 2 vá", "4 giờ sau nấu", "Nấu mới trong ca làm việc"),
        ("Topping", "Thạch đường đen", "T.đen", "Vá đong", "T.đen1 = 1 vá, T.đen2 = 2 vá", "Xem trên bao bì", "Thạch đen thơm đường"),
        ("Topping", "Thạch dâu", "T.dâu", "Vá đong", "T.dâu1 = 1 vá", "Xem trên bao bì", "Thạch vị dâu"),
        ("Topping", "Thạch sữa", "T.sữa", "Vá đong", "T.sữa1 = 1 vá, T.sữa2 = 2 vá", "Xem trên bao bì", "Thạch sữa béo"),
        ("Topping", "Thạch đào", "T.đào", "Vá đong", "T.đào1 = 1 vá, T.đào3 = 3 vá", "Xem trên bao bì", "Thạch vị đào giòn dai"),
        # Mứt quả
        ("Mứt quả & Syrup", "Mứt đào vàng", "Đ.vàng", "Muỗng/vá mứt", "Đ.vàng4 = 4 muỗng mứt đào vàng", "12 tháng", "Hộp mứt đào vàng"),
        ("Mứt quả & Syrup", "Mứt đào mật", "Đ.mật", "Muỗng/vá mứt", "Đ.mật2 = 2 muỗng, Đ.mật3 = 3 muỗng", "12 tháng", "Hộp mứt đào mật hạt"),
        ("Mứt quả & Syrup", "Mứt dâu tây", "D.tây", "Muỗng/vá mứt", "D.tây1 = 1 muỗng, D.tây3 = 3 muỗng", "12 tháng", "Hộp mứt dâu tây"),
        ("Mứt quả & Syrup", "Mứt xoài", "Xoài", "Muỗng/vá mứt", "Xoài1.6 = 1.6 muỗng, Xoài3 = 3 muỗng", "12 tháng", "Hộp mứt xoài hạt"),
        ("Mứt quả & Syrup", "Mứt kiwi", "Kiwi", "Muỗng/vá mứt", "Kiwi1 = 1 muỗng, Kiwi3 = 3 muỗng", "Xem trên bao bì", "Mứt kiwi hạt"),
        ("Mứt quả & Syrup", "Mứt chanh leo", "C.leo", "Muỗng/vá mứt", "C.leo1 = 1 muỗng, C.leo2 = 2 muỗng", "Xem trên bao bì", "Mứt chanh dây chua ngọt"),
        ("Mứt quả & Syrup", "Syrup vải", "Vải", "Muỗng/ml syrup", "Vải3 = 3 muỗng / định lượng vải", "Xem trên bao bì", "Syrup hương vải"),
        ("Mứt quả & Syrup", "Syrup dưa lưới", "D.lưới", "Muỗng/ml syrup", "D.lưới2 = 2 muỗng / định lượng", "Xem trên bao bì", "Syrup dưa lưới xanh"),
        # Bán thành phẩm
        ("Bán thành phẩm", "Trà xanh sân sau", "X", "ml cốt trà xanh hoặc tỉ lệ", "X120 = 120ml, X0.8 = vạch 0.8 bình lắc", "Đổ bỏ cuối ngày", "Ủ từ lá trà xanh sân sau"),
        ("Bán thành phẩm", "Hồng trà sân sau", "H", "ml cốt hồng trà hoặc tỉ lệ", "H100 = 100ml, H0.8 = vạch 0.8 bình lắc", "Đổ bỏ cuối ngày", "Ủ từ lá hồng trà sân sau"),
        ("Bán thành phẩm", "Trà sữa pha sẵn", "TS", "Vạch mức bình lắc", "TS0.8 = rót trà sữa đến vạch 0.8", "Theo ca/cuối ngày", "Cốt trà sữa pha từ bột trà sữa"),
        ("Bán thành phẩm", "Sữa đặc", "S.đặc", "ml sữa đặc", "S.đặc60 = 60ml, S.đặc100 = 100ml", "Xem trên lon", "Sữa đặc có đường"),
        ("Bán thành phẩm", "Latte cô đặc (Cà phê)", "Latte", "ml latte cô đặc", "Latte160 = 160ml latte cô đặc", "Theo quy định", "Cốt cà phê latte"),
        ("Bán thành phẩm", "Matcha cô đặc", "M.cha", "Vạch mức bình lắc", "M.cha0.8 = vạch mức 0.8", "Theo ca", "Cốt matcha đánh mịn"),
        # Loại khác
        ("Loại khác", "Kem tươi nguyên vị", "(kem) / (số)", "Gram (g) kem tươi", "(120) = 120g kem, (180) = 180g kem", "Đổ bỏ cuối ngày", "Chiết trực tiếp từ máy làm kem")
    ]

    curr_row = 6
    for item in raw_mat_ma:
        for col_idx, val in enumerate(item, 1):
            cell = ws1.cell(row=curr_row, column=col_idx, value=val)
            cell.font = bold_font if col_idx == 3 else regular_font
            if col_idx == 3:
                cell.font = code_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx in (1, 4, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            cell.border = cell_border
            if curr_row % 2 == 1:
                cell.fill = light_gray_fill
        curr_row += 1

    # Table B: Bảng Ký Hiệu Mã Hóa Tên Sản Phẩm (42 món)
    curr_row += 2
    ws1.merge_cells(f"A{curr_row}:G{curr_row}")
    ws1[f"A{curr_row}"] = "II. BẢNG MẬT MÃ CÔNG THỨC PHA CHẾ SẢN PHẨM (BẢN THƯỜNG - 42 MÓN)"
    ws1[f"A{curr_row}"].font = section_font
    ws1[f"A{curr_row}"].fill = red_title_fill
    ws1[f"A{curr_row}"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[curr_row].height = 28
    curr_row += 1

    headers_drinks = ["STT", "Nhóm đồ uống", "Tên sản phẩm (Bản thường)", "Ký hiệu mã hóa", "Thành phần 1 (Đường/Kem/Cốt)", "Thành phần 2 (Topping/Mứt)", "Thành phần 3 (Cốt nước/Trà/Sữa)"]
    for col_idx, h in enumerate(headers_drinks, 1):
        cell = ws1.cell(row=curr_row, column=col_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = red_tbl_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws1.row_dimensions[curr_row].height = 26
    curr_row += 1

    # 42 Drinks List with detailed recipe decomposition
    drinks_data = [
        # Col 1 from original image
        (1, "Sữa kem lắc", "Sữa kem lắc dâu tây", "(120)/ D.tây2/ X0.8/", "120g Kem", "2 muỗng Mứt dâu tây", "Trà xanh đến vạch 0.8 bình lắc"),
        (2, "Sữa kem lắc", "Sữa kem lắc đào", "(120)/ T.đào1, Đ.mật2/ X0.8/", "120g Kem", "1 vá Thạch đào + 2 muỗng Mứt đào mật", "Trà xanh đến vạch 0.8 bình lắc"),
        (3, "Sữa kem lắc", "Sữa kem lắc trân châu đường", "(120)/ Đ10/ TC.đen2/ H0.8/", "120g Kem + 10ml Đường đen", "2 vá Trân châu đen", "Hồng trà đến vạch 0.8 bình lắc"),
        (4, "Sundae", "Super sundae trân châu đường", "/Đ10/ (180)/ TC.đen2/", "10ml Đường đen đáy ly + 180g Kem", "2 vá Trân châu đen phủ trên", "-"),
        (5, "Sundae", "Super sundae xoài", "(180)/ Xoài1.6/", "180g Kem", "1.6 muỗng Mứt xoài", "-"),
        (6, "Sundae", "Super sundae kiwi lô hội", "/(180)/ Kiwi1, L.hội2/", "180g Kem", "1 muỗng Mứt kiwi + 2 vá Lô hội", "-"),
        (7, "Sundae", "Lucky sundae O-coco", "/Ô.quế2/ (120)/ S10/ Oreo2/", "2 muỗng Vụn ốc quế đáy + 120g Kem", "10ml Sốt Socola", "2 muỗng Vụn bánh Oreo phủ trên"),
        (8, "Sundae", "Lucky sundae dâu tây", "/Ô.quế2/ (120)/ D.tây1/", "2 muỗng Vụn ốc quế đáy + 120g Kem", "1 muỗng Mứt dâu tây phủ trên", "-"),
        (9, "Trà hoa quả", "Trà đào bigsize", "/40/ T.đào3, Đ.vàng4/ H100/", "40ml Đường mật", "3 vá Thạch đào + 4 muỗng Mứt đào vàng", "100ml Hồng trà"),
        (10, "Trà hoa quả", "Trà xanh hoa đào", "/40/ T.đào3, Đ.mật3/ X120/", "40ml Đường mật", "3 vá Thạch đào + 3 muỗng Mứt đào mật", "120ml Trà xanh"),
        (11, "Trà hoa quả", "Trà xanh kiwi", "/40, Q20/ T.dừa2, T.đào1, Kiwi3/ X120/", "40ml Đường mật + 20ml Đường quả", "2 vá Thạch dừa + 1 vá Thạch đào + 3 muỗng Kiwi", "120ml Trà xanh"),
        (12, "Trà hoa quả", "Chanh leo bách hương", "/20/ T.dừa2, TC.đen2, C.leo2/ X120/", "20ml Đường mật", "2 vá Thạch dừa + 2 vá Trân châu đen + 2 muỗng C.leo", "120ml Trà xanh"),
        (13, "Trà hoa quả", "Dương chi cam lộ", "(110)/ T.dừa1, T.đào1, TC.đen1, Xoài3/", "110g Kem", "1 vá T.dừa + 1 vá T.đào + 1 vá TC.đen + 3 muỗng Xoài", "-"),
        (14, "Nước quả tươi", "Nước chanh tươi lạnh", "/C40/ Q55/", "40g Chanh tươi dầm", "55ml Đường quả", "Nước lọc & đá theo định lượng"),
        (15, "Trà hoa quả", "Trà chanh xanh", "/C40/ 30, Q40/ X160/", "40g Chanh dầm + 30ml Đường mật + 40ml Đường quả", "-", "160ml Trà xanh"),
        (16, "Trà hoa quả", "Trà chanh lô hội", "/C40/ 70/ T.dừa1, L.hội2/ H140/", "40g Chanh dầm + 70ml Đường mật", "1 vá Thạch dừa + 2 vá Lô hội", "140ml Hồng trà"),
        (17, "Trà hoa quả", "Trà xoài chanh leo", "/40/ T.dừa2, C.leo1, Xoài2 / X120/", "40ml Đường mật", "2 vá Thạch dừa + 1 muỗng C.leo + 2 muỗng Xoài", "120ml Trà xanh"),
        (18, "Sundae", "Super sundae matcha O-coco", "(180)/ Oreo2/", "180g Kem matcha", "2 muỗng Vụn bánh Oreo", "-"),
        (19, "Matcha", "Sữa tươi matcha", "/30/ TC.đen1, T.sữa1/ M.cha0.8/", "30ml Đường mật", "1 vá Trân châu đen + 1 vá Thạch sữa", "Matcha cô đặc đến vạch 0.8 bình lắc"),
        (20, "Sundae", "Super sundae đào hoa hồng", "(180)/ Đ.mật3, TC.trắng2/", "180g Kem", "3 muỗng Mứt đào mật + 2 vá Trân châu trắng", "-"),
        (21, "Sữa tươi / Thạch", "Sữa thạch vải hoa hồng", "/10/ T.sữa2, TC.trắng2, Vải3/ S.đặc100/", "10ml Đường mật", "2 vá T.sữa + 2 vá TC.trắng + 3 muỗng Syrup vải", "100ml Sữa đặc"),
        # Col 2 from original image
        (22, "Cà phê Latte", "Cafe latte kem tươi", "/20/ T.đen1/ Latte160/ (90)/", "20ml Đường mật + 160ml Latte cô đặc", "1 vá Thạch đường đen", "90g Kem tươi xịt trên cùng"),
        (23, "Cà phê Latte", "Cafe Mocha kem tươi", "/10, S40/ T.đen1/ Latte160/ (90)/", "10ml Đường mật + 40ml Sốt Socola + 160ml Latte", "1 vá Thạch đường đen", "90g Kem tươi xịt trên cùng"),
        (24, "Cà phê Latte", "Cafe latte caramel kem tươi", "/HD40/ T.đen1/ Latte160/ (90)/", "40ml Syrup hạt dẻ bơ + 160ml Latte cô đặc", "1 vá Thạch đường đen", "90g Kem tươi xịt trên cùng"),
        (25, "Sữa thạch", "Sữa thạch kiwi", "/30/ T.đào2, Kiwi3/ S.đặc60/", "30ml Đường mật", "2 vá Thạch đào + 3 muỗng Mứt kiwi", "60ml Sữa đặc"),
        (26, "Sữa thạch", "Sữa thạch dâu tây", "/20/ T.đào2, D.tây3/ S.đặc60/", "20ml Đường mật", "2 vá Thạch đào + 3 muỗng Mứt dâu tây", "60ml Sữa đặc"),
        (27, "Trà sữa", "Trà sữa trân châu đường đen", "/Đ30/ TC.đen2/ TS0.8/", "30ml Đường đen", "2 vá Trân châu đen", "Trà sữa đến vạch 0.8 bình lắc"),
        (28, "Trà sữa", "Trà sữa caramel", "/HD40/ T.đen2/ TS0.8/", "40ml Syrup hạt dẻ bơ (caramel)", "2 vá Thạch đường đen", "Trà sữa đến vạch 0.8 bình lắc"),
        (29, "Trà sữa", "Trà sữa trân châu", "/30/ TC.đen2/ TS0.8/", "30ml Đường mật", "2 vá Trân châu đen", "Trà sữa đến vạch 0.8 bình lắc"),
        (30, "Trà sữa", "Trà sữa trân châu (L)", "/30/ TC.đen4/ TS0.8/", "30ml Đường mật", "4 vá Trân châu đen", "Trà sữa đến vạch 0.8 bình lắc"),
        (31, "Trà sữa", "Trà sữa thạch dừa", "/30/ T.dừa2/ TS0.8/", "30ml Đường mật", "2 vá Thạch dừa", "Trà sữa đến vạch 0.8 bình lắc"),
        (32, "Trà sữa", "Trà sữa thạch dừa (L)", "/30/ T.dừa6/ TS0.8/", "30ml Đường mật", "6 vá Thạch dừa", "Trà sữa đến vạch 0.8 bình lắc"),
        (33, "Trà sữa", "Trà sữa thạch đường đen", "/30/ T.đen2/ TS0.8/", "30ml Đường mật", "2 vá Thạch đường đen", "Trà sữa đến vạch 0.8 bình lắc"),
        (34, "Trà sữa", "Trà sữa thạch đường đen (L)", "/30/ T.đen4/ TS0.8/", "30ml Đường mật", "4 vá Thạch đường đen", "Trà sữa đến vạch 0.8 bình lắc"),
        (35, "Trà sữa", "Trà sữa 2J", "/30/ T.dừa2, T.đen2/ TS0.8/", "30ml Đường mật", "2 vá Thạch dừa + 2 vá Thạch đường đen", "Trà sữa đến vạch 0.8 bình lắc"),
        (36, "Trà sữa", "Trà sữa 2J (L)", "/30/ T.dừa3, T.đen3/ TS0.8/", "30ml Đường mật", "3 vá Thạch dừa + 3 vá Thạch đường đen", "Trà sữa đến vạch 0.8 bình lắc"),
        (37, "Trà sữa", "Trà sữa O-coco", "/10, S40/ Oreo1, T.đen2/ TS0.8/", "10ml Đường mật + 40ml Sốt Socola", "1 muỗng Vụn Oreo + 2 vá Thạch đường đen", "Trà sữa đến vạch 0.8 bình lắc"),
        (38, "Trà sữa", "Trà sữa Bá Vương", "/30/ TC.đen2, T.đen2, T.dừa2/ TS0.8/", "30ml Đường mật", "2 vá TC.đen + 2 vá T.đen + 2 vá T.dừa", "Trà sữa đến vạch 0.8 bình lắc"),
        (39, "Sundae", "Super sundae kiwi dưa lưới", "(180)/ Kiwi1, T.dừa2/", "180g Kem", "1 muỗng Mứt kiwi + 2 vá Thạch dừa", "-"),
        (40, "Sữa thạch", "Sữa thạch dưa lưới", "/TC.trắng2, T.dừa2, D.lưới2/ S.đặc100/", "100ml Sữa đặc", "2 vá TC.trắng + 2 vá T.dừa + 2 muỗng Syrup dưa lưới", "-"),
        (41, "Sundae", "Super sundae cà phê trân châu", "(180)/ TC.đen2/", "180g Kem (vị cà phê)", "2 vá Trân châu đen", "-"),
        (42, "Sundae", "Super sundae cà phê O-coco", "(180)/ Oreo 2/", "180g Kem (vị cà phê)", "2 muỗng Vụn bánh Oreo", "-")
    ]

    for item in drinks_data:
        stt, cat, name, code, c1, c2, c3 = item
        ws1.cell(row=curr_row, column=1, value=stt).alignment = Alignment(horizontal="center", vertical="center")
        ws1.cell(row=curr_row, column=2, value=cat).alignment = Alignment(horizontal="center", vertical="center")
        ws1.cell(row=curr_row, column=3, value=name).alignment = Alignment(horizontal="left", vertical="center")
        
        c_code = ws1.cell(row=curr_row, column=4, value=code)
        c_code.font = code_font
        c_code.alignment = Alignment(horizontal="center", vertical="center")
        
        ws1.cell(row=curr_row, column=5, value=c1).alignment = Alignment(horizontal="left", vertical="center")
        ws1.cell(row=curr_row, column=6, value=c2).alignment = Alignment(horizontal="left", vertical="center")
        ws1.cell(row=curr_row, column=7, value=c3).alignment = Alignment(horizontal="left", vertical="center")

        for col_idx in range(1, 8):
            cell = ws1.cell(row=curr_row, column=col_idx)
            cell.border = cell_border
            if col_idx != 4:
                cell.font = regular_font
            if curr_row % 2 == 1:
                cell.fill = light_gray_fill
        curr_row += 1

    # Auto-adjust column widths
    ws1.column_dimensions['A'].width = 16
    ws1.column_dimensions['B'].width = 24
    ws1.column_dimensions['C'].width = 30
    ws1.column_dimensions['D'].width = 36
    ws1.column_dimensions['E'].width = 40
    ws1.column_dimensions['F'].width = 48
    ws1.column_dimensions['G'].width = 36


    # -------------------------------------------------------------
    # SHEET 2: CÔNG THỨC KEM SÂN SAU (Image 1)
    # -------------------------------------------------------------
    ws2 = wb.create_sheet(title="Kem_Nguyen_Vi_San_Sau")
    ws2.views.sheetView[0].showGridLines = True

    # Title
    ws2.merge_cells("A1:F1")
    ws2["A1"] = "CÔNG THỨC KEM NGUYÊN VỊ SÂN SAU ④ (17.07.2025)"
    ws2["A1"].font = title_font
    ws2["A1"].fill = red_title_fill
    ws2["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 40

    # Tiêu chuẩn chung
    ws2.merge_cells("A3:F3")
    ws2["A3"] = "1. QUY CHUẨN CÂN ĐO ĐONG ĐẾM"
    ws2["A3"].font = bold_font
    ws2["A3"].fill = light_pink_fill
    ws2["A3"].border = cell_border
    
    ws2.merge_cells("A4:F4")
    ws2["A4"] = "• Tiêu chuẩn cân đồ: ≤ 500g được sai số ± 5g  |  > 500g được sai số ± 10g  |  ≥ 3000g được sai số ± 20g"
    ws2["A4"].font = regular_font
    ws2["A4"].border = cell_border

    ws2.merge_cells("A5:F5")
    ws2["A5"] = "• Cân và đong: Ghi chú bằng gam (g) thì dùng CÂN, ghi chú bằng mililit (ml) thì dùng BÌNH ĐONG."
    ws2["A5"].font = regular_font
    ws2["A5"].border = cell_border

    # Dụng cụ & Nguyên liệu
    ws2.cell(row=7, column=1, value="Dụng cụ").font = bold_font
    ws2.cell(row=7, column=1).fill = light_gray_fill
    ws2.cell(row=7, column=1).border = cell_border
    ws2.merge_cells("B7:F7")
    ws2["B7"] = "Cân điện tử, xô inox, phới khuấy, máy đếm giờ, lưới lọc kem"
    ws2["B7"].font = regular_font
    ws2["B7"].border = cell_border

    ws2.cell(row=8, column=1, value="Nguyên liệu").font = bold_font
    ws2.cell(row=8, column=1).fill = light_gray_fill
    ws2.cell(row=8, column=1).border = cell_border
    ws2.merge_cells("B8:F8")
    ws2["B8"] = "Bột kem nguyên vị, nước lọc"
    ws2["B8"].font = regular_font
    ws2["B8"].border = cell_border

    # Bảng Tiêu chuẩn khối lượng
    ws2.merge_cells("A10:F10")
    ws2["A10"] = "2. TIÊU CHUẨN KHỐI LƯỢNG ĐỊNH LƯỢNG KEM"
    ws2["A10"].font = tbl_header_font
    ws2["A10"].fill = red_tbl_header
    ws2["A10"].alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[10].height = 25

    headers_kem = ["Số phần", "Bột kem nguyên vị (g)", "Nước lọc (g)", "Thời gian khuấy", "Thời gian chờ nở", "Số kem ốc quế ước tính"]
    for c_idx, h in enumerate(headers_kem, 1):
        cell = ws2.cell(row=11, column=c_idx, value=h)
        cell.font = bold_font
        cell.fill = light_pink_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws2.row_dimensions[11].height = 25

    kem_ratio = [
        ("1 phần", 1500, 4000, "3 phút", "15 phút (khuấy lại 2 lần)", "42 cái"),
        ("1.5 phần", 2250, 6000, "3 phút", "15 phút (khuấy lại 2 lần)", "69 cái"),
        ("2 phần", 3000, 8000, "3 phút", "15 phút (khuấy lại 2 lần)", "95 cái")
    ]
    for r_idx, row_data in enumerate(kem_ratio, 12):
        for c_idx, val in enumerate(row_data, 1):
            cell = ws2.cell(row=r_idx, column=c_idx, value=val)
            cell.font = regular_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = cell_border
        ws2.row_dimensions[r_idx].height = 22

    # Các bước thao tác
    ws2.merge_cells("A16:F16")
    ws2["A16"] = "3. CÁC BƯỚC THAO TÁC PHA CHẾ (VÍ DỤ 1 PHẦN)"
    ws2["A16"].font = tbl_header_font
    ws2["A16"].fill = red_tbl_header
    ws2["A16"].alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[16].height = 25

    headers_steps_kem = ["Bước", "Tên bước thao tác", "Nội dung chi tiết thao tác", "Dụng cụ / Thiết bị", "Thời gian", "Quy định bảo quản & Xử lý"]
    for c_idx, h in enumerate(headers_steps_kem, 1):
        cell = ws2.cell(row=17, column=c_idx, value=h)
        cell.font = bold_font
        cell.fill = light_pink_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws2.row_dimensions[17].height = 25

    steps_kem = [
        ("Bước 1", "Cân nước lọc", "Cân đúng 4000g nước lọc vào xô inox sạch.", "Cân điện tử, xô inox", "-", "Đảm bảo nước lọc tinh khiết đạt chuẩn."),
        ("Bước 2", "Thêm bột kem", "Thêm đúng 1500g bột kem nguyên vị vào xô inox đã có nước.", "Cân điện tử", "-", "Đổ nhẹ tránh văng bột ra ngoài."),
        ("Bước 3", "Khuấy tan bột", "Dùng dụng cụ khuấy khuấy liên tục cho đến khi bột kem tan hết (khoảng 3 phút). Để bên ngoài 15 phút, trong 15 phút đó khuấy lại 2 lần.", "Phới khuấy, máy đếm giờ", "3 phút khuấy + 15 phút chờ nở", "Khuấy đều tay từ đáy xô để không vón cục."),
        ("Bước 4", "Lọc kem", "Dùng lưới lọc kem lọc lại hỗn hợp là có thể sử dụng (ghi thời gian pha chế và đổ bỏ).", "Lưới lọc kem, xô/bình đong", "-", "Loại bỏ hoàn toàn cặn vón giúp kem mịn."),
        ("Bước 5", "Bảo quản & Sử dụng", "Kem đã pha có thể lọc vào bình đong, đậy nắp và dán tem hạn sử dụng, bảo quản trong tủ lạnh chờ dùng.", "Bình đong có nắp, tem nhãn, tủ lạnh", "Trong ngày", "• Bình đong đậy nắp trong tủ lạnh: ĐỔ BỎ CUỐI NGÀY\n• Kem trong máy làm kem: ĐỔ BỎ CUỐI NGÀY")
    ]
    for r_idx, step in enumerate(steps_kem, 18):
        for c_idx, val in enumerate(step, 1):
            cell = ws2.cell(row=r_idx, column=c_idx, value=val)
            cell.font = regular_font
            if c_idx in (1, 4, 5):
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            cell.border = cell_border
        ws2.row_dimensions[r_idx].height = 42

    ws2.column_dimensions['A'].width = 12
    ws2.column_dimensions['B'].width = 24
    ws2.column_dimensions['C'].width = 46
    ws2.column_dimensions['D'].width = 26
    ws2.column_dimensions['E'].width = 24
    ws2.column_dimensions['F'].width = 44


    # -------------------------------------------------------------
    # SHEET 3: CÔNG THỨC TRÀ XANH SÂN SAU (Image 2)
    # -------------------------------------------------------------
    ws3 = wb.create_sheet(title="Tra_Xanh_San_Sau")
    ws3.views.sheetView[0].showGridLines = True

    # Title
    ws3.merge_cells("A1:F1")
    ws3["A1"] = "CÔNG THỨC TRÀ XANH SÂN SAU ① (17.07.2025)"
    ws3["A1"].font = title_font
    ws3["A1"].fill = red_title_fill
    ws3["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws3.row_dimensions[1].height = 40

    # Tiêu chuẩn chung
    ws3.merge_cells("A3:F3")
    ws3["A3"] = "1. QUY CHUẨN CÂN ĐO ĐONG ĐẾM"
    ws3["A3"].font = bold_font
    ws3["A3"].fill = light_pink_fill
    ws3["A3"].border = cell_border
    
    ws3.merge_cells("A4:F4")
    ws3["A4"] = "• Tiêu chuẩn cân đồ: ≤ 500g được sai số ± 5g  |  > 500g được sai số ± 10g  |  ≥ 3000g được sai số ± 20g"
    ws3["A4"].font = regular_font
    ws3["A4"].border = cell_border

    ws3.merge_cells("A5:F5")
    ws3["A5"] = "• Cân và đo đong: Ghi chú bằng gam (g) thì dùng CÂN, ghi chú bằng mililit (ml) thì dùng BÌNH ĐONG."
    ws3["A5"].font = regular_font
    ws3["A5"].border = cell_border

    # Dụng cụ & Nguyên liệu
    ws3.cell(row=7, column=1, value="Dụng cụ").font = bold_font
    ws3.cell(row=7, column=1).fill = light_gray_fill
    ws3.cell(row=7, column=1).border = cell_border
    ws3.merge_cells("B7:F7")
    ws3["B7"] = "Cân điện tử, bình đong 5000ml, máy đếm giờ, bình giữ nhiệt, lưới lọc trà, phới khuấy"
    ws3["B7"].font = regular_font
    ws3["B7"].border = cell_border

    ws3.cell(row=8, column=1, value="Nguyên liệu").font = bold_font
    ws3.cell(row=8, column=1).fill = light_gray_fill
    ws3.cell(row=8, column=1).border = cell_border
    ws3.merge_cells("B8:F8")
    ws3["B8"] = "Lá trà xanh, nước nóng 95°C, đá"
    ws3["B8"].font = regular_font
    ws3["B8"].border = cell_border

    # Bảng Tiêu chuẩn khối lượng
    ws3.merge_cells("A10:F10")
    ws3["A10"] = "2. TIÊU CHUẨN KHỐI LƯỢNG ĐỊNH LƯỢNG Ủ TRÀ XANH"
    ws3["A10"].font = tbl_header_font
    ws3["A10"].fill = red_tbl_header
    ws3["A10"].alignment = Alignment(horizontal="center", vertical="center")
    ws3.row_dimensions[10].height = 25

    headers_tra = ["Số phần", "Nước nóng 95°C (g)", "Lá trà xanh", "Đá (g)", "Thời gian ủ trà", "Số cốc dự kiến"]
    for c_idx, h in enumerate(headers_tra, 1):
        cell = ws3.cell(row=11, column=c_idx, value=h)
        cell.font = bold_font
        cell.fill = light_pink_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws3.row_dimensions[11].height = 25

    tra_ratio = [
        ("1 phần", 1500, "60g (1 gói)", 1000, "6 phút", "19 cốc"),
        ("2 phần", 3000, "120g (2 gói)", 2000, "6 phút", "38 cốc")
    ]
    for r_idx, row_data in enumerate(tra_ratio, 12):
        for c_idx, val in enumerate(row_data, 1):
            cell = ws3.cell(row=r_idx, column=c_idx, value=val)
            cell.font = regular_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = cell_border
        ws3.row_dimensions[r_idx].height = 22

    # Các bước thao tác
    ws3.merge_cells("A15:F15")
    ws3["A15"] = "3. CÁC BƯỚC THAO TÁC Ủ TRÀ (VÍ DỤ 1 PHẦN)"
    ws3["A15"].font = tbl_header_font
    ws3["A15"].fill = red_tbl_header
    ws3["A15"].alignment = Alignment(horizontal="center", vertical="center")
    ws3.row_dimensions[15].height = 25

    headers_steps_tra = ["Bước", "Tên bước thao tác", "Nội dung chi tiết thao tác", "Dụng cụ / Thiết bị", "Thời gian / Lưu ý", "Hạn dùng & Bảo quản"]
    for c_idx, h in enumerate(headers_steps_tra, 1):
        cell = ws3.cell(row=16, column=c_idx, value=h)
        cell.font = bold_font
        cell.fill = light_pink_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws3.row_dimensions[16].height = 25

    steps_tra = [
        ("Bước 1", "Cân nước nóng 95°C", "Cân đúng 1500g nước nóng (lấy từ máy nước nóng 95°C) vào bình đong 5000ml.", "Máy nước nóng, bình đong 5000ml, cân điện tử", "Nhiệt độ chuẩn 95°C", "-"),
        ("Bước 2", "Cho lá trà xanh", "Xé 1 gói trà xanh (60g) đổ vào bình đong có chứa sẵn nước nóng.", "Gói trà xanh 60g", "-", "-"),
        ("Bước 3", "Ủ trà kín", "KHÔNG KHUẤY, đậy kín nắp bình đong và để ủ trong vòng đúng 6 phút.", "Nắp bình đong, máy đếm giờ", "Ủ 6 phút (bấm giờ)", "Tuyệt đối không khuấy trà."),
        ("Bước 4", "Chuẩn bị đá sốc nhiệt", "Cân sẵn 1000g đá sạch vào bình giữ nhiệt chờ sẵn.", "Bình giữ nhiệt, cân điện tử, xẻng xúc đá", "-", "Chuẩn bị sẵn trước khi hết giờ ủ."),
        ("Bước 5", "Lọc trà qua đá", "Hết giờ ủ 6 phút, lọc ngay nước trà vào bình giữ nhiệt có chứa sẵn đá. Để nước trà tự chảy lọc tự nhiên trong 30 giây (KHÔNG ÉP LÁ TRÀ).", "Lưới lọc trà, bình giữ nhiệt", "Lọc tự nhiên 30 giây", "Không đè, ép xác trà tránh bị chát đắng."),
        ("Bước 6", "Khuấy tan đá & Đóng tem", "Khuấy đều cho đến khi đá tan hết. Đóng nắp bình giữ nhiệt lại chờ dùng. In và dán tem hạn sử dụng chuẩn hóa.", "Phới khuấy, máy in tem nhãn", "Khuấy tan hoàn toàn", "• Bình giữ nhiệt: ĐỔ BỎ CUỐI NGÀY\n• Đậy nắp trong tủ lạnh: ĐỔ BỎ CUỐI NGÀY")
    ]
    for r_idx, step in enumerate(steps_tra, 17):
        for c_idx, val in enumerate(step, 1):
            cell = ws3.cell(row=r_idx, column=c_idx, value=val)
            cell.font = regular_font
            if c_idx in (1, 4, 5):
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            cell.border = cell_border
        ws3.row_dimensions[r_idx].height = 42

    # Phần Lưu ý cốt lõi
    ws3.merge_cells("A24:F24")
    ws3["A24"] = "4. CÁC LƯU Ý QUAN TRỌNG KHI Ủ TRÀ XANH SÂN SAU"
    ws3["A24"].font = bold_font
    ws3["A24"].fill = yellow_note_fill
    ws3["A24"].border = cell_border
    ws3.row_dimensions[24].height = 24

    notes_tra = [
        "1. KHUẤY TRÀ SẼ KHIẾN NƯỚC TRÀ BỊ CHÁT: Trong suốt quá trình ủ tuyệt đối không dùng que/phới khuấy đảo lá trà.",
        "2. KHI HẾT GIỜ Ủ CẦN LỌC TRÀ NGAY, KHÔNG ĐỂ LÂU, KHÔNG ÉP LÁ TRÀ: Để tránh nước trà bị đắng gắt và chát nồng.",
        "3. Ủ TRÀ BẰNG BÌNH ĐONG 5000ML, KHÔNG Ủ TRÀ BẰNG XÔ INOX: Do xô inox tản nhiệt nhanh làm tụt nhiệt độ chuẩn ủ trà."
    ]
    for idx, n in enumerate(notes_tra, 25):
        ws3.merge_cells(f"A{idx}:F{idx}")
        ws3[f"A{idx}"] = n
        ws3[f"A{idx}"].font = regular_font
        ws3[f"A{idx}"].border = cell_border
        ws3.row_dimensions[idx].height = 22

    ws3.column_dimensions['A'].width = 12
    ws3.column_dimensions['B'].width = 24
    ws3.column_dimensions['C'].width = 46
    ws3.column_dimensions['D'].width = 28
    ws3.column_dimensions['E'].width = 24
    ws3.column_dimensions['F'].width = 44


    # -------------------------------------------------------------
    # SHEET 4: NGUYÊN VẬT LIỆU & HẠN SỬ DỤNG (Images 3 & 4)
    # -------------------------------------------------------------
    ws4 = wb.create_sheet(title="Nguyen_Vat_Lieu_Va_HSD")
    ws4.views.sheetView[0].showGridLines = True

    # Title
    ws4.merge_cells("A1:F1")
    ws4["A1"] = "BÀI HỌC SẢN PHẨM DÒNG CAM - NHẬN BIẾT NGUYÊN VẬT LIỆU & HẠN SỬ DỤNG (HSD)"
    ws4["A1"].font = title_font
    ws4["A1"].fill = red_title_fill
    ws4["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws4.row_dimensions[1].height = 40

    # Bảng 1: Nguyên vật liệu pha chế
    ws4.merge_cells("A3:F3")
    ws4["A3"] = "I. NGUYÊN VẬT LIỆU PHA CHẾ, TOPPING & CỐT NƯỚC"
    ws4["A3"].font = section_font
    ws4["A3"].fill = blue_header
    ws4["A3"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws4.row_dimensions[3].height = 28

    headers_nvl = ["STT", "Phân loại", "Tên nguyên vật liệu", "Dạng sản phẩm / Quy cách", "Hạn sử dụng (HSD)", "Ghi chú bảo quản & Sử dụng"]
    for c_idx, h in enumerate(headers_nvl, 1):
        cell = ws4.cell(row=4, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = blue_light_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws4.row_dimensions[4].height = 26

    nvl_data = [
        (1, "Trà cốt thô", "Hồng trà", "Gói túi zip / bao", "18 tháng", "Bảo quản nơi khô ráo, thoáng mát"),
        (2, "Trà cốt pha sẵn", "Nước Hồng trà", "Bán thành phẩm bình giữ nhiệt", "Đổ bỏ cuối ngày", "Ủ từ lá hồng trà sân sau"),
        (3, "Trà cốt thô", "Trà xanh", "Gói 60g chuẩn", "18 tháng", "Bảo quản kín khí sau khi mở"),
        (4, "Trà cốt pha sẵn", "Nước trà xanh", "Bán thành phẩm bình giữ nhiệt", "Đổ bỏ cuối ngày", "Ủ từ lá trà xanh sân sau"),
        (5, "Bột pha chế", "Bột trà sữa", "Bao đóng kín", "12 tháng", "Dùng nấu cốt trà sữa"),
        (6, "Cốt trà pha sẵn", "Trà sữa lạnh", "Bán thành phẩm bình đong", "Theo quy định / Đổ bỏ cuối ngày", "Bảo quản ngăn mát tủ lạnh"),
        (7, "Sữa / Béo", "Sữa đặc", "Lon / Hộp có nắp", "Xem nhãn trên lon", "Đậy kín bảo quản lạnh sau khi mở"),
        (8, "Bột pha chế", "Bột pudding", "Gói túi", "12 tháng", "Dùng nấu pudding trứng/sữa"),
        (9, "Topping", "Thạch đào", "Hộp / Khay inox topping", "Xem chi tiết bảng HSD nguyên liệu", "Bảo quản quầy topping"),
        (10, "Topping", "Thạch đường đen", "Hộp / Khay inox topping", "Xem chi tiết bảng HSD nguyên liệu", "Bảo quản quầy topping"),
        (11, "Kem", "Kem nguyên vị", "Bán thành phẩm máy kem / bình đong", "Đổ bỏ cuối ngày", "Đổ bỏ cuối ngày ở cả máy kem và bình đong"),
        (12, "Bột pha chế", "Bột kem nguyên vị", "Bao đóng kín", "12 tháng", "Bột nền làm kem tươi"),
        (13, "Topping thô", "Trân châu (chưa nấu)", "Túi hút chân không", "6 tháng", "Bảo quản khô ráo, không để ẩm"),
        (14, "Topping nấu sẵn", "Trân châu nguyên vị (đã nấu)", "Khay ủ trân châu ấm", "4 giờ", "Sau 4 giờ trân châu bị lại hạt, bắt buộc đổ bỏ"),
        (15, "Đường / Ngọt", "Đường mật", "Can / Bình chiết", "24 tháng", "Đường syrup nền pha chế"),
        (16, "Đường / Ngọt", "Đường quả (Fructose)", "Can / Chai chiết vàng", "9 tháng", "Tăng độ tươi trái cây"),
        (17, "Syrup / Sốt", "Syrup đường đen", "Chai chiết", "9 tháng", "Tạo vân ly và vị đường đen"),
        (18, "Syrup / Sốt", "Syrup socola", "Chai chiết", "9 tháng", "Tạo sốt socola"),
        (19, "Syrup / Sốt", "Syrup hạt dẻ và bơ", "Chai chiết", "9 tháng", "Hương caramel hạt dẻ"),
        (20, "Topping khô", "Vụn bánh oreo", "Gói túi màu xanh", "12 tháng", "Đậy kín tránh ỉu, hút ẩm"),
        (21, "Mứt quả", "Mứt xoài", "Hộp lon thiếc", "12 tháng", "Bảo quản kín sau khi khui"),
        (22, "Mứt quả", "Mứt đào vàng", "Hộp lon thiếc", "12 tháng", "Bảo quản kín sau khi khui"),
        (23, "Mứt quả", "Mứt dâu tây", "Hộp lon thiếc", "12 tháng", "Bảo quản kín sau khi khui"),
        (24, "Mứt quả", "Mứt đào mật", "Hộp lon thiếc", "12 tháng", "Bảo quản kín sau khi khui"),
        (25, "Trái cây tươi", "Chanh vàng", "Quả tươi nguyên quả", "Quan sát vỏ ngoài và ruột sau cắt", "Rửa sạch vỏ, cắt lát trong ngày"),
        (26, "Vỏ bánh kem", "Vỏ ốc quế", "Thùng / Bọc bọc kín", "6 tháng", "Bảo quản kín chống ẩm, giữ độ giòn")
    ]

    r_idx = 5
    for item in nvl_data:
        stt, cat, name, qc, hsd, note = item
        ws4.cell(row=r_idx, column=1, value=stt).alignment = Alignment(horizontal="center", vertical="center")
        ws4.cell(row=r_idx, column=2, value=cat).alignment = Alignment(horizontal="center", vertical="center")
        ws4.cell(row=r_idx, column=3, value=name).alignment = Alignment(horizontal="left", vertical="center")
        ws4.cell(row=r_idx, column=4, value=qc).alignment = Alignment(horizontal="left", vertical="center")
        ws4.cell(row=r_idx, column=5, value=hsd).alignment = Alignment(horizontal="center", vertical="center")
        ws4.cell(row=r_idx, column=6, value=note).alignment = Alignment(horizontal="left", vertical="center")

        for c_idx in range(1, 7):
            cell = ws4.cell(row=r_idx, column=c_idx)
            cell.border = cell_border
            cell.font = bold_font if c_idx == 3 else regular_font
            if r_idx % 2 == 1:
                cell.fill = light_gray_fill
        ws4.row_dimensions[r_idx].height = 22
        r_idx += 1

    # Bảng 2: Bao bì, Dụng cụ tiêu hao & Nguồn nước
    r_idx += 2
    ws4.merge_cells(f"A{r_idx}:F{r_idx}")
    ws4[f"A{r_idx}"] = "II. BAO BÌ, VẬT TƯ TIÊU HAO & QUY ĐỊNH NGUỒN NƯỚC"
    ws4[f"A{r_idx}"].font = section_font
    ws4[f"A{r_idx}"].fill = dark_red_fill
    ws4[f"A{r_idx}"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws4.row_dimensions[r_idx].height = 28
    r_idx += 1

    headers_bb = ["STT", "Phân loại", "Tên vật tư / Bao bì", "Quy cách đóng gói", "Hạn sử dụng (HSD)", "Mục đích & Quy định sử dụng"]
    for c_idx, h in enumerate(headers_bb, 1):
        cell = ws4.cell(row=r_idx, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = red_tbl_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws4.row_dimensions[r_idx].height = 26
    r_idx += 1

    packaging_data = [
        (1, "Vật tư dùng 1 lần", "Thìa nhựa", "Bọc màng riêng từng cái", "2 năm", "Dùng cho kem sundae, sữa lắc, đồ ăn kèm"),
        (2, "Vật tư dùng 1 lần", "Ống hút nhỏ", "Bọc màng riêng từng cái", "2 năm", "Dùng cho trà hoa quả, nước chanh, đồ không topping to"),
        (3, "Vật tư dùng 1 lần", "Ống hút to", "Bọc màng riêng từng cái", "2 năm", "Dùng cho trà sữa trân châu, trà có nhiều thạch"),
        (4, "Bao bì mang về", "Túi đơn", "Túi chữ T / Túi 1 ly Mixue", "2 năm", "Đựng 1 ly mang về cho khách"),
        (5, "Bao bì lót", "Giấy lót ốc quế", "Xấp giấy hình nón in logo", "2 năm", "Lót bên ngoài vỏ ốc quế đảm bảo vệ sinh"),
        (6, "Cốc đựng", "Cốc 400 / U", "Thùng cây cốc đáy bầu tròn", "2 năm", "Dùng đựng kem lucky sundae, sữa thạch nhỏ"),
        (7, "Cốc đựng", "Cốc 500 (Size M)", "Thùng cây cốc dáng thẳng 500ml", "2 năm", "Dùng đựng trà sữa, trà hoa quả size vừa"),
        (8, "Cốc đựng", "Cốc 700 (Size L)", "Thùng cây cốc dáng cao 700ml", "2 năm", "Dùng đựng trà đào bigsize, trà chanh, trà sữa L"),
        (9, "Nguồn nước", "Nước thải máy làm đá & thiết bị", "Đường ống xả thải", "KHÔNG ĐƯỢC DÙNG", "Nước thải xả từ máy đá/thiết bị TUYỆT ĐỐI không sử dụng."),
        (10, "Nguồn nước", "Nước lọc tinh khiết pha chế", "Hệ thống lọc RO / Đun sôi", "Kiểm định định kỳ", "Dùng trực tiếp pha trà, làm kem, làm đá vệ sinh.")
    ]

    for item in packaging_data:
        stt, cat, name, qc, hsd, note = item
        ws4.cell(row=r_idx, column=1, value=stt).alignment = Alignment(horizontal="center", vertical="center")
        ws4.cell(row=r_idx, column=2, value=cat).alignment = Alignment(horizontal="center", vertical="center")
        ws4.cell(row=r_idx, column=3, value=name).alignment = Alignment(horizontal="left", vertical="center")
        ws4.cell(row=r_idx, column=4, value=qc).alignment = Alignment(horizontal="left", vertical="center")
        ws4.cell(row=r_idx, column=5, value=hsd).alignment = Alignment(horizontal="center", vertical="center")
        ws4.cell(row=r_idx, column=6, value=note).alignment = Alignment(horizontal="left", vertical="center")

        for c_idx in range(1, 7):
            cell = ws4.cell(row=r_idx, column=c_idx)
            cell.border = cell_border
            cell.font = bold_font if c_idx == 3 else regular_font
            if r_idx % 2 == 1:
                cell.fill = light_gray_fill
            if "KHÔNG ĐƯỢC DÙNG" in str(hsd):
                cell.fill = PatternFill(start_color="FFD2D2", end_color="FFD2D2", fill_type="solid")
                cell.font = Font(name=font_family, size=10, bold=True, color="9C0006")
        ws4.row_dimensions[r_idx].height = 22
        r_idx += 1

    ws4.column_dimensions['A'].width = 8
    ws4.column_dimensions['B'].width = 20
    ws4.column_dimensions['C'].width = 30
    ws4.column_dimensions['D'].width = 32
    ws4.column_dimensions['E'].width = 26
    ws4.column_dimensions['F'].width = 46

    # Save workbook
    output_path = r"c:\Users\Admin\OneDrive\Desktop\DATN\AI-Agent_mixue\Bang_Du_Lieu_Mixue.xlsx"
    wb.save(output_path)
    print(f"Workbook successfully saved to: {output_path}")

if __name__ == "__main__":
    create_mixue_workbook()
