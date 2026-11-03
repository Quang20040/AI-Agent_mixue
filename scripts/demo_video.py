"""Record a ~3 minute captioned demo of the live site (Playwright video), then cut and speed up the waits with ffmpeg.

Usage: python scripts/demo_video.py https://mixue-beverageops-demo.onrender.com demo_out
Nothing is written to the shop's books: the shift report is sent to the queue and then REJECTED by the manager.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip('/')
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else 'demo_out')
OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parents[1]
W, H = 1440, 900
STATE = "() => document.querySelector('[data-testid=\"stApp\"]')?.getAttribute('data-test-script-state')"
T0 = [0.0]
SEGMENTS = []  # (start, end, speed) in seconds of the raw recording
_fast = [None]
LOG = []


def now():
    return time.time() - T0[0]


def fast_start(page, label='Đang chờ AI xử lý'):
    _fast[0] = now()
    badge(page, f'⏩ Tua nhanh · {label}')


def fast_end(page, speed=8):
    if _fast[0] is not None:
        SEGMENTS.append((_fast[0], now(), speed))
        _fast[0] = None
    badge(page, '')


OVERLAY_JS = r"""
(() => {
  if (document.getElementById('demo-style')) return;
  const st = document.createElement('style'); st.id = 'demo-style';
  st.textContent = `
    #demo-cap{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);max-width:1100px;z-index:2147483646;
      background:rgba(20,20,28,.86);color:#fff;border-radius:14px;padding:14px 22px;font:500 21px/1.4 'Segoe UI',Arial,sans-serif;
      box-shadow:0 8px 30px rgba(0,0,0,.35);transition:opacity .35s;text-align:center}
    #demo-cap b{color:#ffd166} #demo-cap .k{display:block;font-size:14px;letter-spacing:.12em;color:#ff8fa3;margin-bottom:4px;font-weight:700}
    #demo-badge{position:fixed;right:22px;top:18px;z-index:2147483646;background:#e60012;color:#fff;border-radius:999px;
      padding:6px 14px;font:700 15px Arial,sans-serif;display:none}
    #demo-cursor{position:fixed;width:22px;height:22px;border-radius:50%;background:rgba(230,0,18,.35);border:2px solid #e60012;
      z-index:2147483647;pointer-events:none;transform:translate(-50%,-50%);transition:left .55s ease, top .55s ease;left:720px;top:450px}
    #demo-cursor.click{background:rgba(230,0,18,.75)}
    #demo-card{position:fixed;inset:0;z-index:2147483645;display:flex;align-items:center;justify-content:center;
      background:linear-gradient(135deg,#b3000e,#e60012 55%,#ff5a6a);color:#fff;font-family:'Segoe UI',Arial,sans-serif;transition:opacity .5s}
    #demo-card .box{max-width:1050px;padding:40px}
    #demo-card h1{font-size:46px;margin:0 0 10px} #demo-card h2{font-size:26px;font-weight:500;margin:0 0 28px;opacity:.95}
    #demo-card li{font-size:24px;margin:10px 0;list-style:none} #demo-card small{font-size:18px;opacity:.85}
    .st-key-login_card,.st-key-login_shell,.st-key-login_card *{opacity:1 !important;animation:none !important}
  `;
  document.head.appendChild(st);
  for (const id of ['demo-cap','demo-badge','demo-cursor']) {
    const d = document.createElement('div'); d.id = id; if (id === 'demo-cap') d.style.opacity = 0; document.body.appendChild(d);
  }
})()
"""


def overlay(page):
    try:
        page.evaluate(OVERLAY_JS)
    except Exception:  # noqa: BLE001
        pass


def cap(page, kicker, html, hold=0):
    overlay(page)
    page.evaluate("([k,h]) => {const c=document.getElementById('demo-cap'); if(!h){c.style.opacity=0;return}"
                  "c.innerHTML=(k?`<span class=k>${k}</span>`:'')+h; c.style.opacity=1}", [kicker, html])
    LOG.append((round(now(), 1), kicker, html))
    if hold:
        page.wait_for_timeout(int(hold * 1000))


def badge(page, text):
    overlay(page)
    page.evaluate("t => {const b=document.getElementById('demo-badge'); b.textContent=t; b.style.display=t?'block':'none'}", text)


def card(page, html, hold):
    overlay(page)
    page.evaluate("h => {let c=document.getElementById('demo-card'); if(!c){c=document.createElement('div');c.id='demo-card';"
                  "document.body.appendChild(c)} c.innerHTML=`<div class=box>${h}</div>`; c.style.opacity=1; c.style.display='flex'}", html)
    page.wait_for_timeout(int(hold * 1000))
    page.evaluate("() => {const c=document.getElementById('demo-card'); c.style.opacity=0; setTimeout(()=>c.style.display='none',600)}")
    page.wait_for_timeout(600)


def idle(page, extra=400, limit=150):
    start, quiet = time.time(), 0.0
    while time.time() - start < limit and quiet < 1.2:
        page.wait_for_timeout(200)
        try:
            running = page.evaluate(STATE) in ('running', 'rerunRequested')
        except Exception:  # noqa: BLE001
            running = True
        quiet = 0.0 if running else quiet + 0.2
    page.wait_for_timeout(extra)
    overlay(page)


def point(page, locator):
    overlay(page)
    try:
        locator.scroll_into_view_if_needed(timeout=10000)
        box = locator.bounding_box(timeout=10000)
    except Exception:  # noqa: BLE001
        box = None
    if box:
        page.evaluate("([x,y]) => {const c=document.getElementById('demo-cursor'); c.style.left=x+'px'; c.style.top=y+'px'}",
                      [box['x'] + box['width'] / 2, box['y'] + box['height'] / 2])
        page.wait_for_timeout(650)


def click(page, locator, wait=True):
    point(page, locator)
    page.evaluate("() => document.getElementById('demo-cursor').classList.add('click')")
    locator.click(timeout=30000)
    page.wait_for_timeout(250)
    try:
        page.evaluate("() => document.getElementById('demo-cursor').classList.remove('click')")
    except Exception:  # noqa: BLE001
        pass
    if wait:
        idle(page)


def scroll(page, dy, steps=6, pause=120):
    for _ in range(steps):
        page.mouse.wheel(0, dy / steps)
        page.wait_for_timeout(pause)
    page.wait_for_timeout(400)


def nav(page, label):
    loc = page.locator('.st-key-main_navigation label').filter(has_text=label).first
    click(page, loc)
    page.wait_for_timeout(400)
    idle(page)
    page.mouse.move(720, 300)


def open_site(page):
    page.goto(BASE, wait_until='domcontentloaded', timeout=180000)
    page.locator('.st-key-login_card, .st-key-main_navigation').first.wait_for(timeout=180000)
    idle(page, 800)


def quick_login(page, key):
    if not page.locator(f'.st-key-{key} button').first.is_visible():
        exp = page.locator('[data-testid="stExpander"] summary').filter(has_text='Tài khoản dùng thử').first
        click(page, exp, wait=False)
        page.wait_for_timeout(700)
    btn = page.locator(f'.st-key-{key} button').first
    if not btn.count():
        return False
    click(page, btn)
    page.locator('.st-key-main_navigation').first.wait_for(timeout=120000)
    idle(page, 600)
    return True


def logout(page):
    btn = page.locator('.st-key-btn_logout button').first
    if btn.count():
        click(page, btn)
        page.locator('.st-key-login_card').first.wait_for(timeout=60000)
        idle(page, 500)


def chat(page, message, hold=5, label='Tuyết Vương đang trả lời'):
    box = page.locator('[data-testid="stChatInputTextArea"]').first
    point(page, box)
    box.click()
    box.press_sequentially(message, delay=45)
    before = page.locator('[data-testid="stChatMessage"]').count()
    box.press('Enter')
    t = time.time()
    started = False
    while time.time() - t < 160:
        page.wait_for_timeout(300)
        if not started and time.time() - t > 3.5:
            fast_start(page, label)
            started = True
        try:
            running = page.evaluate(STATE) in ('running', 'rerunRequested')
        except Exception:  # noqa: BLE001
            running = True
        if not running and page.locator('[data-testid="stChatMessage"]').count() >= before + 2:
            break
    if started:
        fast_end(page, 6)
    idle(page, 300)
    msgs = page.locator('[data-testid="stChatMessage"]')
    last = msgs.nth(msgs.count() - 1)
    try:
        last.scroll_into_view_if_needed(timeout=5000)
        page.evaluate("() => window.scrollBy(0, 120)")
    except Exception:  # noqa: BLE001
        pass
    LOG.append((round(now(), 1), 'reply', last.inner_text()[:300]))
    page.wait_for_timeout(int(hold * 1000))


def scenes(page, browser, ctx):
    # ------------------------------------------------ 0. Title
    open_site(page)
    card(page, "<h1>BeverageOps AI · Mixue 2132</h1><h2>Hệ thống AI Agent hỗ trợ đối soát chốt ca và vận hành cửa hàng đồ uống</h2>"
               "<ul><li>① <b>Đọc ảnh chốt ca có kiểm chứng</b> — AI chép chữ, mã tất định tính tiền & đối soát</li>"
               "<li>② <b>Con người trong vòng lặp</b> — không số nào vào sổ khi Quản lý chưa duyệt</li>"
               "<li>③ <b>Tác tử LangGraph</b> — trả lời tiếng Việt tự nhiên từ dữ liệu thật, có phân quyền & nguồn</li></ul>"
               "<small>Bùi Văn Quang · 22810310162 · Demo trên bản triển khai Render</small>", 9)
    cap(page, 'ĐĂNG NHẬP', 'Phân quyền 3 vai trò · mật khẩu băm <b>PBKDF2</b> · sai 8 lần khóa 60 giây · giữ phiên khi tải lại trang', 4)

    # ------------------------------------------------ 1. Staff closes a shift from photos
    staff = quick_login(page, 'quick_login_staff')
    if not staff:
        quick_login(page, 'quick_login_manager')
    who = 'Nhân viên chính thức' if staff else 'Quản lý'
    cap(page, 'TRỤ CỘT ① · CHỐT CA TỪ ẢNH', f'{who} chụp sổ giao ca viết tay và phiếu POS ngày 01/11 rồi tải lên', 0)
    nav(page, 'Chốt ca')
    page.wait_for_timeout(1500)
    photos = [ROOT / 'data/shift_photos' / n for n in
              ('20261101_ca_sang_chieu.jpg', '20261101_ca_toi_tong_ket.jpg', '20261101_ca_toi_pos_slip.jpg')]
    inp = page.locator('.st-key-shift_photo_uploader input[type=file]').first
    point(page, page.locator('.st-key-shift_photo_uploader').first)
    inp.set_input_files([str(p) for p in photos])
    idle(page, 1200)
    cap(page, 'TRỤ CỘT ① · CHỐT CA TỪ ẢNH', 'Ảnh được tự xoay, đổi HEIC → JPEG, nén và lưu theo mã băm · <b>một ảnh có thể chứa cả 3 ca</b>', 4)
    btn = page.locator('.st-key-run_shift_ocr button').first
    cap(page, 'TRỤ CỘT ① · ĐỌC ẢNH', 'Gemini chỉ <b>chép nguyên văn từng ô</b> (“653”, “962 + 629”, “2014 (dư 20k)”) — không tự tính', 0)
    click(page, btn, wait=False)
    fast_start(page, 'Gemini đang đọc 3 ảnh')
    idle(page, 800, limit=240)
    fast_end(page, 10)
    move = page.locator('.st-key-ocr_move_day button').first
    if move.count():
        cap(page, 'KIỂM CHỨNG', 'Ngày ghi trên ảnh khác ngày đang chọn → hệ thống đề nghị <b>chuyển sang đúng ngày trên ảnh</b>', 3)
        click(page, move)
        page.wait_for_timeout(800)
    cap(page, 'KIỂM CHỨNG', 'Mã tất định quy đổi nghìn đồng, tách biểu thức, bóc ghi chú dư/thiếu, <b>cộng ngang và đối chiếu POS</b>', 4)
    ev = page.locator('.st-key-ocr_open_evidence button').first
    if ev.count():
        click(page, ev)
        page.wait_for_timeout(800)
        cap(page, 'BẰNG CHỨNG TỪNG Ô', 'Mỗi ô có chữ đọc từ ảnh, giá trị chuẩn hóa và <b>lý do cần kiểm tra</b>', 6)
        page.keyboard.press('Escape')
        idle(page, 500)
    form = page.locator('.st-key-ocr_evidence_card').first
    if form.count():
        point(page, form)
    scroll(page, 380)
    cap(page, 'Ô VÀNG = GỢI Ý', 'Ô đọc chắc điền thẳng · ô chưa chắc <b>điền gợi ý, tô vàng</b> để nhân viên đối chiếu ảnh', 5)
    for label in ('Tôi đã đối chiếu ảnh', 'Tôi đã kiểm tra'):
        box = page.locator('[data-testid="stCheckbox"]').filter(has_text=label).first
        if box.count():
            click(page, box.locator('label').first)
    send = page.locator('button').filter(has_text='Gửi yêu cầu Quản lý duyệt').first
    if send.count():
        cap(page, 'TRỤ CỘT ② · NGƯỜI DUYỆT', 'Bấm gửi: báo cáo vào <b>hàng đợi duyệt</b> — <b>chưa có số nào được ghi sổ</b>', 0)
        click(page, send)
        page.wait_for_timeout(1500)
        page.wait_for_timeout(2500)

    # ------------------------------------------------ 2. Manager queue (reject: demo writes nothing)
    if staff:
        cap(page, 'PHÂN QUYỀN', 'Nhân viên không có quyền xem doanh thu — kể cả khi hỏi trợ lý', 0)
        nav(page, 'Trợ lý')
        chat(page, 'doanh thu hôm qua bao nhiêu', hold=4)
        logout(page)
        quick_login(page, 'quick_login_manager')
    cap(page, 'TRỤ CỘT ② · HÀNG ĐỢI DUYỆT', 'Quản lý thấy <b>chuông việc chờ duyệt</b> ngay trên trang chủ', 4)
    queue = page.locator('[class*="st-key-approval_center"]').first
    if queue.count():
        point(page, queue)
        scroll(page, 250)
        page.wait_for_timeout(1500)
        cap(page, 'HUMAN-IN-THE-LOOP', 'Duyệt → đồ thị LangGraph dừng ở <b>interrupt()</b> và ghi sổ khi có quyết định · ở đây em <b>Từ chối</b> để demo không làm đổi sổ thật', 6)
        no = page.locator('[class*="st-key-apv_n_"] button').first
        if no.count():
            click(page, no)
            page.wait_for_timeout(2000)
            cap(page, 'HUMAN-IN-THE-LOOP', 'Yêu cầu chuyển <b>REJECTED</b>, nhân viên thấy trạng thái mới · sổ doanh thu giữ nguyên', 4)
    nav(page, 'Doanh thu')
    cap(page, 'MỘT SỐ MỖI NGÀY', 'Doanh thu chỉ lấy từ <b>báo cáo chốt ca đã duyệt</b> (hoặc POS) — hai nguồn không bao giờ cộng dồn', 0)
    tab = page.locator('[data-baseweb="tab"]').filter(has_text='doanh thu').first
    if tab.count():
        click(page, tab)
    page.wait_for_timeout(5000)

    # ------------------------------------------------ 3. LangGraph agent
    cap(page, 'TRỤ CỘT ③ · TÁC TỬ LANGGRAPH', 'guard → model → authorize → tools → approval · 25 công cụ có phân quyền · mỗi câu trả lời kèm nguồn', 0)
    nav(page, 'Trợ lý')
    newc = page.locator('button').filter(has_text='Trò chuyện mới').first
    if newc.count():
        click(page, newc)
    page.wait_for_timeout(1500)
    chat(page, 'so sánh doanh thu ngày 1/11 và 2/11', hold=6)
    cap(page, 'KHÔNG BỊA SỐ', 'Số lấy từ công cụ <b>get_daily_sales</b> trên dữ liệu đã duyệt · bấm “Nguồn dữ liệu” để xem bảng gốc', 3)
    chat(page, 'ct TS1', hold=5)
    cap(page, 'ĐỊNH TUYẾN TẤT ĐỊNH', 'Hỏi viết tắt “ct TS1” → công thức lấy thẳng từ bảng định lượng, không để mô hình tự nhớ', 3)
    chat(page, 'dự báo ngày mai bán bao nhiêu ly', hold=6)
    cap(page, 'DỰ BÁO', 'Trung bình trượt (WAPE 22,41%) · hiệu chỉnh bằng doanh thu chốt ca đã duyệt và thời tiết Open-Meteo', 3)
    chat(page, 'đói quá', hold=4)
    cap(page, 'TỰ NHIÊN, ĐÚNG NGỮ CẢNH', 'Chuyện ngoài lề được trả lời ngắn, không gọi công cụ, rồi gợi ý việc trợ lý làm được', 3)

    # ------------------------------------------------ 4. Results
    cap(page, '', '')
    card(page, "<h1>Kết quả đánh giá</h1><ul>"
               "<li>🧾 Đọc ảnh: lỗi lọt vào form <b>18 → 6</b> nhờ lớp kiểm chứng (Gemini, 44 ô có đáp án)</li>"
               "<li>🤖 Trợ lý: <b>49/50</b> câu chuẩn · phản hồi trung vị <b>2,2 s</b> trên Render</li>"
               "<li>📈 Dự báo: WAPE <b>22,41%</b> (kiểm định lùi 77 ngày, 39 món)</li>"
               "<li>✅ <b>387</b> kiểm thử tự động chạy trong CI trước mỗi lần triển khai · 39/40 ca kiểm thử trên web thật</li></ul>"
               "<small>AI chép · mã tính · người duyệt — cảm ơn thầy cô đã theo dõi!</small>", 10)


def render(raw, out):
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(raw)],
                               capture_output=True, text=True).stdout.strip() or 0)
    cuts, pos = [], 0.0
    for a, b, speed in sorted(SEGMENTS):
        a, b = max(a, pos), min(b, dur)
        if a > pos:
            cuts.append((pos, a, 1))
        if b > a:
            cuts.append((a, b, speed))
        pos = max(pos, b)
    if pos < dur:
        cuts.append((pos, dur, 1))
    parts = []
    for i, (a, b, s) in enumerate(cuts):
        parts.append(f'[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{s},fps=30[v{i}]')
    graph = ';'.join(parts) + ';' + ''.join(f'[v{i}]' for i in range(len(cuts))) + f'concat=n={len(cuts)}:v=1:a=0,scale=1440:900,format=yuv420p[out]'
    tmp = out.with_name(out.stem + '.tmp.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(raw), '-filter_complex', graph, '-map', '[out]', '-c:v', 'libx264',
                    '-preset', 'veryfast', '-crf', '22', '-movflags', '+faststart', str(tmp)], check=True)
    tmp.rename(out)
    final = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(out)],
                                 capture_output=True, text=True).stdout.strip())
    return dur, final, cuts


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': W, 'height': H}, locale='vi-VN', record_video_dir=str(OUT / 'raw'),
                                  record_video_size={'width': W, 'height': H})
        page = ctx.new_page()
        T0[0] = time.time()
        try:
            scenes(page, browser, ctx)
        except Exception as exc:  # noqa: BLE001 - keep whatever was recorded
            LOG.append((round(now(), 1), 'ERROR', repr(exc)[:500]))
            try:
                page.screenshot(path=str(OUT / 'error.png'))
            except Exception:  # noqa: BLE001
                pass
            if _fast[0] is not None:
                fast_end(page)
        raw = Path(page.video.path())
        ctx.close()
        browser.close()
    dur, final, cuts = render(raw, OUT / 'demo_beverageops.mp4')
    (OUT / 'log.json').write_text(json.dumps({'raw_s': dur, 'final_s': final, 'cuts': cuts, 'log': LOG},
                                             ensure_ascii=False, indent=1), encoding='utf-8')
    print('raw', dur, 'final', final)
    for row in LOG:
        print(row)


if __name__ == '__main__':
    main()
