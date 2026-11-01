# Deploy miễn phí (0 đồng)

Không có dịch vụ cloud nào vừa miễn phí, vừa không cần thẻ, vừa giữ dữ liệu, vừa chạy 24/7.
Vì vậy có hai đường, tùy mục đích:

| Mục đích | Cách | Dữ liệu | Link |
|---|---|---|---|
| **Dùng thật cho quán** | Máy tính ở quán chạy app + **Tailscale Funnel** | Giữ vĩnh viễn trên ổ cứng máy đó | `https://<tên-máy>.<tailnet>.ts.net` cố định |
| **Demo / bảo vệ đồ án** | **Render Free** (`render.yaml`) | Quay về dữ liệu mẫu mỗi lần dịch vụ ngủ (15 phút không dùng) | `https://mixue-beverageops-demo.onrender.com` |

Cả hai không cần thẻ ngân hàng. Khóa Gemini lấy miễn phí ở Google AI Studio (gói miễn phí có giới hạn số lượt/ngày; không bật thanh toán thì không bị tính tiền).

---

## A. Dùng thật cho quán: máy ở quán + Tailscale Funnel

Điều kiện: một máy Windows (máy thu ngân hoặc laptop) **bật trong giờ quán mở**. Nhân viên mở link trên điện thoại như một trang web bình thường.

### 1. Cài đặt (một lần)
1. Cài Python 3.11+ và Git, rồi:
   ```powershell
   git clone https://github.com/Quang20040/AI-Agent_mixue.git
   cd AI-Agent_mixue
   python -m pip install -r requirements.txt
   ```
2. Tạo file `.env` (chép từ `.env.example`) và điền khóa Gemini nếu muốn đọc ảnh bằng AI:
   ```
   LLM_ENABLED=true
   LLM_PROVIDER=gemini
   LLM_MODEL=gemini-2.5-flash
   ALLOW_EXTERNAL_DATA_TRANSFER=true
   GEMINI_API_KEY=...
   ```
3. Tạo tài khoản chủ quán (mật khẩu 12–128 ký tự, gõ ẩn):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\run_shop.ps1 -Setup
   ```
   Lệnh này tạo thư mục dữ liệu `%USERPROFILE%\MixueData`, chép dữ liệu mẫu vào **một lần**, tạo chủ quán rồi chạy app.
   Đăng nhập ở `http://localhost:8501` → vào **Quản lý nhân viên** tạo tài khoản cho nhân viên.

### 2. Mở ra internet bằng Tailscale Funnel (miễn phí, không cần thẻ, không mở cổng router)
1. Cài Tailscale cho Windows, đăng nhập bằng Google/GitHub.
2. Trong trang quản trị Tailscale: bật **MagicDNS** và **HTTPS Certificates** (mục DNS), và cho phép Funnel khi được hỏi.
3. Mở PowerShell **với quyền Administrator**:
   ```powershell
   tailscale funnel --bg 8501
   ```
   Lệnh in ra link dạng `https://<tên-máy>.<tailnet>.ts.net/`. Link này cố định; gửi cho nhân viên.
   `--bg` giữ Funnel chạy nền kể cả sau khi khởi động lại máy. Tắt: `tailscale funnel reset`.

### 3. Hằng ngày
```powershell
cd AI-Agent_mixue
powershell -ExecutionPolicy Bypass -File scripts\run_shop.ps1
```
Có thể đặt lệnh này vào Task Scheduler ("At log on") để tự chạy khi bật máy.

### 4. Cập nhật code
```powershell
git pull
python -m pip install -r requirements.txt
```
Dữ liệu quán nằm ở `%USERPROFILE%\MixueData`, **không** nằm trong thư mục code, nên `git pull` không bao giờ ghi đè.
Sao lưu: chép cả thư mục `MixueData` sang Google Drive / USB định kỳ.

### Giới hạn cần biết
- Máy tắt hoặc mất mạng thì link không vào được.
- Funnel có giới hạn băng thông không công bố; đủ cho vài nhân viên dùng app này, không phù hợp phát video.
- App chỉ nghe trên `127.0.0.1`, nên người trong cùng Wi-Fi cũng vào qua link `ts.net`, không qua IP máy.

---

## B. Demo / bảo vệ đồ án: Render Free

1. Đăng nhập Render bằng GitHub (không cần thẻ) → **New → Blueprint** → chọn repo `AI-Agent_mixue`, nhánh `fix/quality-improvement`.
   Render đọc `render.yaml` (gói `free`).
2. `GEMINI_API_KEY`: dán khóa nếu muốn đọc ảnh thật, hoặc để trống.
3. **Apply**, chờ build xong (vài phút) → mở link `.onrender.com`, dùng nút **Tài khoản dùng thử & đăng nhập nhanh**.
4. Trước buổi bảo vệ:
   - Đổi `LLM_ENABLED` thành `true` trong tab Environment nếu muốn chế độ AI Online (mặc định tắt để người lạ không dùng hết hạn mức Gemini).
   - Mở link trước khoảng 2 phút để dịch vụ thức dậy, và mở lại sau mỗi lần nghỉ dài hơn 15 phút.

Giới hạn: gói Free ngủ sau 15 phút, mọi thay đổi bị xóa khi ngủ/khởi động lại/deploy lại, và chỉ có 750 giờ chạy mỗi tháng cho cả tài khoản. Không dùng bản này để ghi sổ thật.

## Vì sao không dùng các lựa chọn khác
- **Hugging Face Spaces**: Space dạng Docker giờ cần gói trả phí để tạo.
- **Oracle Cloud Always Free**: máy ảo mạnh và giữ dữ liệu, nhưng bắt buộc thẻ để xác minh, hay hết chỗ trống và có thể bị thu hồi khi máy rảnh lâu.
- **ngrok miễn phí**: chỉ 1 GB dữ liệu ra mỗi tháng và hiện trang cảnh báo trước khi vào app.
