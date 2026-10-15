# BÁO CÁO KIỂM TOÁN PHỤ THUỘC & HẠ TẦNG CI/CD (DEPENDENCY & CI/CD AUDIT)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-11-DEVOPS`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Đánh giá quản lý thư viện (Dependencies), Containerization (Docker), Tự động hóa tích hợp và triển khai liên tục (CI/CD)

---

## 1. KIỂM TOÁN QUẢN LÝ THƯ VIỆN & PHỤ THUỘC (DEPENDENCY MANAGEMENT AUDIT)

### 1.1. Lỗ Hổng Trầm Trọng: Thiếu Hoàn Toàn Tệp Khai Báo Dependencies
- **Phát hiện nghiêm trọng:**
  Trong toàn bộ thư mục gốc và các thư mục con của repository, **hoàn toàn không tồn tại bất kỳ tệp kê khai thư viện nào**:
  - Không có `requirements.txt`
  - Không có `Pipfile` hoặc `Pipfile.lock`
  - Không có `pyproject.toml` hoặc `poetry.lock`
  - Không có `environment.yml` (Conda)
- **Hậu quả vận hành (Production Risks):**
  1. **Không thể tái lập môi trường (Non-reproducible Environment):** Một kỹ sư mới gia nhập dự án hoặc máy chủ staging/cloud khi kéo code về không có hướng dẫn cụ thể cần cài những thư viện gì và phiên bản nào.
  2. **Rủi ro Dependency Drift:** Nếu người cài đặt gõ `pip install streamlit pandas sqlalchemy`, pip sẽ tự động kéo các phiên bản mới nhất (có thể là Streamlit 2.0 hoặc Pandas 3.0 với các breaking changes), dẫn đến ứng dụng bị crash ngay lập tức trên máy chủ.
  3. **Không thể quét lỗ hổng bảo mật (Zero Security Vulnerability Auditing):** Các công cụ quét bảo mật phụ thuộc tự động như GitHub Dependabot, Snyk hay `pip-audit` hoàn toàn bất lực vì không có tệp manifest để phân tích CVE.

---

### 1.2. Danh Mục Thư Viện Thực Tế Đang Chạy (Extracted Runtime Dependencies)
Dựa trên việc kiểm tra môi trường thực tế đang chạy của hệ thống (`Python 3.12.6`), đội ngũ kiểm toán đã trích xuất danh mục các thư viện cốt lõi bắt buộc:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXTRACTED RUNTIME DEPENDENCY MANIFEST                    │
├──────────────────────────────┬──────────────┬───────────────────────────────┤
│ Gói Thư Viện (Package)       │ Phiên Bản    │ Mục Đích Sử Dụng Trong Dự Án  │
├──────────────────────────────┼──────────────┼───────────────────────────────┤
│ streamlit                    │ >=1.40.0     │ Giao diện Web App & Dashboard │
│ sqlalchemy                   │ >=2.0.35     │ ORM ánh xạ CSDL               │
│ pandas                       │ >=2.2.3      │ Xử lý bảng tính & chuỗi số liệu│
│ numpy                        │ >=2.1.2      │ Tính toán ma trận, MAE, WAPE  │
│ openpyxl                     │ >=3.1.5      │ Xuất khẩu Sổ kho 31 ngày Excel│
│ pydantic                     │ >=2.9.2      │ Kiểm thực dữ liệu Schema      │
│ pytest                       │ >=8.4.2      │ Chạy 46 unit & integration test│
│ ruff                         │ >=0.8.0      │ Phân tích tĩnh & Linter       │
│ psycopg2-binary              │ >=2.9.9      │ Driver kết nối PostgreSQL     │
└──────────────────────────────┴──────────────┴───────────────────────────────┘
```

---

## 2. KIỂM TOÁN HẠ TẦNG CONTAINER HÓA (DOCKER & DOCKER-COMPOSE AUDIT)

### 2.1. Hiện Trạng Tệp `docker-compose.yml`
Tại [docker-compose.yml:1-22](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/docker-compose.yml#L1-L22):
```yaml
services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:?Run setup_local.py first}
      POSTGRES_USER: ${POSTGRES_USER:?Run setup_local.py first}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Run setup_local.py first}
      TZ: Asia/Ho_Chi_Minh
    ports:
      - "127.0.0.1:${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5
