"""Dịch vụ Quản lý & Trích xuất Doanh thu Chốt Ca (Shift Revenue Service).

Chức năng:
1. Lưu trữ và quản lý báo cáo chốt ca theo từng ca: Ca sáng (8h-13h), Ca chiều (13h-18h), Ca tối/Chốt ngày (18h-23h).
2. Tích hợp AI OCR & Trích xuất Vision thông minh từ ảnh chụp sổ chốt ca viết tay hoặc hóa đơn POS.
3. Tổng hợp doanh thu cuối ngày (tiền mặt, chuyển khoản, Shopee, Grab, BeFood, chi phí phát sinh, thực thu về).
4. Đối soát chênh lệch tự động giữa số tiền thực thu tại ca và doanh thu máy POS.
5. Ghi nhận chi tiết chỉnh sửa của người dùng trên từng trường OCR để phục vụ đánh giá chất lượng.
"""

import json
import os
import math
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from src.engine.storage_lock import FileTransactionLock
from src.runtime_settings import resolve_store_id, setting

ROOT = Path(__file__).resolve().parents[2]
# Paths can be redirected by environment (tests use temporary copies of the tracked data).
SHIFT_DATA_FILE = Path(setting("SHIFT_DATA_FILE") or ROOT / "data" / "shift_reports.json")
_CONFIGURED_SHIFT_DATA_FILE = SHIFT_DATA_FILE
SHIFT_PHOTOS_DIR = ROOT / "data" / "shift_photos"
# Uploaded evidence photos must survive redeploys, so production points this at the persistent disk.
SHIFT_UPLOADS_DIR = Path(setting("SHIFT_UPLOADS_DIR") or SHIFT_PHOTOS_DIR / "uploads")
OCR_EDITS_LOG_FILE = Path(setting("OCR_EDITS_LOG_FILE") or ROOT / "data" / "agent_private" / "ocr_user_edits.jsonl")
SHIFT_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

_SHIFT_LOCK = FileTransactionLock(lambda: SHIFT_DATA_FILE.with_suffix('.lock'))


class ShiftStorageError(RuntimeError):
    pass

REQUIRED_SHIFT_MONEY_FIELDS = (
    "cash_vnd",
    "cash_diff_vnd",
    "bank_transfer_vnd",
    "shopee_food_vnd",
    "grab_food_vnd",
    "be_food_vnd",
    "petty_cash_kept_vnd",
    "expenses_vnd",
    "total_collected_vnd",
)

# Định nghĩa các ca chuẩn tại cửa hàng Mixue
SHIFT_DEFINITIONS = {
    "CA_SANG": {
        "code": "CA_SANG",
        "title": "1. Ca sáng bàn giao (8h-13h)",
        "short_name": "Ca sáng",
        "hours": "08:00 - 13:00",
        "default_petty_cash": 1000000
    },
    "CA_CHIEU": {
        "code": "CA_CHIEU",
        "title": "2. Ca chiều bàn giao (13h-18h)",
        "short_name": "Ca chiều",
        "hours": "13:00 - 18:00",
        "default_petty_cash": 1000000
    },
    "CA_TOI": {
        "code": "CA_TOI",
        "title": "3. Ca tối & Chốt tổng hợp cả ngày (18h-23h)",
        "short_name": "Ca tối / Tổng hợp ngày",
        "hours": "18:00 - 23:00",
        "default_petty_cash": 1000000
    }
}


