# -*- coding: utf-8 -*-
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def build_complete_workbook():
    wb = openpyxl.Workbook()
    wb.remove(wb.active) # Remove default sheet

    # Fonts
    font_family = "Segoe UI"
    title_font = Font(name=font_family, size=14, bold=True, color="FFFFFF")
    section_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
    tbl_header_font = Font(name=font_family, size=10, bold=True, color="FFFFFF")
    bold_font = Font(name=font_family, size=10, bold=True, color="000000")
    regular_font = Font(name=font_family, size=10, color="000000")
    italic_font = Font(name=font_family, size=9, italic=True, color="4B5563")
    code_font = Font(name="Consolas", size=10, bold=True, color="9C0006")

    # Fills
    mixue_red = PatternFill(start_color="D92525", end_color="D92525", fill_type="solid")
    dark_red = PatternFill(start_color="A81818", end_color="A81818", fill_type="solid")
    header_red = PatternFill(start_color="E04343", end_color="E04343", fill_type="solid")
    blue_header = PatternFill(start_color="1E88E5", end_color="1E88E5", fill_type="solid")
    blue_light = PatternFill(start_color="29B6F6", end_color="29B6F6", fill_type="solid")
    light_pink = PatternFill(start_color="FDEDEC", end_color="FDEDEC", fill_type="solid")
    light_gray = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFF9E6", end_color="FFF9E6", fill_type="solid")
    orange_fill = PatternFill(start_color="FFEAD2", end_color="FFEAD2", fill_type="solid")
    green_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    sub_title_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")

    # Borders
    thin_side = Side(style='thin', color='C4C4C4')
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    def set_sheet_defaults(ws):
        ws.views.sheetView[0].showGridLines = True

    # =========================================================================
    # 1. SHEET: SanTruoc_Dong_Kem (Bảng công thức dòng kem ①)
    # =========================================================================
    ws_kem = wb.create_sheet(title="SanTruoc_Dong_Kem")
    set_sheet_defaults(ws_kem)

    ws_kem.merge_cells("A1:G1")
    ws_kem["A1"] = "BẢNG CÔNG THỨC DÒNG KEM SÂN TRƯỚC ① (25/5/2026)"
    ws_kem["A1"].font = title_font
    ws_kem["A1"].fill = mixue_red
    ws_kem["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_kem.row_dimensions[1].height = 38

    headers_k = ["Phân loại", "Tên sản phẩm", "Số vòng", "Loại cốc", "Khối lượng / Thao tác kem", "Đường / Topping lót đáy", "Mứt quả / Topping phủ trên"]
    for c_idx, h in enumerate(headers_k, 1):
        cell = ws_kem.cell(row=3, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = header_red
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_kem.row_dimensions[3].height = 26

    data_kem = [
        ("Dòng kem", "Kem ốc quế", "3.5 vòng", "Vỏ ốc quế", "Đánh kem vòng quanh miệng ốc quế 120±10g (tính cả vỏ ốc quế), kéo đỉnh nhọn ở giữa", "-", "-"),
        ("Dòng sundae", "Super sundae trân châu đường đen", "5.5 vòng", "Cốc chữ U", "Kem tươi 180±10g (không tính cốc)", "Đường đen 10g (0.5 lần ép) quét quanh thành cốc", "Trân châu nguyên vị 80g (2 muôi thủng)"),
        ("Dòng sundae", "Super sundae xoài", "5.5 vòng", "Cốc chữ U", "Kem tươi 180±10g (không tính cốc)", "-", "Mứt xoài 50g (2 thìa nhựa)"),
        ("Dòng sundae", "Super sundae đào hồng", "5.5 vòng", "Cốc chữ U", "Kem tươi 180±10g (không tính cốc)", "-", "Mứt đào mật 25g (1 thìa) + Trân châu trắng 50g (2 thìa)"),
        ("Dòng sundae", "Super sundae đào vàng", "5.5 vòng", "Cốc chữ U", "Kem tươi 180±10g (không tính cốc)", "-", "Mứt đào vàng 25g (1 thìa) + Thạch dừa 50g (2 thìa)"),
        ("Dòng sundae", "Lucky sundae O-coco", "3.5 vòng", "Cốc chữ U", "Kem tươi 120±10g (không tính cốc)", "Vụn ốc quế 14g (2 thìa nhựa lót đáy)", "Sốt Socola 10g (0.5 lần ép) + Vụn Oreo 16g (2 thìa nhựa)"),
        ("Dòng sundae", "Lucky sundae dâu tây", "3.5 vòng", "Cốc chữ U", "Kem tươi 120±10g (không tính cốc)", "Vụn ốc quế 14g (2 thìa nhựa lót đáy)", "Mứt dâu tây 25g (1 thìa nhựa)"),
        ("Dòng sundae", "Super sundae O-coco", "5.5 vòng", "Cốc chữ U", "Kem tươi 180±10g (không tính cốc)", "-", "Sốt Socola 10g (0.5 lần ép) + Vụn Oreo 16g (2 thìa nhựa)"),
        ("Dòng sundae", "Super sundae dâu tây", "5.5 vòng", "Cốc chữ U", "Kem tươi 180±10g (không tính cốc)", "-", "Mứt dâu tây 50g (2 thìa nhựa)")
    ]

    r_idx = 4
    for row in data_kem:
        for c_idx, val in enumerate(row, 1):
            cell = ws_kem.cell(row=r_idx, column=c_idx, value=val)
            cell.font = bold_font if c_idx in (2, 4) else regular_font
            cell.border = cell_border
            if c_idx in (1, 3, 4):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if r_idx % 2 == 1:
                cell.fill = light_gray
        ws_kem.row_dimensions[r_idx].height = 26
        r_idx += 1

    r_idx += 1
    ws_kem.merge_cells(f"A{r_idx}:G{r_idx}")
    ws_kem[f"A{r_idx}"] = "LƯU Ý QUAN TRỌNG KHI PHA CHẾ DÒNG KEM & SUNDAE"
    ws_kem[f"A{r_idx}"].font = bold_font
    ws_kem[f"A{r_idx}"].fill = yellow_fill
    ws_kem[f"A{r_idx}"].border = cell_border
    r_idx += 1

    notes_kem = [
        "1. Dòng sản phẩm kem cần tuân thủ đúng thứ tự thao tác theo bảng công thức, không được tự ý thay đổi thứ tự thêm nguyên liệu.",
        "2. Lucky sundae: Vụn ốc quế có thể thay thế bằng: Trân châu nguyên vị 40g (1 muôi thủng) / Thạch đường đen 40g (1 muôi) / Thạch đào 40g (1 muôi) tùy yêu cầu khách hàng.",
        "3. Độ nở của kem bị ảnh hưởng bởi nhiều yếu tố, số vòng kem chỉ mang tính tham khảo, bắt buộc phải căn cứ theo KHỐI LƯỢNG THỰC TẾ (cân).",
        "4. Kích thước vụn ốc quế chuẩn: từ 1x1cm đến 3x3cm. Tuyệt đối không dùng mảnh quá vụn nát (<1x1cm) hoặc quá to (>3x3cm)."
    ]
    for n in notes_kem:
        ws_kem.merge_cells(f"A{r_idx}:G{r_idx}")
        ws_kem[f"A{r_idx}"] = n
        ws_kem[f"A{r_idx}"].font = regular_font
        ws_kem[f"A{r_idx}"].border = cell_border
        ws_kem.row_dimensions[r_idx].height = 22
        r_idx += 1

    ws_kem.column_dimensions['A'].width = 16
    ws_kem.column_dimensions['B'].width = 30
    ws_kem.column_dimensions['C'].width = 12
    ws_kem.column_dimensions['D'].width = 14
    ws_kem.column_dimensions['E'].width = 38
    ws_kem.column_dimensions['F'].width = 34
    ws_kem.column_dimensions['G'].width = 38

    # =========================================================================
    # 2. SHEET: SanTruoc_Tra_Sua (Bảng công thức dòng trà sữa ②)
    # =========================================================================
    ws_ts = wb.create_sheet(title="SanTruoc_Tra_Sua")
    set_sheet_defaults(ws_ts)

    ws_ts.merge_cells("A1:G1")
    ws_ts["A1"] = "BẢNG CÔNG THỨC DÒNG TRÀ SỮA SÂN TRƯỚC ② (25/5/2026)"
    ws_ts["A1"].font = title_font
    ws_ts["A1"].fill = mixue_red
    ws_ts["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_ts.row_dimensions[1].height = 38

    headers_ts = ["Nhóm", "Tên sản phẩm", "Nhiệt độ", "Cỡ cốc", "Đường / Kem", "Topping", "Mứt quả & Nước cốt / Trà sữa lạnh"]
    for c_idx, h in enumerate(headers_ts, 1):
        cell = ws_ts.cell(row=3, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = header_red
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_ts.row_dimensions[3].height = 26

    data_ts = [
        # Trà hoa nhài & Sữa thạch
        ("Trà hoa / Sữa", "Trà sữa hoa nhài", "Đá", "Cốc 500", "Đường mật 30g (1.5 thìa nhựa)", "Trân châu trắng 50g (2 thìa nhựa)", "Thêm đá, Sữa đặc 80ml, Trà xanh 180ml"),
        ("Trà hoa / Sữa", "Trà sữa hoa nhài", "Ấm", "Cốc 500", "Đường mật 30g (1.5 thìa nhựa)", "Trân châu trắng 50g (2 thìa nhựa)", "Sữa đặc 80ml, Trà xanh 180ml, Thêm nước nóng đến cách miệng cốc 0.8cm"),
        ("Trà hoa / Sữa", "Sữa thạch dâu tây", "Dưới đá / Đúng đá", "Cốc 500", "Đường mật 20g (1 thìa nhựa)", "Thạch đào 80g (2 muôi thủng)", "Mứt dâu tây 75g (3 thìa) | Thêm đá, Sữa đặc 60ml, Thêm nước lọc đến cách miệng 0.8cm"),
        ("Trà hoa / Sữa", "Dương chi cam lộ", "Đá", "Cốc 500", "Kem 110±10g (3.5 vòng)", "T.dừa 25g (1 thìa) + T.đào 40g (1 muôi) + TC.đen 40g (1 muôi)", "Mứt xoài 75g (3 thìa) | Thêm đá & Thêm nước lọc đến cách miệng cốc 0.8cm"),
        # Dòng Trà sữa Cốc 500
        ("Trà sữa (500ml)", "Trà sữa trân châu đường đen", "Dưới đá / Đúng đá", "Cốc 500", "Đường đen 30g (1.5 lần ép) quét quanh cốc", "Trân châu nguyên vị 80g (2 muôi thủng)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (500ml)", "Trà sữa caramel", "Dưới đá / Đúng đá", "Cốc 500", "Syrup hạt dẻ bơ 40g (2 lần ép)", "Thạch đường đen 80g (2 muôi thủng)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (500ml)", "Trà sữa trân châu", "Dưới đá / Đúng đá", "Cốc 500", "Đường mật 30g (1.5 thìa nhựa)", "Trân châu nguyên vị 80g (2 muôi thủng)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (500ml)", "Trà sữa thạch dừa", "Dưới đá / Đúng đá", "Cốc 500", "Đường mật 30g (1.5 thìa nhựa)", "Thạch dừa 50g (2 thìa nhựa)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (500ml)", "Trà sữa thạch đường đen", "Dưới đá / Đúng đá", "Cốc 500", "Đường mật 30g (1.5 thìa nhựa)", "Thạch đường đen 80g (2 muôi thủng)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (500ml)", "Trà sữa 2J", "Dưới đá / Đúng đá", "Cốc 500", "Đường mật 30g (1.5 thìa nhựa)", "Thạch dừa 50g (2 thìa) + Thạch đường đen 80g (2 muôi)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (500ml)", "Trà sữa O-coco", "Dưới đá / Đúng đá", "Cốc 500", "Đường mật 10g + Socola 40g (2 lần ép) quét quanh cốc", "Vụn Oreo 8g (1 thìa) + Thạch đường đen 80g (2 muôi)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        # Dòng Trà sữa Cốc 700 (Size L)
        ("Trà sữa (700ml)", "Trà sữa Bá Vương", "Dưới đá / Đúng đá", "Cốc 700", "Đường mật 30g (1.5 thìa nhựa)", "Trân châu 80g (2 muôi) + T.đen 80g (2 muôi) + T.dừa 50g (2 thìa)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (700ml)", "Trà sữa trân châu (size L)", "Dưới đá / Đúng đá", "Cốc 700", "Đường mật 30g (1.5 thìa nhựa)", "Trân châu nguyên vị 160g (4 muôi thủng)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (700ml)", "Trà sữa thạch dừa (size L)", "Dưới đá / Đúng đá", "Cốc 700", "Đường mật 30g (1.5 thìa nhựa)", "Thạch dừa 150g (6 thìa nhựa)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (700ml)", "Trà sữa thạch đường đen (size L)", "Dưới đá / Đúng đá", "Cốc 700", "Đường mật 30g (1.5 thìa nhựa)", "Thạch đường đen 160g (4 muôi thủng)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm"),
        ("Trà sữa (700ml)", "Trà sữa 2J (size L)", "Dưới đá / Đúng đá", "Cốc 700", "Đường mật 30g (1.5 thìa nhựa)", "Thạch dừa 75g (3 thìa) + Thạch đường đen 120g (3 muôi)", "Thêm đá, Rót trà sữa lạnh đến cách miệng cốc 0.8cm")
    ]

    r_idx = 4
    for row in data_ts:
        for c_idx, val in enumerate(row, 1):
            cell = ws_ts.cell(row=r_idx, column=c_idx, value=val)
            cell.font = bold_font if c_idx == 2 else regular_font
            cell.border = cell_border
            if c_idx in (1, 3, 4):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if r_idx % 2 == 1:
                cell.fill = light_gray
        ws_ts.row_dimensions[r_idx].height = 26
        r_idx += 1

    r_idx += 1
    ws_ts.merge_cells(f"A{r_idx}:G{r_idx}")
    ws_ts[f"A{r_idx}"] = "LƯU Ý QUAN TRỌNG KHI PHA CHẾ DÒNG TRÀ SỮA"
    ws_ts[f"A{r_idx}"].font = bold_font
    ws_ts[f"A{r_idx}"].fill = yellow_fill
    ws_ts[f"A{r_idx}"].border = cell_border
    r_idx += 1

    notes_ts = [
        "1. Trà sữa hoa nhài mức nhiệt đá KHÔNG THÊM NƯỚC LỌC; nếu chưa đến cách miệng 0.8cm thì thêm đá, nếu đầy quá vớt bớt đá ra.",
        "2. Các sản phẩm quét thành cốc (Trà sữa trân châu đường đen, Trà sữa O-coco): KHÔNG lắc cốc khi trả đồ, nhắc khách lắc đều trước khi uống.",
        "3. Trà sữa 2J size M: Khách được chọn 2 trong 3 loại topping: TC nguyên vị 40g (1 muôi) / Thạch dừa 50g (2 thìa) / Thạch đường đen 40g (1 muôi).",
        "4. Trà sữa 2J size L: Khách được chọn 2 trong 3 loại topping: TC nguyên vị 120g (3 muôi) / Thạch dừa 75g (3 thìa) / Thạch đường đen 120g (3 muôi)."
    ]
    for n in notes_ts:
        ws_ts.merge_cells(f"A{r_idx}:G{r_idx}")
        ws_ts[f"A{r_idx}"] = n
        ws_ts[f"A{r_idx}"].font = regular_font
        ws_ts[f"A{r_idx}"].border = cell_border
        ws_ts.row_dimensions[r_idx].height = 22
        r_idx += 1

    ws_ts.column_dimensions['A'].width = 18
    ws_ts.column_dimensions['B'].width = 28
    ws_ts.column_dimensions['C'].width = 16
    ws_ts.column_dimensions['D'].width = 12
    ws_ts.column_dimensions['E'].width = 34
    ws_ts.column_dimensions['F'].width = 38
    ws_ts.column_dimensions['G'].width = 46

    # =========================================================================
    # 3. SHEET: SanTruoc_Tra_Hoa_Qua (Bảng công thức dòng trà hoa quả ③)
    # =========================================================================
    ws_hq = wb.create_sheet(title="SanTruoc_Tra_Hoa_Qua")
    set_sheet_defaults(ws_hq)

    ws_hq.merge_cells("A1:H1")
    ws_hq["A1"] = "BẢNG CÔNG THỨC DÒNG TRÀ HOA QUẢ SÂN TRƯỚC ③ (25/5/2026)"
    ws_hq["A1"].font = title_font
    ws_hq["A1"].fill = mixue_red
    ws_hq["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_hq.row_dimensions[1].height = 38

    headers_hq = ["Nhóm", "Tên sản phẩm", "Nhiệt độ", "Cốc", "Trái cây tươi", "Đường", "Topping / Mứt quả", "Trà / Nước lọc / Nước nóng"]
    for c_idx, h in enumerate(headers_hq, 1):
        cell = ws_hq.cell(row=3, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = header_red
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_hq.row_dimensions[3].height = 26

    data_hq = [
        ("Trà hoa quả", "Trà đào bigsize", "Dưới đá / Đúng đá", "Cốc 700", "-", "Đường mật 40g (2 thìa)", "Thạch đào 120g (3 muôi) | Mứt đào vàng 100g (4 thìa)", "Thêm đá, Hồng trà 100ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà xanh hoa đào", "Dưới đá / Đúng đá", "Cốc 700", "-", "Đường mật 40g (2 thìa)", "Thạch đào 120g (3 muôi) | Mứt đào mật 75g (3 thìa)", "Thêm đá, Trà xanh 120ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Chanh leo bách hương", "Dưới đá / Đúng đá", "Cốc 700", "-", "Đường mật 20g (1 thìa)", "Thạch dừa 50g (2 thìa) + TC.đen 40g (1 muôi) | Mứt C.leo 50g (2 thìa)", "Thêm đá, Trà xanh 120ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Chanh leo bách hương", "Ấm", "Cốc 700", "-", "Đường mật 20g (1 thìa)", "Thạch dừa 50g (2 thìa) + TC.đen 40g (1 muôi) | Mứt C.leo 50g (2 thìa)", "Nước lọc đến vạch 7, Thêm nước nóng đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà xoài chanh leo", "Dưới đá / Đúng đá", "Cốc 700", "-", "Đường mật 40g (2 thìa)", "Thạch dừa 50g (2 thìa) | Mứt C.leo 25g (1 thìa) + Mứt xoài 50g (2 thìa)", "Thêm đá, Trà xanh 120ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà dâu dâu tây", "Dưới đá / Đúng đá", "Cốc 700", "-", "Đường mật 40g (2 thìa)", "Trân châu trắng 50g (2 thìa) | Mứt dâu 75g (3 thìa) + Đào mật 25g (1 thìa)", "Thêm đá, Trà xanh 120ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà cam đào tây", "Dưới đá / Đúng đá", "Cốc 700", "Cam cắt lát 40g (ép nước cốt)", "Đường mật 40g (2 thìa)", "Mứt đào tây 100g (4 thìa nhựa)", "Thêm đá, Trà xanh 120ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà cam đào tây", "Ấm", "Cốc 700", "Cam cắt lát 40g (ép nước cốt)", "Đường mật 40g (2 thìa)", "Mứt đào tây 100g (4 thìa nhựa)", "Nước lọc đến vạch 7, Thêm nước nóng đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà cam vàng tươi", "Dưới đá / Đúng đá", "Cốc 700", "Cam cắt lát 40g (ép nước cốt)", "Đường mật 40g (2 thìa)", "Mứt cam tươi 50g (2 thìa nhựa)", "Thêm đá, Trà xanh 120ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà cam vàng tươi", "Ấm", "Cốc 700", "Cam cắt lát 40g (ép nước cốt)", "Đường mật 40g (2 thìa)", "Mứt cam tươi 50g (2 thìa nhựa)", "Nước lọc đến vạch 7, Thêm nước nóng đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà xanh kiwi", "Dưới đá / Đúng đá", "Cốc 700", "-", "Đường mật 40g + Đường quả 20g", "Thạch dừa 50g (2 thìa) | Mứt kiwi 75g (3 thìa)", "Thêm đá, Trà xanh 120ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà xanh kiwi", "Ấm", "Cốc 700", "-", "Đường mật 40g + Đường quả 20g", "Thạch dừa 50g (2 thìa) | Mứt kiwi 75g (3 thìa)", "Nước lọc đến vạch 7, Thêm nước nóng đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà chanh lô hội", "Dưới đá / Đúng đá", "Cốc 700", "Chanh cắt lát 40g (KHÔNG GIÃ)", "Đường mật 70g (3.5 thìa)", "Thạch dừa 25g (1 thìa) + Lô hội 50g (2 thìa)", "Thêm đá, Hồng trà lạnh 140ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Nước chanh tươi lạnh", "Dưới đá / Đúng đá", "Cốc 700", "Chanh cắt lát 40g (giã ra nước)", "Đường quả 55g (2.7 thìa)", "-", "Thêm đá, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà hoa quả", "Trà xanh chanh", "Dưới đá / Đúng đá", "Cốc 700", "Chanh cắt lát 40g (giã ra nước)", "Đường mật 30g + Đường quả 40g", "-", "Thêm đá, Trà xanh 160ml, Nước lọc đến cách miệng cốc 0.8cm"),
        ("Trà nguyên vị", "Trà nhài mật ong", "Đá / Ấm / Nóng", "Cốc 700", "-", "Đường mật 45g (2.2 thìa)", "-", "Thêm đá (nếu uống đá), Trà xanh 240ml, Nước lọc/nóng đến cách miệng 0.8cm"),
        ("Trà nguyên vị", "Hồng trà mật ong", "Đá / Ấm / Nóng", "Cốc 700", "-", "Đường mật 45g (2.2 thìa)", "-", "Thêm đá (nếu uống đá), Hồng trà lạnh 240ml, Nước lọc/nóng đến cách miệng 0.8cm")
    ]

    r_idx = 4
    for row in data_hq:
        for c_idx, val in enumerate(row, 1):
            cell = ws_hq.cell(row=r_idx, column=c_idx, value=val)
            cell.font = bold_font if c_idx == 2 else regular_font
            cell.border = cell_border
            if c_idx in (1, 3, 4):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if r_idx % 2 == 1:
                cell.fill = light_gray
        ws_hq.row_dimensions[r_idx].height = 26
        r_idx += 1

    r_idx += 1
    ws_hq.merge_cells(f"A{r_idx}:H{r_idx}")
    ws_hq[f"A{r_idx}"] = "LƯU Ý QUAN TRỌNG KHI PHA CHẾ DÒNG TRÀ HOA QUẢ"
    ws_hq[f"A{r_idx}"].font = bold_font
    ws_hq[f"A{r_idx}"].fill = yellow_fill
    ws_hq[f"A{r_idx}"].border = cell_border
    r_idx += 1

    notes_hq = [
        "1. Khối lượng chanh, cam cắt lát chuẩn 40±5g. Dùng chày giã dầm 8-10 lần (hoặc ép ra nước cốt đối với cam cắt lát).",
        "2. Trà chanh lô hội: Chanh cắt lát TUYỆT ĐỐI KHÔNG ĐƯỢC GIÃ, chỉ thả vào trực tiếp.",
        "3. Dòng trà nguyên vị (Trà nhài mật ong, Hồng trà mật ong): Nếu khách chọn 'không đường' thì không thêm đường.",
        "4. Pha chế mức nhiệt 'Ấm': Dùng ca lắc bật pha chế mức nhiệt Ấm, thêm nước lọc đến vạch 7 rồi thêm nước nóng đến cách miệng 0.8cm (nếu nguyên liệu đã chạm vạch 7 thì không cần thêm nước lọc)."
    ]
    for n in notes_hq:
        ws_hq.merge_cells(f"A{r_idx}:H{r_idx}")
        ws_hq[f"A{r_idx}"] = n
        ws_hq[f"A{r_idx}"].font = regular_font
        ws_hq[f"A{r_idx}"].border = cell_border
        ws_hq.row_dimensions[r_idx].height = 22
        r_idx += 1

    ws_hq.column_dimensions['A'].width = 16
    ws_hq.column_dimensions['B'].width = 25
    ws_hq.column_dimensions['C'].width = 18
    ws_hq.column_dimensions['D'].width = 12
    ws_hq.column_dimensions['E'].width = 28
    ws_hq.column_dimensions['F'].width = 30
    ws_hq.column_dimensions['G'].width = 46
    ws_hq.column_dimensions['H'].width = 46

    # =========================================================================
    # 4. SHEET: SanTruoc_Ca_Phe (Bảng công thức cà phê tươi sân trước ⑤)
    # =========================================================================
    ws_cf = wb.create_sheet(title="SanTruoc_Ca_Phe")
    set_sheet_defaults(ws_cf)

    ws_cf.merge_cells("A1:H1")
    ws_cf["A1"] = "BẢNG CÔNG THỨC CÀ PHÊ TƯƠI SÂN TRƯỚC ⑤ (25/5/2026)"
    ws_cf["A1"].font = title_font
    ws_cf["A1"].fill = mixue_red
    ws_cf["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_cf.row_dimensions[1].height = 38

    headers_cf = ["Dòng sản phẩm", "Tên món", "Nhiệt độ", "Cốc", "Đường / Trái cây", "Topping / Sữa đặc / Mứt", "Cà phê tươi", "Kem tươi / Nước lọc / Nóng"]
    for c_idx, h in enumerate(headers_cf, 1):
        cell = ws_cf.cell(row=3, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = header_red
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_cf.row_dimensions[3].height = 26

    data_cf = [
        # Cà phê kem
        ("Cà phê kem", "Cafe Latte kem tươi", "Đá", "Cốc 500", "Đường mật 20g (1 thìa nhựa)", "Thạch đường đen 40g (1 muôi) | Sữa đặc 40ml", "Cà phê tươi 120ml (khuấy đều)", "Thêm đá đến vạch tim, Kem tươi 90±10g (2.5 vòng), Đóng nắp cầu"),
        ("Cà phê kem", "Americano + kem", "Đá", "Cốc 500", "-", "-", "Thêm đá đến vạch tim, Cà phê tươi 140ml, Thêm nước lọc đến vạch tim (khuấy đều)", "Kem tươi 90±10g (2.5 vòng), Đóng nắp cầu"),
        # Americano / Trái cây
        ("Americano", "Americano cam", "Đá", "Cốc 500", "Cam cắt lát 40g (ép nước) + Đường mật 20g (1 thìa)", "Mứt cam tươi 25g (1 thìa nhựa)", "Thêm đá đến cách miệng 0.8cm, Cà phê tươi 140ml", "Thêm nước lọc đến cách miệng cốc 0.8cm"),
        ("Americano", "Americano chanh", "Đá", "Cốc 500", "Chanh cắt lát 40g (không giã) + Đường mật 10g + Đường quả 30g", "-", "Thêm đá đến cách miệng 0.8cm, Cà phê tươi 140ml", "Thêm nước lọc đến cách miệng cốc 0.8cm"),
        ("Americano", "Americano", "Đá", "Cốc 500", "-", "-", "Thêm đá đến cách miệng 0.8cm, Cà phê tươi 140ml", "Thêm nước lọc đến cách miệng cốc 0.8cm"),
        ("Americano", "Americano", "Nóng", "Cốc 500", "-", "-", "Cà phê tươi 140ml", "Thêm nước nóng đến cách miệng cốc 0.8cm"),
        # Cà phê latte
        ("Cà phê latte", "Cafe Latte", "Đá", "Cốc chữ U", "Đường mật 20g (1 thìa nhựa)", "Sữa đặc 100ml (khuấy đều)", "Thêm đá đến cách miệng 0.8cm, Cà phê tươi 120ml", "-"),
        ("Cà phê latte", "Cafe Latte", "Nóng", "Cốc chữ U", "Đường mật 20g (1 thìa nhựa)", "Sữa đặc 100ml (khuấy đều)", "Cà phê tươi 120ml", "Thêm nước nóng đến cách miệng cốc 0.8cm"),
        ("Cà phê latte", "Cafe latte caramel hạt dẻ", "Đá", "Cốc chữ U", "Syrup hạt dẻ và bơ 30g (1.5 lần ép)", "Sữa đặc 100ml (khuấy đều)", "Thêm đá đến cách miệng 0.8cm, Cà phê tươi 120ml", "-"),
        ("Cà phê latte", "Cafe latte caramel hạt dẻ", "Nóng", "Cốc chữ U", "Syrup hạt dẻ và bơ 30g (1.5 lần ép)", "Sữa đặc 100ml (khuấy đều)", "Cà phê tươi 120ml", "Thêm nước nóng đến cách miệng cốc 0.8cm")
    ]

    r_idx = 4
    for row in data_cf:
        for c_idx, val in enumerate(row, 1):
            cell = ws_cf.cell(row=r_idx, column=c_idx, value=val)
            cell.font = bold_font if c_idx == 2 else regular_font
            cell.border = cell_border
            if c_idx in (1, 3, 4):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if r_idx % 2 == 1:
                cell.fill = light_gray
        ws_cf.row_dimensions[r_idx].height = 26
        r_idx += 1

    r_idx += 1
    ws_cf.merge_cells(f"A{r_idx}:H{r_idx}")
    ws_cf[f"A{r_idx}"] = "LƯU Ý QUAN TRỌNG KHI PHA CHẾ CÀ PHÊ TƯƠI SÂN TRƯỚC"
    ws_cf[f"A{r_idx}"].font = bold_font
    ws_cf[f"A{r_idx}"].fill = yellow_fill
    ws_cf[f"A{r_idx}"].border = cell_border
    r_idx += 1

    notes_cf = [
        "1. Dòng cà phê kem cần khuấy đều phần nước bên dưới bằng thìa khuấy, sau đó mới đánh kem tươi lên trên.",
        "2. Sản phẩm Americano mặc định KHÔNG ĐƯỜNG. Nếu khách hàng yêu cầu thêm đường, áp dụng tiêu chuẩn đường bình thường là 20g.",
        "3. Tiêu chuẩn pha dòng cà phê tươi: THÊM ĐÁ TRƯỚC, SAU ĐÓ MỚI THÊM CÀ PHÊ TƯƠI (giúp giữ hương vị cà phê bền lâu hơn).",
        "4. Cafe Latte, Cafe latte caramel hạt dẻ: Mức nhiệt đá KHÔNG THÊM NƯỚC; Mức nhiệt nóng KHÔNG THÊM ĐÁ mà thêm nước nóng đến cách miệng cốc 0.8cm.",
        "5. Thêm topping: Dòng 'cà phê tuyệt đỉnh' và 'cà phê latte' thêm topping theo quy định dòng cà phê; dòng 'americano/americano trái cây' thêm theo quy định dòng trà hoa quả."
    ]
    for n in notes_cf:
        ws_cf.merge_cells(f"A{r_idx}:H{r_idx}")
        ws_cf[f"A{r_idx}"] = n
        ws_cf[f"A{r_idx}"].font = regular_font
        ws_cf[f"A{r_idx}"].border = cell_border
        ws_cf.row_dimensions[r_idx].height = 22
        r_idx += 1

    ws_cf.column_dimensions['A'].width = 16
    ws_cf.column_dimensions['B'].width = 26
    ws_cf.column_dimensions['C'].width = 12
    ws_cf.column_dimensions['D'].width = 12
    ws_cf.column_dimensions['E'].width = 34
    ws_cf.column_dimensions['F'].width = 36
    ws_cf.column_dimensions['G'].width = 38
    ws_cf.column_dimensions['H'].width = 40

    # =========================================================================
    # 5. SHEET: Topping_Them_QuyDinh (Khối lượng topping thêm ⑥)
    # =========================================================================
    ws_top = wb.create_sheet(title="Topping_Them_QuyDinh")
    set_sheet_defaults(ws_top)

    ws_top.merge_cells("A1:G1")
    ws_top["A1"] = "KHỐI LƯỢNG TOPPING THÊM TRONG CÁC SẢN PHẨM ⑥ (25/5/2026)"
    ws_top["A1"].font = title_font
    ws_top["A1"].fill = mixue_red
    ws_top["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_top.row_dimensions[1].height = 38

    ws_top.merge_cells("A2:G2")
    ws_top["A2"] = "Áp dụng cho khách hàng mua thêm topping tại cửa hàng. Chỉ giới hạn cho sản phẩm mua tại chỗ/mang về, KHÔNG ÁP DỤNG cho giao ship."
    ws_top["A2"].font = italic_font
    ws_top["A2"].fill = light_pink
    ws_top["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws_top.row_dimensions[2].height = 22

    headers_top = ["STT", "Tên Topping thêm", "Dòng Sundae (g/muỗng)", "Dòng Trà Hoa Quả (g/muỗng)", "Dòng Trà Sữa (g/muỗng)", "Dòng Cà Phê (g/muỗng)", "Dụng cụ chuẩn"]
    for c_idx, h in enumerate(headers_top, 1):
        cell = ws_top.cell(row=4, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = blue_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_top.row_dimensions[4].height = 26

    topping_matrix = [
        (1, "Trân châu trắng", "25g (1 thìa nhựa)", "25g (1 thìa nhựa)", "25g (1 thìa nhựa)", "25g (1 thìa nhựa)", "Thìa nhựa đầy bằng"),
        (2, "Thạch dừa", "25g (1 thìa nhựa)", "25g (1 thìa nhựa)", "25g (1 thìa nhựa)", "25g (1 thìa nhựa)", "Thìa nhựa đầy bằng"),
        (3, "Lô hội (Nha đam)", "25g (1 thìa nhựa)", "25g (1 thìa nhựa)", "25g (1 thìa nhựa)", "25g (1 thìa nhựa)", "Thìa nhựa đầy bằng"),
        (4, "Trân châu nguyên vị (đen)", "40g (1 muôi thủng)", "40g (1 muôi thủng)", "40g (1 muôi thủng)", "40g (1 muôi thủng)", "Muôi thủng đầy bằng"),
        (5, "Thạch đào", "40g (1 muôi thủng)", "40g (1 muôi thủng)", "40g (1 muôi thủng)", "40g (1 muôi thủng)", "Muôi thủng đầy bằng"),
        (6, "Thạch đường đen", "40g (1 muôi thủng)", "40g (1 muôi thủng)", "40g (1 muôi thủng)", "40g (1 muôi thủng)", "Muôi thủng đầy bằng"),
        (7, "Vụn ốc quế", "7g (1 thìa nhựa)", "Không áp dụng", "Không áp dụng", "Không áp dụng", "Thìa nhựa đầy bằng"),
        (8, "Vụn bánh Oreo", "8g (1 thìa nhựa)", "8g (1 thìa nhựa)", "8g (1 thìa nhựa)", "8g (1 thìa nhựa)", "Thìa nhựa đầy bằng")
    ]

    r_idx = 5
    for item in topping_matrix:
        for c_idx, val in enumerate(item, 1):
            cell = ws_top.cell(row=r_idx, column=c_idx, value=val)
            cell.font = bold_font if c_idx == 2 else regular_font
            cell.border = cell_border
            if c_idx in (1, 3, 4, 5, 6, 7):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            if r_idx % 2 == 1:
                cell.fill = light_gray
        ws_top.row_dimensions[r_idx].height = 24
        r_idx += 1

    r_idx += 1
    ws_top.merge_cells(f"A{r_idx}:G{r_idx}")
    ws_top[f"A{r_idx}"] = "QUY TẮC GIẢM ĐƯỜNG BẮT BUỘC KHI KHÁCH HÀNG THÊM TOPPING"
    ws_top[f"A{r_idx}"].font = bold_font
    ws_top[f"A{r_idx}"].fill = yellow_fill
    ws_top[f"A{r_idx}"].border = cell_border
    r_idx += 1

    sugar_rules = [
        ("Giới hạn số phần", "Trừ topping có sẵn trong công thức sản phẩm, mỗi cốc CHỈ CÓ THỂ THÊM NHIỀU NHẤT 2 PHẦN TOPPING."),
        ("Khách chọn Đường 100% + 1 phần topping", "Sản phẩm sẽ tự động pha chế giảm xuống mức ĐƯỜNG 70%."),
        ("Khách chọn Đường 100% + 2 phần topping", "Sản phẩm sẽ tự động pha chế giảm xuống mức ĐƯỜNG 50%."),
        ("Khách chọn Đường 70% hoặc 50% + topping", "Sản phẩm sẽ pha chế cố định ở mức ĐƯỜNG 50%."),
        ("Khách chọn Đường 30% + topping", "Sản phẩm VẪN GIỮ NGUYÊN mức ĐƯỜNG 30% (không giảm thêm nữa).")
    ]
    for rule, desc in sugar_rules:
        ws_top.merge_cells(f"A{r_idx}:C{r_idx}")
        ws_top[f"A{r_idx}"] = rule
        ws_top[f"A{r_idx}"].font = bold_font
        ws_top[f"A{r_idx}"].border = cell_border
        ws_top[f"A{r_idx}"].fill = orange_fill
        
        ws_top.merge_cells(f"D{r_idx}:G{r_idx}")
        ws_top[f"D{r_idx}"] = desc
        ws_top[f"D{r_idx}"].font = regular_font
        ws_top[f"D{r_idx}"].border = cell_border
        ws_top.row_dimensions[r_idx].height = 24
        r_idx += 1

    ws_top.column_dimensions['A'].width = 8
    ws_top.column_dimensions['B'].width = 26
    ws_top.column_dimensions['C'].width = 22
    ws_top.column_dimensions['D'].width = 24
    ws_top.column_dimensions['E'].width = 22
    ws_top.column_dimensions['F'].width = 22
    ws_top.column_dimensions['G'].width = 24

    # =========================================================================
    # 6. SHEET: Tham_Chieu_Duong_Da_DungCu (Tham chiếu đường, đá, dụng cụ ⑦)
    # =========================================================================
    ws_tc = wb.create_sheet(title="Tham_Chieu_Duong_Da_DungCu")
    set_sheet_defaults(ws_tc)

    ws_tc.merge_cells("A1:G1")
    ws_tc["A1"] = "BẢNG THAM CHIẾU LƯỢNG ĐƯỜNG, ĐÁ VÀ TIÊU CHUẨN DỤNG CỤ ⑦ (25/5/2026)"
    ws_tc["A1"].font = title_font
    ws_tc["A1"].fill = mixue_red
    ws_tc["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_tc.row_dimensions[1].height = 38

    # Bảng 1: Lượng đường
    ws_tc.merge_cells("A3:D3")
    ws_tc["A3"] = "1. BẢNG THAM CHIẾU TIÊU CHUẨN ĐƯỜNG (Đường mật / Đường quả)"
    ws_tc["A3"].font = section_font
    ws_tc["A3"].fill = dark_red
    ws_tc["A3"].alignment = Alignment(horizontal="left", vertical="center", indent=1)

    # Bảng 2: Lượng đá
    ws_tc.merge_cells("E3:G3")
    ws_tc["E3"] = "2. BẢNG THAM CHIẾU TIÊU CHUẨN ĐÁ"
    ws_tc["E3"].font = section_font
    ws_tc["E3"].fill = blue_header
    ws_tc["E3"].alignment = Alignment(horizontal="left", vertical="center", indent=1)

    headers_sugar = ["Mức 100% (Chuẩn)", "Mức 70%", "Mức 50%", "Mức 30%"]
    for c_idx, h in enumerate(headers_sugar, 1):
        cell = ws_tc.cell(row=4, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = header_red
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = cell_border

    headers_ice = ["Cỡ cốc", "Mức bình thường (100% đá)", "Mức ít đá (70% đá)"]
    for c_idx, h in enumerate(headers_ice, 5):
        cell = ws_tc.cell(row=4, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = blue_light
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = cell_border
    ws_tc.row_dimensions[4].height = 24

    sugar_conversion = [
        (10, 7, 5, 3),
        (15, 10, 8, 5),
        (20, 14, 10, 6),
        (30, 21, 15, 9),
        (40, 28, 20, 12),
        (50, 35, 25, 15),
        (55, 40, 30, 15),
        (60, 42, 30, 18),
        (70, 50, 35, 20)
    ]
    ice_specs = [
        ("Cốc 500 (Size M)", "Cách miệng cốc 0.8cm", "Đến vạch tim"),
        ("Cốc 700 (Size L)", "Cách miệng cốc 0.8cm", "Đến vạch tim"),
        ("Cốc chữ U", "Đến vạch tim", "Dưới vạch tim 1cm")
    ]

    for idx in range(max(len(sugar_conversion), len(ice_specs))):
        r = 5 + idx
        if idx < len(sugar_conversion):
            s_row = sugar_conversion[idx]
            for c_i, v in enumerate(s_row, 1):
                cell = ws_tc.cell(row=r, column=c_i, value=f"{v}g/ml")
                cell.font = bold_font if c_i == 1 else regular_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = cell_border
                if idx % 2 == 1:
                    cell.fill = light_gray
        else:
            for c_i in range(1, 5):
                cell = ws_tc.cell(row=r, column=c_i, value="")
                cell.border = cell_border

        if idx < len(ice_specs):
            i_row = ice_specs[idx]
            for c_i, v in enumerate(i_row, 5):
                cell = ws_tc.cell(row=r, column=c_i, value=v)
                cell.font = bold_font if c_i == 5 else regular_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = cell_border
                if idx % 2 == 1:
                    cell.fill = light_gray
        else:
            for c_i in range(5, 8):
                cell = ws_tc.cell(row=r, column=c_i, value="")
                cell.border = cell_border
        ws_tc.row_dimensions[r].height = 20

    # Bảng 3: Tiêu chuẩn dụng cụ định lượng
    curr_r = 15
    ws_tc.merge_cells(f"A{curr_r}:G{curr_r}")
    ws_tc[f"A{curr_r}"] = "3. BẢNG TIÊU CHUẨN ĐỊNH LƯỢNG CỦA CÁC DỤNG CỤ PHA CHẾ"
    ws_tc[f"A{curr_r}"].font = section_font
    ws_tc[f"A{curr_r}"].fill = mixue_red
    ws_tc[f"A{curr_r}"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws_tc.row_dimensions[curr_r].height = 26
    curr_r += 1

    headers_tool = ["STT", "Tên dụng cụ", "Quy cách đong", "Khối lượng / Dung tích", "Nguyên liệu định lượng tương ứng", "Mục đích sử dụng chính", "Sai số cho phép"]
    for c_idx, h in enumerate(headers_tool, 1):
        cell = ws_tc.cell(row=curr_r, column=c_idx, value=h)
        cell.font = tbl_header_font
        cell.fill = header_red
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws_tc.row_dimensions[curr_r].height = 25
    curr_r += 1

    tools_data = [
        (1, "Thìa nhựa", "1 thìa đầy bằng", "7g", "Vụn ốc quế", "Đong topping khô rắc kem", "±1g"),
        (2, "Thìa nhựa", "1 thìa đầy bằng", "8g", "Vụn bánh Oreo", "Đong topping vụn oreo", "±1g"),
        (3, "Thìa nhựa", "1 thìa đầy bằng", "20g", "Đường mật, đường quả", "Đong đường pha chế", "±1g"),
        (4, "Thìa nhựa", "1 thìa đầy bằng", "25g", "Trân châu trắng, Thạch dừa, Mứt dâu, Mứt xoài, Đào vàng, Đào mật", "Đong topping dẻo & mứt quả", "±2g"),
        (5, "Muôi thủng inox", "1 muôi đầy bằng", "40g", "Trân châu nguyên vị (đen), Thạch đường đen, Thạch đào", "Múc topping ngâm nước/nấu", "±2g"),
        (6, "Vòi ấn chiết siro", "1 lần ép hết hành trình", "20g", "Đường đen, Syrup hạt dẻ bơ, Syrup socola", "Bơm sốt quanh thành cốc / tạo vị", "±1g"),
        (7, "Bình / Cốc đong 500ml", "Chia vạch ml", "50ml - 500ml", "Dung tích trà, trà sữa, sữa đặc, cà phê tươi", "Đong chất lỏng", "Theo vạch"),
        (8, "Chày dầm trái cây", "Thao tác dầm tay", "8 - 10 lần", "Chanh cắt lát, cam cắt lát", "Dầm lấy nước cốt tươi", "-"),
        (9, "Thìa khuấy dài", "Thao tác khuấy tròn", "-", "Khuấy tan đá, khuấy cà phê kem trước", "Hòa tan đồ uống", "-"),
        (10, "Phới lồng khuấy", "Đánh đều tay", "-", "Khuấy trà, cốt trà sữa, thạch đào, thạch đường đen, sữa đặc", "Nấu cốt & hòa tan bột sân sau", "-"),
        (11, "Lưới lọc trân châu", "Lưới ráo nước", "-", "Trân châu đen nấu chín", "Vớt ráo trân châu trước khi ủ đường", "-"),
        (12, "Lưới lọc trà inox", "Lưới mắt nhỏ", "-", "Trà xanh, hồng trà", "Lọc bã xác trà tự nhiên", "-"),
        (13, "Lưới lọc kem", "Lưới mắt siêu mịn", "-", "Kem tươi nguyên vị, cốt sữa đặc", "Loại bỏ cặn bột vón giúp cốt sánh mịn", "-"),
        (14, "Cân điện tử nhỏ", "Đĩa cân phẳng", "0.1g - 3000g", "Cân chanh, cam lát, nguyên liệu đong nhỏ", "Cân định lượng chính xác", "≤500g: ±5g")
    ]

    for item in tools_data:
        for c_idx, val in enumerate(item, 1):
            cell = ws_tc.cell(row=curr_r, column=c_idx, value=val)
            cell.font = bold_font if c_idx == 2 else regular_font
            cell.border = cell_border
            if c_idx in (1, 3, 4, 7):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            if curr_r % 2 == 1:
                cell.fill = light_gray
        ws_tc.row_dimensions[curr_r].height = 22
        curr_r += 1

    ws_tc.column_dimensions['A'].width = 8
    ws_tc.column_dimensions['B'].width = 22
    ws_tc.column_dimensions['C'].width = 18
    ws_tc.column_dimensions['D'].width = 18
    ws_tc.column_dimensions['E'].width = 36
    ws_tc.column_dimensions['F'].width = 30
    ws_tc.column_dimensions['G'].width = 16

    # =========================================================================
    # RE-ATTACH ALL OTHER SHEETS (From previous scripts)
    # =========================================================================
    # Load previously existing sheets from Bang_Du_Lieu_Mixue.xlsx
    old_wb = openpyxl.load_workbook(r"c:\Users\Admin\OneDrive\Desktop\DATN\AI-Agent_mixue\Bang_Du_Lieu_Mixue.xlsx")
    
    keep_sheets = [
        "Tong_Hop_San_Sau", "Mat_Ma_San_Pham", 
        "1_Tra_Xanh", "2_Tra_Sua_Lanh", "3_Hong_Tra_Lanh", 
        "4_Kem_Nguyen_Vi", "5_Thach_Duong_Den", "6_Thach_Dao", "7_Sua_Dac", 
        "Nguyen_Vat_Lieu_Va_HSD"
    ]

    for s_name in keep_sheets:
        if s_name in old_wb.sheetnames:
            src_ws = old_wb[s_name]
            dst_ws = wb.create_sheet(title=s_name)
            set_sheet_defaults(dst_ws)

            # Copy merged cells
            for m in src_ws.merged_cells.ranges:
                dst_ws.merge_cells(str(m))

            # Copy row heights
            for r_num in range(1, src_ws.max_row + 1):
                if src_ws.row_dimensions[r_num].height:
                    dst_ws.row_dimensions[r_num].height = src_ws.row_dimensions[r_num].height

            # Copy column widths
            for col_letter, col_dim in src_ws.column_dimensions.items():
                if col_dim.width:
                    dst_ws.column_dimensions[col_letter].width = col_dim.width

            # Copy cells content and styling
            for r_num in range(1, src_ws.max_row + 1):
                for c_num in range(1, src_ws.max_column + 1):
                    s_cell = src_ws.cell(row=r_num, column=c_num)
                    d_cell = dst_ws.cell(row=r_num, column=c_num, value=s_cell.value)
                    if s_cell.has_style:
                        d_cell.font = Font(name=s_cell.font.name, size=s_cell.font.size, bold=s_cell.font.bold, italic=s_cell.font.italic, color=s_cell.font.color)
                        d_cell.fill = PatternFill(fill_type=s_cell.fill.fill_type, start_color=s_cell.fill.start_color, end_color=s_cell.fill.end_color)
                        d_cell.alignment = Alignment(horizontal=s_cell.alignment.horizontal, vertical=s_cell.alignment.vertical, wrap_text=s_cell.alignment.wrap_text, indent=s_cell.alignment.indent)
                        d_cell.border = cell_border

    # Save complete final file
    out_path = r"c:\Users\Admin\OneDrive\Desktop\DATN\AI-Agent_mixue\Bang_Du_Lieu_Mixue.xlsx"
    wb.save(out_path)
    print(f"Master workbook saved successfully with {len(wb.sheetnames)} sheets: {wb.sheetnames}")

if __name__ == "__main__":
    build_complete_workbook()