volumes:
  postgres_data:
```

### 2.2. Các Khiếm Khuyết Nghiêm Trọng Về Hạ Tầng
1. **Thiếu Hoàn Toàn `Dockerfile` Của Ứng Dụng:**
   Repository **hoàn toàn không có tệp `Dockerfile`** để đóng gói ứng dụng Python/Streamlit BeverageOps AI.
2. **`docker-compose.yml` Chỉ Chạy Cơ Sở Dữ Liệu:**
   Tệp compose hiện tại chỉ khởi chạy một dịch vụ đơn lẻ là `postgres:16`. Không có service `app` để kết nối với `postgres`, khiến việc triển khai đóng gói container một lệnh (`docker compose up`) trở nên bất khả thi.
3. **Thiếu Cơ Chế Quản Lý Volume Dữ Liệu Ứng Dụng:**
   Thư mục ảnh chụp sổ ca [data/shift_photos/](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/data/shift_photos/) và database SQLite [data/beverageops.db](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/data/beverageops.db) đang nằm trực tiếp trên ổ cứng máy tính host, chưa có cấu hình mount volume an toàn trong Docker.

---

## 3. KIỂM TOÁN ĐƯỜNG ỐNG CI/CD (CI/CD PIPELINE AUDIT)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CI/CD MATURITY LEVEL: ZERO                            │
├────────────────────┬──────────┬─────────────────────────────────────────────┤
│ Tiêu Chí DevOps    │ Trạng    │ Đánh Giá Thực Tế                            │
│                    │ Thái     │                                             │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 1. VCS Workflows   │ KHÔNG CÓ │ Không có .github/workflows/ hoặc .gitlab-ci │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 2. Automated Lint  │ KHÔNG CÓ │ Ruff không được chạy tự động trên mỗi commit│
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 3. Automated Test  │ KHÔNG CÓ │ 46 bài unit test chỉ được chạy thủ công     │
│                    │          │ bằng tay trên máy dev                       │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 4. Build & Push    │ KHÔNG CÓ │ Không có luồng build Docker image đẩy lên   │
│                    │          │ Docker Hub / GitHub Container Registry (GHCR│
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 5. Automated CD    │ KHÔNG CÓ │ Không có luồng deploy tự động sang Staging  │
└────────────────────┴──────────┴─────────────────────────────────────────────┘
```

- **Rủi ro lớn khi hợp nhất mã nguồn (Merge Risk):**
  Vì không có CI Pipeline bảo vệ nhánh chính (`main`), bất kỳ lập trình viên nào đẩy code bị lỗi cú pháp, vi phạm bảo mật hoặc làm gãy 2 bài test chốt ca đều có thể merge thẳng vào repository mà không hề có bất kỳ rào cản tự động nào ngăn chặn.

---

## 4. BỘ HỒ SƠ ĐỀ XUẤT CHUẨN HÓA DEVOPS (TARGET DEVOPS ARTIFACTS)

### 4.1. Tệp `requirements.txt` Chuẩn Cần Bổ Sung Ngay
```text
# Core Web & UI Framework
streamlit==1.40.1

# Database & ORM
SQLAlchemy==2.0.35
psycopg2-binary==2.9.9

# Data Processing & Analytics
pandas==2.2.3
numpy==2.1.2
openpyxl==3.1.5

# Validation & Schema
pydantic==2.9.2

# Testing & Quality Assurance
pytest==8.4.2
pytest-asyncio==1.4.0
ruff==0.8.4
```

### 4.2. Tệp `Dockerfile` Đa Tầng (Multi-stage Dockerfile)
```dockerfile
# Stage 1: Build stage
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production runtime stage
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH \
    TZ=Asia/Ho_Chi_Minh

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl tzdata && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
COPY . .

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "src/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 4.3. Đường Ống GitHub Actions CI (`.github/workflows/ci.yml`)
```yaml
name: BeverageOps AI CI Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  audit-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run Static Code Analysis (Ruff)
        run: python -m ruff check src tests
      - name: Run Automated Pytest Suite
        run: pytest tests/ -v --tb=short
```