def _load_raw_shift_data() -> list[dict[str, Any]]:
    """Đọc toàn bộ báo cáo ca từ file JSON persistent."""
    with _SHIFT_LOCK:
        if not SHIFT_DATA_FILE.exists():
            initial_data = []  # no sample reports: only what the shop actually closes and approves
            _save_raw_shift_data(initial_data)
            return initial_data
        try:
            with open(SHIFT_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
                    raise ValueError('Invalid shift storage schema')
                return data
        except Exception as e:
            raise ShiftStorageError('Không đọc được báo cáo ca. Dữ liệu có thể bị hỏng; cần khôi phục bản sao lưu.') from e


def _sync_shift_reports_to_db(data: list[dict[str, Any]]) -> None:
    """Đồng bộ bản ghi báo cáo chốt ca sang bảng quan hệ `shift_reports` trong Database."""
    # A path swapped at runtime (unit tests on a scratch file) must not touch the database.
    if SHIFT_DATA_FILE != _CONFIGURED_SHIFT_DATA_FILE:
        return
    try:
        from src.database import SessionLocal, engine
        from src.models import ShiftReportRecord

        ShiftReportRecord.__table__.create(bind=engine, checkfirst=True)
        with SessionLocal() as db:
            seen_ids = set()
            for idx, row in enumerate(data):
                if not isinstance(row, dict):
                    continue
                b_date = str(row.get("business_date") or "")
                s_code = str(row.get("shift_code") or "")
                rep_id = str(row.get("id") or f"SHIFT_{b_date}_{s_code}_{idx}")
                seen_ids.add(rep_id)
                existing = db.get(ShiftReportRecord, rep_id)
                if existing is None:
                    existing = ShiftReportRecord(report_id=rep_id)
                    db.add(existing)
                existing.business_date = b_date
                existing.shift_code = s_code
                existing.cash_vnd = int(row.get("cash_vnd") or 0)
                existing.bank_transfer_vnd = int(row.get("bank_transfer_vnd") or 0)
                existing.total_collected_vnd = int(row.get("total_collected_vnd") or 0)
                existing.status = str(row.get("status") or "APPROVED")
                existing.signed_by = str(row.get("signed_by") or "")
                existing.payload = row
                existing.updated_at = datetime.now()
            if seen_ids:
                db.query(ShiftReportRecord).filter(~ShiftReportRecord.report_id.in_(seen_ids)).delete(synchronize_session=False)
            else:
                db.query(ShiftReportRecord).delete(synchronize_session=False)
            db.commit()
    except Exception:
        pass


def _save_raw_shift_data(data: list[dict[str, Any]]) -> bool:
    """Lưu toàn bộ báo cáo ca vào file JSON persistent một cách nguyên tử (atomic) và đồng bộ CSDL."""
    with _SHIFT_LOCK:
        try:
            SHIFT_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = SHIFT_DATA_FILE.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, SHIFT_DATA_FILE)
            _sync_shift_reports_to_db(data)
            return True
        except Exception as e:
            print(f"[shift_service] Lỗi lưu {SHIFT_DATA_FILE}: {e}")
            return False


