# Script dựng dữ liệu/sổ tay Mixue (chạy một lần)

Các script sinh `Bang_Du_Lieu_Mixue.xlsx` và CSV trong `DU_LIEU_CAN_NHAP/`. Chúng dùng đường dẫn
tương đối, nên chạy từ thư mục gốc của repo, ví dụ:

```bash
python scripts/data_build/populate_mixue_operational_data.py
```

Không phải một phần của ứng dụng; ứng dụng đọc dữ liệu đã nạp vào database (`python src/ingestion.py`).
