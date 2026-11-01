# Chạy BeverageOps AI cho quán trên một máy Windows, miễn phí, dữ liệu nằm ngoài thư mục code.
#
#   Lần đầu (tạo tài khoản chủ quán):  powershell -ExecutionPolicy Bypass -File scripts\run_shop.ps1 -Setup
#   Những lần sau:                     powershell -ExecutionPolicy Bypass -File scripts\run_shop.ps1
#
# Dữ liệu (CSDL, báo cáo chốt ca, ảnh chứng từ, lịch sử chat, phê duyệt đang chờ) nằm ở -DataDir
# (mặc định %USERPROFILE%\MixueData), nên `git pull` để cập nhật code không bao giờ ghi đè dữ liệu quán.
# Mở ra internet bằng Tailscale Funnel: xem docs/DEPLOY_FREE.md.
param(
    [string]$DataDir = (Join-Path $env:USERPROFILE "MixueData"),
    [int]$Port = 8501,
    [switch]$Setup
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

New-Item -ItemType Directory -Force -Path $DataDir, "$DataDir\agent_private", "$DataDir\chat_attachments", "$DataDir\shift_uploads" | Out-Null
# Seed một lần từ dữ liệu mẫu trong repo; không bao giờ ghi đè dữ liệu quán đã có.
if (-not (Test-Path "$DataDir\beverageops.db")) { Copy-Item "$Repo\data\beverageops.db" "$DataDir\beverageops.db" }
if (-not (Test-Path "$DataDir\shift_reports.json")) { Copy-Item "$Repo\data\shift_reports.json" "$DataDir\shift_reports.json" }

$Posix = $DataDir -replace '\\', '/'
$env:APP_ENV = "production"
$env:APP_DEMO_MODE = "false"
$env:STORE_ID = "2132"
$env:TZ = "Asia/Ho_Chi_Minh"
$env:DATABASE_URL = "sqlite:///$Posix/beverageops.db"
$env:SHIFT_DATA_FILE = "$DataDir\shift_reports.json"
$env:OCR_EDITS_LOG_FILE = "$DataDir\agent_private\ocr_user_edits.jsonl"
$env:AGENT_CHECKPOINT_PATH = "$DataDir\agent_private\checkpoints.sqlite"
$env:AGENT_AUDIT_PATH = "$DataDir\agent_private\audit.jsonl"
$env:CHAT_ATTACHMENTS_DIR = "$DataDir\chat_attachments"
$env:SHIFT_UPLOADS_DIR = "$DataDir\shift_uploads"

if ($Setup) {
    $user = Read-Host "Tên đăng nhập chủ quán (chữ thường, số, gạch dưới; ví dụ chuquan)"
    $name = Read-Host "Tên hiển thị (ví dụ Bùi Văn Quang)"
    python scripts\provision_admin.py $user --name $name --reset-existing
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Dữ liệu quán: $DataDir"
Write-Host "Mở trên máy này: http://localhost:$Port  (Ctrl+C để dừng)"
# Chỉ nghe trên localhost; người ngoài vào qua Tailscale Funnel (HTTPS), không mở cổng trên router.
python -m streamlit run src\dashboard\app.py --server.address 127.0.0.1 --server.port $Port --server.headless true