def _get_seed_shift_reports() -> list[dict[str, Any]]:
    """Khởi tạo dữ liệu thực tế mẫu từ các bức ảnh sổ chốt ngày 14/10/2026 của cửa hàng Mixue 39 Tôn Quang Phiệt."""
    return [
        {
            "id": "SHIFT_20261014_SANG",
            "business_date": "2026-10-14",
            "shift_code": "CA_SANG",
            "shift_name": "1. Ca sáng bàn giao (8h-13h)",
            "cash_vnd": 653000,
            "cash_diff_vnd": 0,
            "bank_transfer_vnd": 1591000,
            "bank_transfer_formula": "962 + 629",
            "shopee_food_vnd": 16000,
            "grab_food_vnd": 30000,
            "be_food_vnd": 0,
            "petty_cash_kept_vnd": 1000000,
            "expenses_vnd": 0,
            "expenses_details": [],
            "total_collected_vnd": 2328000,
            "signed_by": "Hà",
            "notes": "Ca sáng bàn giao két 1,000,000đ và tổng tiền thu về 2,328k.",
            "image_filename": "20261014_ca_sang_chieu.jpg",
            "image_path": str(SHIFT_PHOTOS_DIR / "20261014_ca_sang_chieu.jpg"),
            "status": "APPROVED",
            "created_by": "ha_bar",
            "created_at": "2026-10-14T13:05:00+07:00"
        },
        {
            "id": "SHIFT_20261014_CHIEU",
            "business_date": "2026-10-14",
            "shift_code": "CA_CHIEU",
            "shift_name": "2. Ca chiều bàn giao (13h-18h)",
            "cash_vnd": 2014000,
            "cash_diff_vnd": 20000,
            "bank_transfer_vnd": 3861000,
            "bank_transfer_formula": "1630 + 1221 + 1010",
            "shopee_food_vnd": 83000,
            "grab_food_vnd": 95000,
            "be_food_vnd": 0,
            "petty_cash_kept_vnd": 1000000,
            "expenses_vnd": 0,
            "expenses_details": [],
            "total_collected_vnd": 6090000,
            "signed_by": "Nhi",
            "notes": "Tiền mặt dư 20k. Bàn giao két 1,000,000đ. Tổng thu về ca chiều 6,090k.",
            "image_filename": "20261014_ca_sang_chieu.jpg",
            "image_path": str(SHIFT_PHOTOS_DIR / "20261014_ca_sang_chieu.jpg"),
            "status": "APPROVED",
            "created_by": "nhi_bar",
            "created_at": "2026-10-14T18:10:00+07:00"
        },
        {
            "id": "SHIFT_20261014_TOI",
            "business_date": "2026-10-14",
            "shift_code": "CA_TOI",
            "shift_name": "3. Ca tối & Chốt tổng hợp cả ngày (18h-23h)",
            "cash_vnd": 3260000,
            "cash_diff_vnd": 35000,
            "bank_transfer_vnd": 6377000,
            "bank_transfer_formula": "4725 + 1652",
            "shopee_food_vnd": 115000,
            "grab_food_vnd": 104000,
            "be_food_vnd": 0,
            "petty_cash_kept_vnd": 1000000,
            "expenses_vnd": 56000,
            "expenses_details": [
                {"item": "Tiền ship sạc đt hotline", "amount": 41000},
                {"item": "Ship đơn", "amount": 15000}
            ],
            "total_collected_vnd": 9877000,
            "signed_by": "An",
            "notes": "Dư 35k tiền mặt. Đã trừ 56k chi phí (41k sạc đt + 15k ship). An chốt sổ và cầm tiền mặt.",
            "image_filename": "20261014_ca_toi_tong_ket.jpg",
            "image_path": str(SHIFT_PHOTOS_DIR / "20261014_ca_toi_tong_ket.jpg"),
            "pos_slip_image": "20261014_pos_slip.jpg",
            "pos_revenue_vnd": 10119000,
            "pos_discounts_vnd": -217000,
            "pos_collected_vnd": 9877137,
            "variance_pos_vnd": -137,
            "status": "APPROVED",
            "created_by": "an_quanly",
            "created_at": "2026-10-14T23:25:00+07:00"
        }
    ]


def build_ocr_field_edits(extracted: dict[str, Any], confirmed_values: dict[str, int | None]) -> dict[str, Any]:
    """Compare OCR reading against user-confirmed values to build field-level audit & evaluation log."""
    readings = extracted.get("field_readings") or {}
    field_edits: dict[str, dict[str, Any]] = {}
    corrected_fields: list[str] = []
    manual_fields: list[str] = []

    for field, final_val in confirmed_values.items():
        r = readings.get(field, {})
        ocr_status = r.get("status", "not_present")
        ocr_val = r.get("value")
        norm_val = r.get("normalized_value")
        auto_filled_val = extracted.get(field)

        if auto_filled_val is not None:
            if auto_filled_val == final_val:
                action = "confirmed_as_is"
            else:
                action = "corrected_ocr_value"
                corrected_fields.append(field)
        else:
            manual_fields.append(field)
            if ocr_status == "uncertain":
                if ocr_val is not None and ocr_val != final_val:
                    corrected_fields.append(field)
                action = "confirmed_uncertain" if ocr_val == final_val else "edited_uncertain"
            elif ocr_status == "unreadable":
                action = "completed_unreadable"
            else:
                action = "completed_missing"

        field_edits[field] = {
            "raw_text": r.get("raw_text", ""),
            "ocr_value": ocr_val,
            "normalized_value": norm_val,
            "auto_filled_value": auto_filled_val,
            "user_final_value": final_val,
            "ocr_status": ocr_status,
            "source": r.get("source", "unknown"),
            "review_reason": r.get("review_reason", ""),
            "action": action,
        }

    return {
        "field_edits": field_edits,
        "corrected_fields": corrected_fields,
        "manual_fields": manual_fields,
    }


def record_ocr_user_edits(
    *,
    report_id: str,
    business_date: str,
    shift_code: str,
    confirmed_by: str,
    store_id: str = "2132",
    extracted: dict[str, Any],
    confirmed_values: dict[str, int | None],
    review_seconds: float | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Persist structured OCR edit record for quality evaluation and pilot monitoring."""
    edit_summary = build_ocr_field_edits(extracted, confirmed_values)
    record = {
        "report_id": report_id,
        "business_date": business_date,
        "shift_code": shift_code,
        "store_id": store_id,
        "confirmed_by": confirmed_by,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "mode": "vision" if extracted.get("status") == "NEEDS_REVIEW" else "manual",
        "image_sha256": extracted.get("image_sha256"),
        "model": extracted.get("model"),
        "extracted_at": extracted.get("extracted_at"),
        "document_date": extracted.get("document_date"),
        "document_type": extracted.get("document_type", "unknown"),
        "consistency": extracted.get("consistency", {}),
        "field_readings": extracted.get("field_readings", {}),
        "field_edits": edit_summary["field_edits"],
        "corrected_fields": edit_summary["corrected_fields"],
        "manual_fields": edit_summary["manual_fields"],
        "review_seconds": review_seconds,
    }
    target_log = log_path or OCR_EDITS_LOG_FILE
    try:
        target_log.parent.mkdir(parents=True, exist_ok=True)
        with open(target_log, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return record


def validate_shift_report_payload(
    report_dict: dict[str, Any],
    *,
    actor_role: str | None = None,
    require_admin_for_approval: bool = False,
) -> tuple[bool, str]:
    """Validate shift report fields and permissions before saving."""
    if require_admin_for_approval:
        from src.auth import is_admin_role
        if not is_admin_role(actor_role):
            return False, "Tài khoản hiện tại không có quyền phê duyệt báo cáo chốt ca."

    b_date = report_dict.get("business_date") or report_dict.get('report_date') or report_dict.get("date")
    if not b_date or report_dict.get('shift_code') not in SHIFT_DEFINITIONS:
        return False, 'Cần ngày làm việc và mã ca hợp lệ.'
    if report_dict.get('report_scope', 'daily_cumulative' if report_dict.get('shift_code') == 'CA_TOI' else 'per_shift') not in {'per_shift', 'daily_cumulative'}:
        return False, 'Loại báo cáo ca không hợp lệ.'
    if b_date:
        try:
            date.fromisoformat(str(b_date))
        except ValueError:
            return False, f"Ngày làm việc '{b_date}' không hợp lệ (định dạng chuẩn YYYY-MM-DD)."

    for key in (*REQUIRED_SHIFT_MONEY_FIELDS, 'pos_revenue_vnd', 'pos_collected_vnd'):
        val = report_dict.get(key)
        if val is not None:
            try:
                num = float(val)
            except (TypeError, ValueError):
                return False, f"Trường {key} có giá trị không hợp lệ."
            if isinstance(val, bool) or not math.isfinite(num) or not num.is_integer() or abs(num) > 500_000_000:
                return False, f'Trường {key} phải là số tiền nguyên hữu hạn trong giới hạn cho phép.'
            if key != "cash_diff_vnd" and num < 0:
                return False, f"Trường {key} không được âm."
    return True, "OK"


def get_all_shift_reports(business_date: str | date | None = None) -> list[dict[str, Any]]:
    """Lấy danh sách tất cả các báo cáo ca, có thể lọc theo ngày."""
    data = _load_raw_shift_data()
    if not business_date:
        return sorted(data, key=lambda x: (x.get("business_date", ""), x.get("shift_code", "")), reverse=True)

    d_str = business_date.isoformat() if isinstance(business_date, date) else str(business_date)
    filtered = [r for r in data if r.get("business_date") == d_str]
    return sorted(filtered, key=lambda x: x.get("shift_code", ""))


def latest_shift_report_date() -> date:
    """Most recent business date that has a shift report; today (Vietnam time) if none."""
    from datetime import timedelta
    dates = []
    for row in get_all_shift_reports():
        try:
            dates.append(date.fromisoformat(str(row.get("business_date") or row.get("report_date"))[:10]))
        except ValueError:
            continue
    return max(dates) if dates else datetime.now(timezone(timedelta(hours=7))).date()


def get_shift_report_by_id(report_id: str) -> dict[str, Any] | None:
    """Tìm một báo cáo ca theo ID."""
    data = _load_raw_shift_data()
    for r in data:
        if r.get("id") == report_id or r.get("shift_id") == report_id:
            return r
    return None


def save_or_update_shift_report(
    report_dict: dict[str, Any],
    *,
    actor_role: str | None = None,
    actor_username: str | None = None,
    require_admin_for_approval: bool = True,
) -> tuple[bool, str, dict[str, Any]]:
    """Lưu mới hoặc cập nhật một báo cáo chốt ca."""
    from src.auth import is_admin_role
    from src.database import SessionLocal
    from src.models import User
    with SessionLocal() as db:
        actor = db.get(User, actor_username) if actor_username else None
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, 'Chỉ quản lý đang hoạt động được ghi sổ báo cáo ca.', report_dict
        actor_role = actor.role
    report_dict = dict(report_dict)
    if report_dict.get('report_date'):
        report_dict.setdefault('business_date', report_dict['report_date'])

    with _SHIFT_LOCK:
        data = _load_raw_shift_data()
        rep_id = report_dict.get("id") or report_dict.get("shift_id")
        existing_index = next((i for i, item in enumerate(data) if
            (rep_id and rep_id in {item.get('id'), item.get('shift_id')}) or
            (report_dict.get('business_date') and report_dict.get('shift_code')
             and item.get('business_date') == report_dict['business_date']
             and item.get('shift_code') == report_dict['shift_code'])), None)
        original_patch = report_dict
        report_dict = {**(data[existing_index] if existing_index is not None else {}), **original_patch}
        rep_id = report_dict.get('id') or report_dict.get('shift_id')
        report_dict.setdefault('report_scope', 'daily_cumulative' if report_dict.get('shift_code') == 'CA_TOI' else 'per_shift')
        # Recompute after merging, but preserve an explicitly reviewed total.
        if any(k in original_patch for k in REQUIRED_SHIFT_MONEY_FIELDS) and original_patch.get('total_collected_vnd') is None:
            report_dict['total_collected_vnd'] = None
        valid, err_msg = validate_shift_report_payload(report_dict, actor_role=actor_role, require_admin_for_approval=True)
        if not valid:
            return False, err_msg, report_dict

        if not rep_id:
            b_date = report_dict.get("business_date") or report_dict.get("date") or date.today().isoformat()
            s_code = report_dict.get("shift_code") or report_dict.get("shift_type") or "CA_SANG"
            rep_id = f"SHIFT_{str(b_date).replace('-', '')}_{s_code}_{uuid.uuid4().hex[:6]}"
            report_dict["id"] = rep_id
            report_dict["created_at"] = datetime.now().isoformat()

        report_dict["updated_at"] = datetime.now().isoformat()

        # Tính toán lại tổng thu về nếu chưa có và không phải bản cập nhật một phần (partial update)
        has_money_keys = any(k in report_dict for k in REQUIRED_SHIFT_MONEY_FIELDS)
        if has_money_keys and report_dict.get("total_collected_vnd") is None:
            cash = float(report_dict.get("cash_vnd", 0) or 0)
            bank = float(report_dict.get("bank_transfer_vnd", 0) or 0)
            shopee = float(report_dict.get("shopee_food_vnd", 0) or 0)
            grab = float(report_dict.get("grab_food_vnd", 0) or 0)
            be = float(report_dict.get("be_food_vnd", 0) or 0)
            exp = float(report_dict.get("expenses_vnd", 0) or 0)
            diff = float(report_dict.get("cash_diff_vnd", 0) or 0)
            # cash_vnd is the cash counted; the total is built on the cash that should have been there.
            report_dict["total_collected_vnd"] = cash - diff + bank + shopee + grab + be - exp
        if report_dict.get('cash_vnd') is None or report_dict.get('total_collected_vnd') is None:
            return False, 'Cần xác nhận tiền mặt và tổng thu về; không có phát sinh thì nhập 0.', report_dict
        valid, err_msg = validate_shift_report_payload(report_dict, actor_role=actor_role, require_admin_for_approval=True)
        if not valid:
            return False, err_msg, report_dict

        updated = False
        b_date_val = report_dict.get("business_date")
        s_code_val = report_dict.get("shift_code")
        for idx, item in enumerate(data):
            id_match = rep_id and (item.get("id") == rep_id or item.get("shift_id") == rep_id)
            date_shift_match = (
                b_date_val is not None
                and s_code_val is not None
                and item.get("business_date") == b_date_val
                and item.get("shift_code") == s_code_val
            )
            if id_match or date_shift_match:
                merged_item = dict(item)
                merged_item.update(report_dict)
                data[idx] = merged_item
                report_dict = merged_item
                updated = True
                break

        if not updated:
            data.append(report_dict)

        ok = _save_raw_shift_data(data)
        if ok:
            msg = f"Đã lưu thành công báo cáo chốt ca '{report_dict.get('shift_name', rep_id)}' ngày {report_dict.get('business_date') or report_dict.get('date')}!"
            return True, msg, report_dict
        return False, "Lỗi ghi dữ liệu vào hệ thống lưu trữ.", report_dict


def delete_shift_report(report_id: str, *, delete_uploaded_image: bool = False, actor_username=None) -> tuple[bool, str]:
    """Xóa một báo cáo chốt ca theo ID."""
    from src.auth import is_admin_role
    from src.database import SessionLocal
    from src.models import User
    with SessionLocal() as db:
        actor = db.get(User, actor_username) if actor_username else None
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, 'Chỉ quản lý đang hoạt động được xóa báo cáo ca.'
    with _SHIFT_LOCK:
        data = _load_raw_shift_data()
        removed = [r for r in data if r.get("id") == report_id or r.get("shift_id") == report_id]
        new_data = [r for r in data if r.get("id") != report_id and r.get("shift_id") != report_id]
        if len(new_data) == len(data):
            return False, "Không tìm thấy báo cáo ca cần xóa."
        ok = _save_raw_shift_data(new_data)
        if ok and delete_uploaded_image:
            uploads_dir = SHIFT_UPLOADS_DIR.resolve()
            for r in removed:
                img_path_str = r.get("image_path")
                if img_path_str:
                    p = Path(img_path_str).resolve()
                    if p.is_file() and uploads_dir in p.parents:
                        try:
                            p.unlink()
                        except OSError:
                            pass
        return ok, "Đã xóa báo cáo chốt ca thành công." if ok else "Lỗi khi lưu dữ liệu."


def get_daily_closing_summary(business_date: str | date) -> dict[str, Any]:
    """Tính toán và đối soát bảng tổng hợp doanh thu cuối ngày cho toàn bộ các ca."""
    d_str = business_date.isoformat() if isinstance(business_date, date) else str(business_date)
    shifts = [s for s in get_all_shift_reports(d_str) if s.get("status", "APPROVED") == "APPROVED"]

    toi_shift = next((s for s in shifts if s.get("shift_code") == "CA_TOI"), None)
    sang_shift = next((s for s in shifts if s.get("shift_code") == "CA_SANG"), None)
    chieu_shift = next((s for s in shifts if s.get("shift_code") == "CA_CHIEU"), None)

    if toi_shift and toi_shift.get('report_scope', 'daily_cumulative') == 'daily_cumulative':
        total_cash = float(toi_shift.get("cash_vnd", 0))
        total_bank = float(toi_shift.get("bank_transfer_vnd", 0))
        total_shopee = float(toi_shift.get("shopee_food_vnd", 0))
        total_grab = float(toi_shift.get("grab_food_vnd", 0))
        total_be = float(toi_shift.get("be_food_vnd", 0))
        total_expenses = float(toi_shift.get("expenses_vnd", 0))
        total_collected = float(toi_shift.get("total_collected_vnd", 0))
        signed_closing = toi_shift.get("signed_by", "An")
        notes_closing = toi_shift.get("notes", "")
    else:
        total_cash = sum(float(s.get("cash_vnd", 0) or 0) for s in shifts)
        total_bank = sum(float(s.get("bank_transfer_vnd", 0) or 0) for s in shifts)
        total_shopee = sum(float(s.get("shopee_food_vnd", 0) or 0) for s in shifts)
        total_grab = sum(float(s.get("grab_food_vnd", 0) or 0) for s in shifts)
        total_be = sum(float(s.get("be_food_vnd", 0) or 0) for s in shifts)
        total_expenses = sum(float(s.get("expenses_vnd", 0) or 0) for s in shifts)
        total_collected = sum(float(s.get("total_collected_vnd", 0) or 0) for s in shifts)
        signed_closing = ", ".join(filter(None, [s.get("signed_by") for s in shifts]))
        notes_closing = "Tổng hợp cộng dồn từ các ca trong ngày."

    pos_rev = 0.0
    from sqlalchemy import func

    from src.database import SessionLocal
    from src.models import SalesDaily

    db = SessionLocal()
    try:
        p_d = date.fromisoformat(d_str)
        store_id = resolve_store_id(db)
        q_pos = db.query(func.sum(SalesDaily.revenue_vnd)).filter(SalesDaily.business_date == p_d, SalesDaily.store_id == store_id).scalar()
        if q_pos:
            pos_rev = float(q_pos)
    except Exception as e:
        print(f"[shift_service] Lỗi truy vấn POS: {e}")
    finally:
        db.close()

    if toi_shift and toi_shift.get("pos_revenue_vnd"):
        pos_rev = float(toi_shift.get("pos_revenue_vnd"))

    pos_collected = float(toi_shift.get("pos_collected_vnd", pos_rev) if toi_shift else pos_rev)
    variance = total_collected - pos_collected if pos_collected > 0 else 0

    return {
        "business_date": d_str,
        "shift_count": len(shifts),
        "shifts": shifts,
        "has_morning": sang_shift is not None,
        "has_afternoon": chieu_shift is not None,
        "has_evening": toi_shift is not None,
        "total_cash_vnd": total_cash,
        "total_bank_vnd": total_bank,
        "total_shopee_vnd": total_shopee,
        "total_grab_vnd": total_grab,
        "total_be_vnd": total_be,
        "total_delivery_apps_vnd": total_shopee + total_grab + total_be,
        "total_expenses_vnd": total_expenses,
        "total_collected_vnd": total_collected,
        "pos_revenue_vnd": pos_rev,
        "pos_collected_vnd": pos_collected,
        "variance_pos_vnd": variance,
        "signed_by": signed_closing,
        "notes": notes_closing,
        "is_fully_closed": (sang_shift is not None and chieu_shift is not None and toi_shift is not None)
    }


def extract_shift_data_from_image(
    image_bytes: bytes | list[bytes] | None = None,
    image_path: str | Path | list[str | Path] | None = None,
    images: list[bytes | str | Path] | None = None,
    image_paths: list[str | Path] | None = None,
    shift_hint: str | None = None,
    target_date: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Read actual image content; return a review draft, never sample figures."""
    from src.engine.vision_ocr import extract_image
    return extract_image(
        image_bytes=image_bytes,
        image_path=image_path,
        images=images,
        image_paths=image_paths,
        shift_hint=shift_hint,
        target_date=target_date,
        **kwargs,
    )


extract_shift_image_with_ai = extract_shift_data_from_image
upsert_shift_report = save_or_update_shift_report
