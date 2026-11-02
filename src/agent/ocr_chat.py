"""OCR inside the chat (Trụ cột 1 x Trụ cột 2).

Mixed into ``MixueOperationsAgent``: attaches shift photos, reads them through the
verifiable OCR pipeline, edits drafts, routes OCR/governance intents to server-side tool
calls, and confirms drafts only from the LangGraph approval node (or an explicit cancel).
Relies on the host agent for ``_actor``, ``_conversation_owner``, ``_ensure_store``,
``_runtime`` and ``_conversation_id``.
"""
from __future__ import annotations

from datetime import datetime, timezone

import re
from typing import Any

from src.engine.plan_service import list_plans


def _normalize_vn(text: str) -> str:
    from src.agent.mixue_agent import _normalize_vn as normalize
    return normalize(text)


def _parse_query_date_range(query: str, *args, **kwargs):
    from src.agent.mixue_agent import _parse_query_date_range as parse
    return parse(query, *args, **kwargs)


class OcrChatMixin:

    def attach_shift_image(
        self,
        image_bytes: bytes,
        filename: str = "shift_photo.jpg",
        mime_type: str = "image/jpeg",
        user_role: str = "MANAGER",
        user_name: str = "Quản lý",
        *,
        user_id=None,
    ) -> dict[str, Any]:
        """Register an uploaded shift image and issue a server-generated file_id bound to (account, store, conversation)."""
        import hashlib
        from pathlib import Path
        actor = self._actor(user_role, user_name, user_id)
        owner = self._conversation_owner(actor)
        store = self._ensure_store()
        if not image_bytes:
            raise ValueError("Dữ liệu ảnh trống.")
        sha256 = hashlib.sha256(image_bytes).hexdigest()
        ext = Path(filename or "shift.jpg").suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"
        from src.runtime_settings import ROOT as _ROOT, setting as _setting
        attach_dir = Path(_setting("CHAT_ATTACHMENTS_DIR") or _ROOT / "data" / "shift_photos" / "chat_attachments")
        attach_dir.mkdir(parents=True, exist_ok=True)
        safe_path = attach_dir / f"{owner[:12]}_{self._conversation_id[:8]}_{sha256[:12]}{ext}"
        safe_path.write_bytes(image_bytes)
        reg = store.register_attachment(
            owner,
            self._conversation_id,
            store_id=actor.store_id,
            user_id=actor.user_id,
            filename=Path(filename or "shift.jpg").name,
            mime_type=mime_type,
            sha256=sha256,
            size_bytes=len(image_bytes),
            storage_path=str(safe_path),
        )
        file_id = reg['file_id'] if isinstance(reg, dict) else reg
        return {
            "status": "SUCCESS",
            "file_id": file_id,
            "filename": Path(filename or "shift.jpg").name,
            "conversation_id": self._conversation_id,
            "store_id": actor.store_id,
            "user_id": actor.user_id,
        }

    def _format_ocr_draft_message(self, draft: dict[str, Any], prefix: str = "") -> str:
        """Render the OCR shift draft with document type, consistency check, unclear fields, and confirmation prompt."""
        doc_labels = {
            "pos_receipt": "🧾 Hóa đơn in máy POS (`pos_receipt`)",
            "handwritten_ledger": "📝 Sổ chốt ca viết tay (`handwritten_ledger`)",
            "composite": "🧾+📝 Ảnh ghép nhiều chứng từ: Hóa đơn POS + Sổ viết tay (`composite`)",
            "unknown": "📄 Chứng từ chốt ca (`unknown`)",
        }
        field_labels = {
            "pos_revenue_vnd": "Tổng doanh thu POS",
            "pos_collected_vnd": "Thực thu trên POS",
            "cash_vnd": "Tiền mặt thực đếm",
            "cash_diff_vnd": "Lệch tiền mặt (dư/thiếu)",
            "petty_cash_kept_vnd": "Tiền lẻ giữ két cố định",
            "bank_transfer_vnd": "Chuyển khoản ngân hàng",
            "shopee_food_vnd": "ShopeeFood",
            "be_food_vnd": "BeFood",
            "grab_food_vnd": "GrabFood",
            "expenses_vnd": "Khoản chi trong ca",
            "total_collected_vnd": "Tổng thực thu bàn giao",
        }
        fields = draft.get("fields", {})
        readings = draft.get("field_readings", {})
        meta = draft.get("meta") or {}
        suggestions = {k: v for k, v in (meta.get("suggestions") or {}).items() if fields.get(k) is None}
        consistency = draft.get("consistency", {})
        uncertain = draft.get("uncertain_fields", [])

        f_ids = draft.get("file_ids") or ([draft.get("file_id")] if draft.get("file_id") else [])
        f_names = draft.get("filenames") or []
        if len(f_ids) > 1:
            file_meta = f"**{len(f_ids)} tệp:** " + ", ".join(f"`{f}`" for f in f_ids)
            if f_names:
                file_meta += f" *({', '.join(f_names)})*"
        else:
            file_meta = f"`{draft.get('file_id')}`"
            if f_names:
                file_meta += f" *({f_names[0]})*"

        lines = [
            f"{prefix}### 📸 Dự Thảo Chốt Ca Từ Ảnh (`{draft['draft_id']}`)",
            f"- **Mã tệp máy chủ:** {file_meta} · **Trạng thái:** `Đang chờ xác nhận (Chưa ghi doanh thu)`",
            f"- **Loại chứng từ nhận diện:** {doc_labels.get(draft.get('document_type', 'unknown'), draft.get('document_type', 'unknown'))}",
            f"- **Ngày báo cáo:** `{fields.get('report_date') or 'Chưa rõ (cần xác nhận)'}` · **Ca làm việc:** `{fields.get('shift_code') or 'Chưa rõ (cần xác nhận)'}` · **Người ký:** `{fields.get('signed_by') or 'Chưa rõ'}`",
        ]
        if draft.get("pos_region_text") or draft.get("handwritten_region_text"):
            if draft.get("pos_region_text"):
                lines.append(f"- **Vùng hóa đơn POS:** {draft['pos_region_text'][:180]}")
            if draft.get("handwritten_region_text"):
                lines.append(f"- **Vùng sổ viết tay:** {draft['handwritten_region_text'][:180]}")

        lines.append("\n**1. Số liệu trong biểu mẫu dự thảo:**")
        for k, label in field_labels.items():
            val = fields.get(k)
            r = readings.get(k, {})
            src = r.get("source", "unknown")
            raw_t = r.get("raw_text") or ""
            if val is not None:
                lines.append(f"- **{label}:** **{int(val):,} đ** *(nguồn: `{src}`" + (f", đọc thô: `{raw_t}`)*" if raw_t else ")*"))
            elif r.get("status") in {"uncertain", "unreadable"} or k in uncertain:
                norm_v = r.get("normalized_value")
                hint = suggestions.get(k) or {}
                norm_hint = (f", **gợi ý: {int(hint['value']):,} đ** ({hint.get('basis', '')})" if hint.get("value") is not None
                             else f", gợi ý chuẩn hóa: `{norm_v:,} đ`" if isinstance(norm_v, int) else "")
                reason = r.get("review_reason") or "Chưa rõ đơn vị hoặc cần xác nhận"
                lines.append(f"- **{label}:** ⚠️ **[Để trống chờ xác nhận]** *(đọc thô: `{raw_t or '—'}`{norm_hint} — {reason})*")

        discrepancies = consistency.get("discrepancies", [])
        cash_note = (consistency.get("shift_check") or {}).get("cash_explanation")
        if cash_note:
            lines.append(f"\n💵 {cash_note}")
        if discrepancies:
            lines.append("\n**2. ⚠️ Cảnh báo đối soát nhất quán (Hệ thống giữ nguyên số gốc, không tự sửa số):**")
            for d in discrepancies:
                lines.append(f"- ❌ {d['message']}")
        else:
            lines.append("\n**2. ✅ Kiểm tra nhất quán:** Các khoản đã xác nhận hiện khớp nhau.")

        shift_names = {"CA_SANG": "Ca sáng", "CA_CHIEU": "Ca chiều", "CA_TOI": "Ca tối"}
        detected = meta.get("detected_shifts") or []
        if len(detected) > 1:
            lines.append("\n📑 **Ảnh có nhiều ca:** " + ", ".join(shift_names.get(x, x) for x in detected)
                         + f". Dự thảo này lấy số của **{shift_names.get(fields.get('shift_code'), fields.get('shift_code'))}**; "
                         "muốn ca khác, nhắn ví dụ `đọc lại ảnh cho ca chiều`.")
        if not meta.get("shift_present", True):
            lines.append("\n⚠️ Ảnh không có mục của ca này; các ô để trống.")
        if suggestions:
            lines.append(f"\n💡 Có **{len(suggestions)} ô có số gợi ý** (quy đổi số viết tắt ×1.000, cộng biểu thức). "
                         "Nhắn **`dùng số gợi ý`** để điền tất cả, hoặc sửa từng ô bằng lời.")
        if uncertain:
            uncertain_vi = [field_labels.get(f, f) for f in uncertain]
            lines.append(
                "\n**3. ❓ Phần chưa rõ cần bạn xác nhận hoặc bổ sung:**\n"
                + f"Bạn vui lòng kiểm tra và xác nhận các trường: **{', '.join(uncertain_vi)}**.\n"
                + "*Bạn có thể sửa trực tiếp trên biểu mẫu bên dưới hoặc nhắn tin (ví dụ: `Sửa tiền mặt thành 9657300, ShopeeFood 115837, ca tối ngày 14/10/2026`) trước khi bấm **Xác nhận & Lưu chốt ca**.*"
            )
        else:
            lines.append(
                "\n**3. ⏳ Chờ xác nhận:**\n"
                "*Dữ liệu đang ở trạng thái dự thảo. Bạn có thể sửa từng trường hoặc bấm **Xác nhận & Lưu chốt ca** để ghi vào sổ doanh thu.*"
            )
        return "\n".join(lines)

    def tool_inspect_attached_shift_image(
        self,
        file_id: str | None = None,
        shift_code: str | None = None,
        report_date: str | None = None,
        *,
        file_ids: list[str] | None = None,
        model=None,
    ) -> dict[str, Any]:
        """Read attached shift image(s) by server-issued file_id(s) and create a conversation-scoped OCR draft."""
        from pathlib import Path
        from src.engine.shift_service import extract_shift_image_with_ai
        from src.engine.vision_ocr import MONEY_FIELDS

        ids: list[str] = []
        if file_ids:
            ids.extend(str(f).strip() for f in file_ids if str(f).strip())
        elif file_id:
            ids.append(str(file_id).strip())

        if not ids:
            return {
                "status": "INVALID_FILE_ID",
                "message": "Chỉ chấp nhận mã tệp do máy chủ cấp (FILE_...), không cho phép truyền đường dẫn tệp tùy ý.",
            }

        for fid in ids:
            if not re.fullmatch(r"^FILE_[A-F0-9]{16}$", fid):
                return {
                    "status": "INVALID_FILE_ID",
                    "message": f"Mã tệp '{fid}' không hợp lệ. Chỉ chấp nhận mã tệp do máy chủ cấp (FILE_...).",
                }

        actor = getattr(self, "_current_actor", None) or self._actor("MANAGER", "Quản lý")
        owner = self._conversation_owner(actor)
        store = self._ensure_store()

        image_bytes_list: list[bytes] = []
        filenames: list[str] = []
        for fid in ids:
            attachment = store.get_attachment(
                owner, self._conversation_id, fid, store_id=actor.store_id, user_id=actor.user_id,
            )
            if not attachment:
                return {
                    "status": "FORBIDDEN",
                    "message": f"Mã tệp ảnh {fid} không tồn tại hoặc không thuộc tài khoản, cửa hàng và cuộc trò chuyện hiện tại.",
                }
            storage_path = Path(attachment["storage_path"])
            if not storage_path.is_file():
                return {
                    "status": "FILE_NOT_FOUND",
                    "message": f"Không tìm thấy dữ liệu tệp {fid} trên máy chủ.",
                }
            image_bytes_list.append(storage_path.read_bytes())
            filenames.append(attachment.get("filename") or fid)

        extracted = extract_shift_image_with_ai(
            image_bytes=image_bytes_list[0] if len(image_bytes_list) == 1 else None,
            images=image_bytes_list if len(image_bytes_list) > 1 else None,
            shift_hint=shift_code,
            target_date=report_date,
            model=model or getattr(self, "_ocr_model_override", None),
        )
        if extracted.get("status") not in {"SUCCESS", "NEEDS_REVIEW"}:
            err_reason = extracted.get("warning") or extracted.get("message") or "OCR thất bại."
            return {
                "status": extracted.get("status", "OCR_FAILED"),
                "file_id": ids[0],
                "file_ids": ids,
                "message": (
                    f"⚠️ **Chưa đọc được ảnh chốt ca (`{extracted.get('status', 'OCR_FAILED')}`):** "
                    f"{err_reason}\n\n"
                    "Hệ thống **không nhận là đã đọc ảnh** và **không tạo dự thảo tự động** khi OCR thất bại. "
                    "Bạn vui lòng gửi lại ảnh rõ nét hơn hoặc nhập số liệu thủ công."
                ),
                "ocr_result": extracted,
                "source_refs": [f"attachment:{fid}" for fid in ids],
            }

        draft_fields: dict[str, Any] = {
            "report_date": extracted.get("report_date") or report_date,
            "shift_code": extracted.get("shift_code") or shift_code,
            "signed_by": extracted.get("signed_by") or "",
            "notes": extracted.get("notes") or "",
        }
        for mf in MONEY_FIELDS:
            draft_fields[mf] = extracted.get(mf)

        readings = extracted.get("field_readings", {})
        uncertain_fields: list[str] = []
        if not draft_fields.get("report_date"):
            uncertain_fields.append("report_date")
        if not draft_fields.get("shift_code"):
            uncertain_fields.append("shift_code")
        for mf in MONEY_FIELDS:
            r = readings.get(mf, {})
            if r.get("status") in {"uncertain", "unreadable"} or (
                mf in {"cash_vnd", "total_collected_vnd"} and draft_fields.get(mf) is None
            ):
                uncertain_fields.append(mf)

        initial_baseline = {mf: draft_fields.get(mf) for mf in MONEY_FIELDS}
        draft_payload = {
            "document_type": extracted.get("document_type", "unknown"),
            "pos_region_text": extracted.get("pos_region_text", ""),
            "handwritten_region_text": extracted.get("handwritten_region_text", ""),
            "fields": draft_fields,
            "initial_ocr_fields": initial_baseline,
            "field_readings": readings,
            "consistency": extracted.get("consistency", {}),
            "uncertain_fields": uncertain_fields,
            "user_edits": {},
            "warnings": [extracted["warning"]] if extracted.get("warning") else list(extracted.get("warnings", [])),
            "model": extracted.get("model", ""),
            "file_ids": ids,
            "filenames": filenames,
            "meta": {
                "suggestions": extracted.get("suggestions") or {},
                "detected_shifts": (extracted.get("day_sheet") or {}).get("detected_shifts", []),
                "shift_present": (extracted.get("day_sheet") or {}).get("shift_present", True),
            },
        }
        saved_draft = store.save_ocr_draft(
            owner,
            self._conversation_id,
            store_id=actor.store_id,
            user_id=actor.user_id,
            file_id=ids[0],
            draft_data=draft_payload,
        )
        msg = self._format_ocr_draft_message(saved_draft)
        return {
            "status": "SUCCESS",
            "text": msg,
            "draft_id": saved_draft["draft_id"],
            "file_id": ids[0],
            "file_ids": ids,
            "draft": saved_draft,
            "source_refs": [f"attachment:{fid}" for fid in ids] + [f"ocr_draft:{saved_draft['draft_id']}"],
        }


    def get_active_ocr_draft(self, draft_id: str | None = None) -> dict[str, Any] | None:
        return self.tool_get_shift_ocr_draft(draft_id)

    def process_image_message(
        self,
        image_bytes: bytes | None = None,
        user_query: str = "",
        filename: str = "shift_photo.jpg",
        user_role: str = "MANAGER",
        user_name: str = "Quản lý",
        *,
        file_bytes: bytes | list[bytes] | None = None,
        files: list[tuple[str, bytes]] | list[dict[str, Any]] | list[Any] | None = None,
        user_id=None,
        ocr_model=None,
    ) -> dict[str, Any]:
        """Full conversational flow: user sends image(s) -> attach -> identify doc type -> OCR -> verify -> show draft -> wait for confirmation."""
        file_list: list[tuple[bytes, str]] = []
        if files:
            for item in files:
                if isinstance(item, tuple) and len(item) >= 2:
                    if isinstance(item[0], str) and isinstance(item[1], (bytes, bytearray)):
                        file_list.append((bytes(item[1]), item[0]))
                    elif isinstance(item[1], str) and isinstance(item[0], (bytes, bytearray)):
                        file_list.append((bytes(item[0]), item[1]))
                elif isinstance(item, dict):
                    b = item.get("bytes") or item.get("file_bytes") or item.get("data")
                    name = item.get("filename") or item.get("name") or "photo.jpg"
                    if b:
                        file_list.append((bytes(b), str(name)))
                elif hasattr(item, "getvalue") and hasattr(item, "name"):
                    file_list.append((item.getvalue(), item.name))
        elif isinstance(file_bytes, list):
            for idx, b in enumerate(file_bytes):
                fn = filename[idx] if isinstance(filename, list) and idx < len(filename) else f"shift_photo_{idx+1}.jpg"
                file_list.append((b, fn))
        else:
            raw_bytes = image_bytes if image_bytes is not None else file_bytes
            if raw_bytes is not None:
                fn = filename if isinstance(filename, str) else "shift_photo.jpg"
                file_list.append((raw_bytes, fn))

        if not file_list:
            return {
                "status": "ERROR",
                "text": "⚠️ Cần cung cấp dữ liệu ảnh để xử lý.",
                "tool_called": "inspect_attached_shift_image",
                "raw_result": {"status": "INVALID_IMAGE"},
                "evidence_refs": [],
            }

        actor = self._actor(user_role, user_name, user_id)
        owner = self._conversation_owner(actor)
        store = self._ensure_store()

        attachments = []
        try:
            for b_data, fn in file_list:
                att = self.attach_shift_image(
                    b_data, filename=fn, user_role=user_role, user_name=user_name, user_id=user_id,
                )
                attachments.append(att)
        except Exception as exc:
            return {
                "status": "ERROR",
                "text": f"⚠️ Không thể đính kèm ảnh: {exc}",
                "tool_called": "inspect_attached_shift_image",
                "raw_result": {"status": "INVALID_IMAGE"},
                "evidence_refs": [],
            }

        file_ids = [att["file_id"] for att in attachments]
        primary_file_id = file_ids[0]

        q_norm = _normalize_vn(user_query or "")
        shift_hint = None
        if "ca sang" in q_norm:
            shift_hint = "CA_SANG"
        elif "ca chieu" in q_norm:
            shift_hint = "CA_CHIEU"
        elif "ca toi" in q_norm:
            shift_hint = "CA_TOI"
        report_date, _ = _parse_query_date_range(user_query or "")

        if user_query and user_query.strip():
            user_msg = user_query.strip()
        elif len(attachments) == 1:
            user_msg = f"[Đính kèm ảnh chốt ca: {attachments[0]['filename']} ({primary_file_id})]"
        else:
            files_desc = ", ".join(f"{a['filename']} ({a['file_id']})" for a in attachments)
            user_msg = f"[Đính kèm {len(attachments)} ảnh chứng từ/hóa đơn: {files_desc}]"

        store.append(owner, self._conversation_id, "user", user_msg, [f"attachment:{fid}" for fid in file_ids])

        # Step 1 of the chat OCR flow runs inside the LangGraph runtime (guard -> authorize ->
        # tools) so the call is RBAC-checked, schema-validated, traced and checkpointed in
        # both LLM and offline_rules modes. The file_ids are server-issued, never model output.
        args: dict[str, Any] = {"file_ids": file_ids}
        if shift_hint:
            args["shift_code"] = shift_hint
        if report_date:
            args["report_date"] = report_date
        self._ocr_model_override = ocr_model
        try:
            graph_result = self._runtime().invoke(
                user_msg, actor, self._conversation_id,
                forced_call={"name": "inspect_attached_shift_image", "args": args},
            )
        finally:
            self._ocr_model_override = None
        res = graph_result.get("raw_result") or {}
        if graph_result.get("pending_approval") and "draft_id" not in res:
            res = {"status": "PENDING_APPROVAL", "message": graph_result["text"]}
        if res.get("status") != "SUCCESS":
            reply_text = res.get("message", "Không đọc được ảnh chốt ca.")
            store.append(owner, self._conversation_id, "assistant", reply_text, [])
            return {
                "status": "ERROR",
                "text": reply_text,
                "tool_called": "inspect_attached_shift_image",
                "raw_result": res,
                "file_id": primary_file_id,
                "file_ids": file_ids,
                "pending_ocr_draft": None,
                "evidence_refs": [],
            }

        reply_text = res["text"]
        store.append(owner, self._conversation_id, "assistant", reply_text, res.get("source_refs", []))
        return {
            "status": "SUCCESS",
            "text": reply_text,
            "tool_called": "inspect_attached_shift_image",
            "execution_mode": graph_result.get("execution_mode"),
            "trace": graph_result.get("trace", []),
            "raw_result": res,
            "file_id": primary_file_id,
            "file_ids": file_ids,
            "draft_id": res.get("draft_id"),
            "draft": res.get("draft"),
            "pending_ocr_draft": res.get("draft"),
            "evidence_refs": res.get("source_refs", []),
        }

    def tool_view_shift_ocr_draft(self, draft_id: str | None = None) -> dict[str, Any]:
        """Read-only view of the pending OCR draft, formatted with sources and review reasons."""
        draft = self.tool_get_shift_ocr_draft(draft_id)
        if not draft:
            msg = ("Hiện chưa có dự thảo chốt ca OCR nào đang chờ trong cuộc trò chuyện này. "
                   "Hãy mở mục **📸 Đính kèm ảnh chứng từ** bên dưới khung chat để gửi ảnh sổ chốt ca hoặc hóa đơn POS.")
            return {"status": "NO_ACTIVE_DRAFT", "message": msg, "text": msg}
        return {
            "status": "SUCCESS",
            "text": self._format_ocr_draft_message(draft),
            "draft_id": draft["draft_id"],
            "draft": draft,
            "source_refs": [f"attachment:{fid}" for fid in (draft.get("file_ids") or [draft.get("file_id")]) if fid]
            + [f"ocr_draft:{draft['draft_id']}"],
        }

    def tool_get_governance_overview(self) -> dict[str, Any]:
        """RBAC + human-in-the-loop overview for the authenticated actor (never from model arguments)."""
        from src.auth import get_allowed_pages, is_admin_role

        actor = getattr(self, "_current_actor", None) or self._actor("MANAGER", "Quản lý")
        admin = is_admin_role(actor.role)
        runtime = self._runtime()
        allowed = [spec for spec in runtime.tools.values() if spec.allowed(actor.role)]
        denied = [spec.name for spec in runtime.tools.values() if not spec.allowed(actor.role)]
        by_effect: dict[str, list[str]] = {}
        for spec in allowed:
            by_effect.setdefault(spec.effect, []).append(spec.name)

        snapshot = runtime.graph.get_state(runtime._config(actor, self._conversation_id))
        pending = snapshot.interrupts[0].value if snapshot.interrupts else None
        draft = self.tool_get_shift_ocr_draft()
        plans = list_plans() if admin else []
        recent = plans[:5]

        effect_vi = {"read": "Chỉ đọc", "draft": "Tạo/sửa dự thảo", "approval": "Cần phê duyệt (interrupt)"}
        lines = [
            "### 🛡️ Quyền hạn & quản trị phê duyệt (RBAC + Human-in-the-Loop)",
            f"- **Tài khoản:** `{actor.user_id}` · **Họ tên:** {actor.name} · **Vai trò do máy chủ xác thực:** `{actor.role}`"
            + (" (Quản trị)" if admin else " (Nhân viên)"),
            f"- **Trang được truy cập:** {', '.join(get_allowed_pages(actor.role)) or 'Không có'}",
            "\n**Công cụ Agent được phép gọi:**",
        ]
        for effect in ("read", "draft", "approval"):
            if by_effect.get(effect):
                lines.append(f"- {effect_vi[effect]} ({len(by_effect[effect])}): " + ", ".join(f"`{n}`" for n in sorted(by_effect[effect])))
        if denied:
            lines.append(f"- 🔒 Bị chặn ở node `_authorize` ({len(denied)}): " + ", ".join(f"`{n}`" for n in sorted(denied)))
        lines.append("\n**Trạng thái phê duyệt trong cuộc trò chuyện này:**")
        if pending:
            lines.append(f"- ⏸️ Đang dừng tại `interrupt()`: **{pending.get('plan_id')}** ({pending.get('plan_type')}) — chờ bấm Phê duyệt/Hủy.")
        else:
            lines.append("- Không có bước `interrupt()` nào đang chờ.")
        if draft:
            lines.append(f"- 📸 Dự thảo OCR `{draft['draft_id']}`: {len(draft.get('missing_fields') or [])} trường còn thiếu"
                         + (" · đủ điều kiện gửi phê duyệt" if draft.get("is_complete") else ""))
        if admin:
            approved = sum(1 for p in plans if p.get("status") == "APPROVED")
            waiting = sum(1 for p in plans if p.get("status") == "PENDING_APPROVAL")
            lines.append(f"\n**Lịch sử kế hoạch (sơ chế/nhập hàng):** {len(plans)} kế hoạch · {approved} đã duyệt · {waiting} đang chờ duyệt")
            for p in recent:
                who = f" · duyệt bởi {p['approved_by']}" if p.get("approved_by") else ""
                lines.append(f"- `{p.get('plan_id')}` · {p.get('plan_type')} · ngày {p.get('target_date')} · **{p.get('status')}**{who}")
        else:
            lines.append("\n*Nhân viên không được xem lịch sử phê duyệt kế hoạch và không thể tự phê duyệt; mọi bước ghi sổ cần Quản lý.*")
        return {
            "status": "SUCCESS",
            "text": "\n".join(lines),
            "role": actor.role,
            "is_admin": admin,
            "allowed_tools": sorted(spec.name for spec in allowed),
            "denied_tools": sorted(denied),
            "pending_approval": pending,
            "recent_plans": [{k: p.get(k) for k in ("plan_id", "plan_type", "target_date", "status", "approved_by")} for p in recent],
            "source_refs": ["policy:Server_Side_RBAC", "checkpoint:langgraph"] + (["table:operation_plans"] if admin else []),
        }

    def tool_get_shift_ocr_draft(self, draft_id: str | None = None) -> dict[str, Any] | None:
        actor = getattr(self, "_current_actor", None) or self._actor("MANAGER", "Quản lý")
        owner = self._conversation_owner(actor)
        draft = self._ensure_store().get_active_ocr_draft(
            owner, self._conversation_id, store_id=actor.store_id, user_id=actor.user_id,
        )
        if draft and (draft_id is None or draft.get("draft_id") == draft_id):
            return draft
        return None

    def tool_update_shift_ocr_draft(self, draft_id: str | None = None, **field_updates) -> dict[str, Any]:
        """Update fields in the active OCR shift draft and re-run consistency checks."""
        from src.engine.vision_ocr import MONEY_FIELDS, MoneyReading, ShiftReading, check_ocr_consistency

        actor = getattr(self, "_current_actor", None) or self._actor("MANAGER", "Quản lý")
        owner = self._conversation_owner(actor)
        store = self._ensure_store()
        active = store.get_active_ocr_draft(
            owner, self._conversation_id, store_id=actor.store_id, user_id=actor.user_id,
        )
        if not active or (draft_id and active.get("draft_id") != draft_id):
            return {
                "status": "NO_ACTIVE_DRAFT",
                "message": "Hiện không có dự thảo chốt ca OCR nào đang chờ xác nhận trong cuộc trò chuyện này.",
            }

        clean_updates = {k: v for k, v in field_updates.items() if v is not None and k != "draft_id"}
        if not clean_updates:
            return {
                "status": "INVALID_UPDATE",
                "message": "Chưa có trường dữ liệu nào được chọn để cập nhật.",
            }

        fields = dict(active.get("fields", {}))
        readings = dict(active.get("field_readings", {}))
        for k, v in clean_updates.items():
            fields[k] = v
            if k in MONEY_FIELDS and k in readings:
                readings[k] = {
                    **readings[k],
                    "value": int(v),
                    "normalized_value": int(v),
                    "status": "read",
                    "review_reason": f"Đã được người dùng chỉnh sửa/xác nhận ({int(v):,} đ).",
                }

        # Re-run consistency check on updated monetary values
        reading_models = {}
        for mf in MONEY_FIELDS:
            r = readings.get(mf, {})
            val = fields.get(mf)
            reading_models[mf] = MoneyReading(
                value=int(val) if val is not None else None,
                normalized_value=int(val) if val is not None else r.get("normalized_value"),
                status="read" if val is not None else r.get("status", "not_present"),
                source=r.get("source", "unknown"),
                raw_text=str(r.get("raw_text", "")),
                is_calculated=bool(r.get("is_calculated", False)),
                unit_explicit=True if val is not None else bool(r.get("unit_explicit", True)),
                review_reason=str(r.get("review_reason", "")),
                evidence=str(r.get('evidence') or (f'Người dùng xác nhận: {val}' if val is not None else '')),
            )
        sr = ShiftReading(
            document_type=active.get("document_type", "unknown"),
            document_date=fields.get("report_date") or active.get("business_date"),
            signed_by=fields.get("signed_by", ""),
            raw_text="Updated draft fields",
            fields=reading_models,
        )
        consistency = check_ocr_consistency(sr)

        uncertain_fields: list[str] = []
        if not fields.get("report_date"):
            uncertain_fields.append("report_date")
        if not fields.get("shift_code"):
            uncertain_fields.append("shift_code")
        for mf in MONEY_FIELDS:
            if fields.get(mf) is None and readings.get(mf, {}).get("status") in {"uncertain", "unreadable"}:
                uncertain_fields.append(mf)
            elif mf in {"cash_vnd", "total_collected_vnd"} and fields.get(mf) is None:
                uncertain_fields.append(mf)

        updated = store.update_ocr_draft_fields(
            owner,
            self._conversation_id,
            store_id=actor.store_id,
            user_id=actor.user_id,
            field_updates=clean_updates,
            consistency=consistency,
            uncertain_fields=uncertain_fields,
            draft_id=active["draft_id"],
        )
        if updated:
            updated["field_readings"] = readings
        msg = self._format_ocr_draft_message(updated, prefix="✏️ **Đã cập nhật dự thảo chốt ca:**\n\n")
        return {
            "status": "SUCCESS",
            "text": msg,
            "draft_id": updated["draft_id"],
            "draft": updated,
            "source_refs": [f"attachment:{updated['file_id']}", f"ocr_draft:{updated['draft_id']}"],
        }

    def update_ocr_draft(
        self,
        updates: dict[str, Any],
        user_role: str = "MANAGER",
        user_name: str = "Quản lý",
        *,
        user_id=None,
        draft_id: str | None = None,
    ) -> dict[str, Any]:
        """Public method for UI or chat to update fields in the pending OCR draft."""
        actor = self._actor(user_role, user_name, user_id)
        owner = self._conversation_owner(actor)
        res = self.tool_update_shift_ocr_draft(draft_id=draft_id, **updates)
        if res.get("status") == "SUCCESS":
            self._ensure_store().append(
                owner, self._conversation_id, "assistant", res["text"], res.get("source_refs", []),
            )
        return res

    def confirm_ocr_draft(
        self,
        approve: bool,
        user_role: str = "MANAGER",
        user_name: str = "Quản lý",
        *,
        user_id=None,
        draft_id: str | None = None,
        record_message: bool = True,
    ) -> dict[str, Any]:
        """Verify permissions and re-validate the entire OCR draft before writing to shift_reports.json.

        ``record_message=False`` is used by the LangGraph approval node, whose caller
        (``resume_approval``) already appends the reply to the transcript.
        """
        from src.auth import is_admin_role
        from src.engine.shift_service import (
            record_ocr_user_edits,
            upsert_shift_report,
            validate_shift_report_payload,
        )
        from src.engine.vision_ocr import MONEY_FIELDS

        actor = self._actor(user_role, user_name, user_id)
        owner = self._conversation_owner(actor)
        store = self._ensure_store()
        active = store.get_active_ocr_draft(
            owner, self._conversation_id, store_id=actor.store_id, user_id=actor.user_id,
        )
        if not active or (draft_id and active.get("draft_id") != draft_id):
            return {
                "status": "NO_ACTIVE_DRAFT",
                "text": "Không có dự thảo chốt ca OCR nào đang chờ xác nhận trong cuộc trò chuyện này.",
                "message": "Không có dự thảo chốt ca OCR nào đang chờ xác nhận trong cuộc trò chuyện này.",
            }

        if not approve:
            cancelled = store.resolve_ocr_draft(
                owner,
                self._conversation_id,
                store_id=actor.store_id,
                user_id=actor.user_id,
                new_status="CANCELLED",
                draft_id=active["draft_id"],
            )
            msg = f"🛑 **Đã hủy xác nhận dự thảo `{active['draft_id']}`.** Hệ thống không ghi dữ liệu vào sổ doanh thu."
            if record_message:
                store.append(owner, self._conversation_id, "assistant", msg, [])
            return {
                "status": "CANCELLED",
                "is_approved": False,
                "draft_id": active["draft_id"],
                "draft": cancelled,
                "text": msg,
                "message": msg,
            }

        # Enforce server-side RBAC before saving revenue
        if not is_admin_role(actor.role):
            msg = "🔒 **TỪ CHỐI QUYỀN:** Tài khoản Nhân viên không được phép xác nhận lưu báo cáo doanh thu chốt ca. Chỉ Quản lý hoặc Chủ cửa hàng mới có quyền xác nhận."
            return {
                "status": "FORBIDDEN",
                "is_approved": False,
                "draft_id": active["draft_id"],
                "text": msg,
                "message": msg,
                "tool_called": "rbac_restriction",
                "raw_result": {"status": "FORBIDDEN", "role": actor.role},
            }

        fields = dict(active.get("fields", {}))
        report_date = fields.get("report_date")
        shift_code = fields.get("shift_code")
        from src.engine.shift_service import REQUIRED_SHIFT_MONEY_FIELDS
        missing_core = [
            k for k in ('report_date', 'shift_code', *REQUIRED_SHIFT_MONEY_FIELDS)
            if fields.get(k) is None or fields.get(k) == ""
        ]
        if missing_core:
            msg = (
                f"⚠️ **Chưa thể lưu chốt ca:** Dự thảo `{active['draft_id']}` còn thiếu các trường bắt buộc chưa được xác nhận: "
                f"**{', '.join(missing_core)}**. Bạn vui lòng bổ sung trước khi xác nhận lưu."
            )
            return {
                "status": "VALIDATION_FAILED",
                "is_approved": False,
                "draft_id": active["draft_id"],
                "missing_fields": missing_core,
                "text": msg,
                "message": msg,
            }

        meta = active.get("meta") or {}
        payload = {
            "report_date": str(report_date),
            "shift_code": str(shift_code),
            "signed_by": str(fields.get("signed_by") or user_name),
            "notes": str(fields.get("notes") or ""),
            "status": "APPROVED",
        }
        if fields.get("bank_transfer_formula"):
            payload["bank_transfer_formula"] = str(fields["bank_transfer_formula"])
        attachment = store.get_attachment(owner, self._conversation_id, active["file_id"],
                                          store_id=actor.store_id, user_id=actor.user_id) if active.get("file_id") else None
        if attachment and attachment.get("storage_path"):
            payload["image_path"] = attachment["storage_path"]
        for mf in MONEY_FIELDS:
            payload[mf] = int(fields.get(mf) or 0)

        payload['business_date'] = str(report_date)
        valid, validation_error = validate_shift_report_payload(payload, actor_role=actor.role, require_admin_for_approval=True)
        if not valid:
            err_str = validation_error
            msg = f"❌ **Kiểm định dữ liệu thất bại:** {err_str}"
            return {
                "status": "VALIDATION_FAILED",
                "is_approved": False,
                "draft_id": active["draft_id"],
                "errors": [validation_error],
                "text": msg,
                "message": msg,
            }

        initial_ocr = active.get("initial_ocr_fields") or {}
        ocr_context = {
            **initial_ocr,
            "field_readings": active.get("field_readings", {}),
            "document_type": active.get("document_type", "unknown"),
            "consistency": active.get("consistency", {}),
            "model": active.get("model", "chat_ocr"),
        }
        edit_log = record_ocr_user_edits(
            report_id=active['draft_id'],
            business_date=str(report_date),
            shift_code=str(shift_code),
            extracted=ocr_context,
            confirmed_values={key: payload[key] for key in MONEY_FIELDS},
            confirmed_by=actor.user_id,
            store_id=actor.store_id,
            review_seconds=meta.get("review_seconds"),
        )
        payload["ocr_review"] = {
            "mode": meta.get("origin") or "chat_vision",
            "draft_id": active["draft_id"],
            "file_id": active["file_id"],
            "document_type": active.get("document_type", "unknown"),
            "corrected_fields": edit_log["corrected_fields"],
            "manual_fields": edit_log["manual_fields"],
            "field_edits": edit_log["field_edits"],
        }
        ok, error, saved_report = upsert_shift_report(payload, actor_role=actor.role, actor_username=actor.user_id)
        if not ok:
            return {'status': 'VALIDATION_FAILED', 'is_approved': False, 'text': error, 'message': error}
        confirmed_draft = store.resolve_ocr_draft(
            owner,
            self._conversation_id,
            store_id=actor.store_id,
            user_id=actor.user_id,
            new_status="CONFIRMED",
            draft_id=active["draft_id"],
        )
        msg = (
            f"✅ **ĐÃ XÁC NHẬN & LƯU BÁO CÁO CHỐT CA (`{active['draft_id']}`):**\n\n"
            f"- **Ngày:** `{payload['report_date']}` · **Ca:** `{payload['shift_code']}` · **Người ký:** `{payload['signed_by']}`\n"
            f"- **Tiền mặt:** **{payload['cash_vnd']:,} đ** | **Chuyển khoản:** **{payload['bank_transfer_vnd']:,} đ**\n"
            f"- **ShopeeFood:** **{payload['shopee_food_vnd']:,} đ** | **GrabFood:** **{payload['grab_food_vnd']:,} đ**\n"
            f"- **Tổng thực thu bàn giao:** **{payload['total_collected_vnd']:,} đ**"
        )
        if record_message:
            store.append(
                owner, self._conversation_id, "assistant", msg,
                [f"shift_reports:{payload['report_date']}:{payload['shift_code']}", f"ocr_draft:{active['draft_id']}"],
            )
        return {
            "status": "SUCCESS",
            "is_approved": True,
            "draft_id": active["draft_id"],
            "draft": confirmed_draft,
            "report": saved_report,
            "text": msg,
            "message": msg,
            "evidence_refs": [f"shift_reports:{payload['report_date']}:{payload['shift_code']}", f"ocr_draft:{active['draft_id']}"],
        }

    @staticmethod
    def _parse_conversational_ocr_edits(query: str) -> dict[str, Any]:
        """Parse conversational field edits when a user updates an active OCR shift draft via chat."""
        q_norm = _normalize_vn(query)
        updates: dict[str, Any] = {}

        field_patterns = [
            ("pos_revenue_vnd", r"(?:tong doanh thu pos|doanh thu pos)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("pos_collected_vnd", r"(?:thuc thu pos|so tien thu duoc pos)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("cash_vnd", r"(?:tien mat|cash)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("bank_transfer_vnd", r"(?:chuyen khoan|ck)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("shopee_food_vnd", r"(?:shopeefood|shopee food|shopee)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("grab_food_vnd", r"(?:grabfood|grab food|grab)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("be_food_vnd", r"(?:befood|be food)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("cash_diff_vnd", r"(?:lech tien mat|tien du|du)\s*(?:la|thanh|=|:)?\s*([-+]?\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("petty_cash_kept_vnd", r"(?:co dinh ket|tien le giu ket|giu ket)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("expenses_vnd", r"(?:khoan chi|chi trong ca|chi)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
            ("total_collected_vnd", r"(?:tong thu ve|tong thuc thu|thuc thu ban giao)\s*(?:la|thanh|=|:)?\s*(\d[\d.,]*)\s*(?:(k|nghin|ngan)\b)?"),
        ]
        for field_key, pat in field_patterns:
            m = re.search(pat, q_norm)
            if m:
                raw_num = re.sub(r"[^\d-]", "", m.group(1))
                if raw_num and raw_num not in {"-", ""}:
                    val = int(raw_num)
                    if m.group(2):
                        val *= 1000
                    updates[field_key] = val

        if any(w in q_norm for w in ["sua", "cap nhat", "chot ca", "ca sang", "ca chieu", "ca toi", "ngay", "nguoi ky"]):
            if "ca sang" in q_norm:
                updates["shift_code"] = "CA_SANG"
            elif "ca chieu" in q_norm:
                updates["shift_code"] = "CA_CHIEU"
            elif "ca toi" in q_norm:
                updates["shift_code"] = "CA_TOI"
            parsed_d, _ = _parse_query_date_range(query)
            if parsed_d and (updates or any(w in q_norm for w in ["sua", "cap nhat", "chot ca", "ca sang", "ca chieu", "ca toi"])):
                updates["report_date"] = parsed_d
            signer_m = re.search(r"(?:nguoi ky|nhan vien ky|ky ten)\s*(?:la|thanh|:)?\s*([A-Za-zÀ-ỹ]+)", query, re.IGNORECASE)
            if signer_m:
                updates["signed_by"] = signer_m.group(1).strip()

        return updates

    def submit_shift_review_for_approval(
        self,
        *,
        extracted: dict[str, Any],
        reviewed_values: dict[str, Any],
        report_date: str,
        shift_code: str,
        signed_by: str = "",
        notes: str = "",
        bank_transfer_formula: str = "",
        image_paths: list[str] | None = None,
        review_seconds: float | None = None,
        user_role: str = "MANAGER",
        user_name: str = "Quản lý",
        user_id=None,
        review_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """OCR page -> the same governed write path as the chat.

        The values a person reviewed on the OCR page become a DRAFT_OCR_ in the user's
        conversation; then request_shift_draft_confirmation pauses the graph at interrupt()
        until a manager approves. Nothing is written to shift_reports before that.
        """
        from pathlib import Path
        from src.engine.vision_ocr import MONEY_FIELDS

        actor = self._actor(user_role, user_name, user_id)
        owner = self._conversation_owner(actor)
        store = self._ensure_store()
        file_ids, filenames = [], []
        for path in image_paths or []:
            p = Path(path)
            if p.is_file():
                att = self.attach_shift_image(p.read_bytes(), filename=p.name, user_role=user_role,
                                              user_name=user_name, user_id=user_id)
                file_ids.append(att["file_id"])
                filenames.append(att["filename"])
        fields = {mf: reviewed_values.get(mf) for mf in MONEY_FIELDS}
        fields.update(report_date=report_date, shift_code=shift_code)
        # The manager approves the numbers the staff checked, so the arithmetic check is re-run on them
        # (the OCR-time check may describe a misread that the staff already corrected).
        from src.engine.vision_ocr import MoneyReading, ShiftReading, check_ocr_consistency
        readings = extracted.get("field_readings", {}) or {}
        consistency = check_ocr_consistency(ShiftReading(
            document_type=extracted.get("document_type", "unknown"),
            document_date=report_date, signed_by=signed_by or "", raw_text="Reviewed values",
            fields={mf: MoneyReading(
                value=int(fields[mf]) if fields.get(mf) is not None else None,
                normalized_value=int(fields[mf]) if fields.get(mf) is not None else None,
                status="read" if fields.get(mf) is not None else "not_present",
                source=(readings.get(mf) or {}).get("source", "unknown"),
                raw_text=str((readings.get(mf) or {}).get("raw_text", ""))[:300],
                unit_explicit=True,
                evidence=f"Nhân viên xác nhận: {fields[mf]}" if fields.get(mf) is not None else "",
            ) for mf in MONEY_FIELDS},
        ))
        draft = store.save_ocr_draft(
            owner, self._conversation_id, store_id=actor.store_id, user_id=actor.user_id,
            file_id=file_ids[0] if file_ids else "",
            draft_data={
                "document_type": extracted.get("document_type", "unknown"),
                "fields": fields,
                "report_date": report_date,
                "shift_code": shift_code,
                "signed_by": signed_by,
                "notes": notes,
                "bank_transfer_formula": bank_transfer_formula,
                "field_readings": extracted.get("field_readings", {}),
                "consistency": consistency,
                "warnings": list(extracted.get("warnings", [])),
                "file_ids": file_ids,
                "filenames": filenames,
                "meta": {"origin": "ocr_page", "review_seconds": review_seconds, **(review_meta or {})},
            },
        )
        if not (review_meta or {}).get("from_staff_draft"):
            # Every report sent from the OCR page waits in the store's approval queue, so several shifts
            # (or days) can wait side by side. A newer report for the same day and shift replaces the older
            # one still waiting. A manager approves from the queue; that is when interrupt() is reached.
            store.mark_ocr_draft(draft["draft_id"], "SUBMITTED", {
                "submitted_by": actor.user_id, "submitted_by_name": user_name,
                "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            replaced = store.supersede_submitted(actor.store_id, report_date, shift_code, draft["draft_id"])
            shift_name = {"CA_SANG": "Ca sáng", "CA_CHIEU": "Ca chiều", "CA_TOI": "Ca tối"}.get(shift_code, shift_code)
            text = (f"📨 Đã gửi báo cáo {shift_name} ngày {report_date} vào danh sách chờ duyệt. "
                    "Chưa có số nào được ghi sổ; Quản lý kiểm tra và duyệt."
                    + (" Bản gửi trước của cùng ca này đã được thay bằng bản mới." if replaced else ""))
            store.append(owner, self._conversation_id, "user",
                         f"[Trang Chốt ca & OCR] Gửi Quản lý duyệt báo cáo {shift_code} ngày {report_date} ({draft['draft_id']})",
                         [f"ocr_draft:{draft['draft_id']}"])
            store.append(owner, self._conversation_id, "assistant", text, [f"ocr_draft:{draft['draft_id']}"])
            return {"text": text, "raw_result": {"status": "SUBMITTED_TO_MANAGER", "replaced": replaced},
                    "pending_approval": None, "draft": {**draft, "status": "SUBMITTED"}}
        store.append(owner, self._conversation_id, "user",
                     f"[Trang Chốt ca & OCR] Gửi phê duyệt báo cáo {shift_code} ngày {report_date} ({draft['draft_id']})",
                     [f"ocr_draft:{draft['draft_id']}"])
        result = self._runtime().invoke(
            "Yêu cầu phê duyệt lưu báo cáo chốt ca", actor, self._conversation_id,
            forced_call={"name": "request_shift_draft_confirmation", "args": {"draft_id": draft["draft_id"]}},
        )
        if (result.get("raw_result") or {}).get("status") == "UNAUTHORIZED":
            result["text"] = ("🔒 Vai trò hiện tại không được gửi phê duyệt lưu doanh thu chốt ca. "
                              "Dự thảo đã được giữ lại để Quản lý/Chủ quán xử lý.")
        store.append(owner, self._conversation_id, "assistant", result["text"], result.get("evidence_refs"))
        result["draft"] = draft
        return result

    def list_staff_submissions(self, user_role, user_name, *, user_id=None) -> list[dict[str, Any]]:
        """Reports staff sent for approval (managers of the same store only)."""
        from src.auth import is_admin_role
        actor = self._actor(user_role, user_name, user_id)
        if not is_admin_role(actor.role):
            return []
        return self._ensure_store().list_submitted_ocr_drafts(actor.store_id)

    def open_staff_submission(self, draft_id, user_role, user_name, *, user_id=None) -> dict[str, Any]:
        """A manager takes a staff submission into the governed path: draft -> request -> interrupt()."""
        from src.auth import is_admin_role
        actor = self._actor(user_role, user_name, user_id)
        if not is_admin_role(actor.role):
            return {"text": "🔒 Chỉ Quản lý/Chủ quán được mở báo cáo nhân viên gửi.", "raw_result": {"status": "UNAUTHORIZED"}}
        store = self._ensure_store()
        sub = store.get_ocr_draft_by_id(draft_id)
        if not sub or sub.get("status") != "SUBMITTED" or sub.get("store_id") != actor.store_id:
            return {"text": "Báo cáo này không còn chờ duyệt.", "raw_result": {"status": "NOT_FOUND"}}
        meta = sub.get("meta") or {}
        fields = sub["fields"]
        submitter = meta.get("submitted_by_name") or sub.get("user_id")
        notes = (sub.get("notes") or "").strip()
        result = self.submit_shift_review_for_approval(
            extracted={"field_readings": sub.get("field_readings", {}), "consistency": sub.get("consistency") or {},
                       "warnings": sub.get("warnings", []), "document_type": sub.get("document_type", "unknown")},
            reviewed_values={k: fields.get(k) for k in fields if k.endswith("_vnd")},
            report_date=sub.get("business_date"), shift_code=sub.get("shift_code"),
            signed_by=sub.get("signed_by", ""), notes=(notes + f" [Nhân viên {submitter} gửi]").strip(),
            bank_transfer_formula=sub.get("bank_transfer_formula", ""),
            image_paths=store.attachment_paths(sub.get("file_ids") or []),
            review_seconds=meta.get("review_seconds"), user_role=user_role, user_name=user_name, user_id=user_id,
            review_meta={"from_staff_draft": draft_id, "submitted_by": meta.get("submitted_by"),
                         "submitted_by_name": submitter,
                         "suggested_fields": meta.get("suggested_fields", []),
                         "suggestions_edited": meta.get("suggestions_edited", [])},
        )
        store.mark_ocr_draft(draft_id, "FORWARDED", {"forwarded_to": (result.get("draft") or {}).get("draft_id"),
                                                     "forwarded_by": actor.user_id})
        return result

    def list_my_submissions(self, user_role, user_name, *, user_id=None, limit: int = 12) -> list[dict[str, Any]]:
        """What this person sent and where each report stands (waiting, approved, rejected, replaced)."""
        actor = self._actor(user_role, user_name, user_id)
        return self._ensure_store().list_ocr_submissions_by_user(actor.store_id, actor.user_id, limit)

    def decide_submissions(self, draft_ids, approve: bool, user_role, user_name, *, user_id=None,
                           reason: str = "") -> list[dict[str, Any]]:
        """Approve or reject several queued shift reports at once.

        Each approval still takes the governed path, one report at a time: queued draft → manager's draft →
        request_shift_draft_confirmation → interrupt() → the manager's decision (this call) → write.
        A rejection writes nothing; the report is marked REJECTED so the sender sees it.
        """
        from src.auth import is_admin_role
        actor = self._actor(user_role, user_name, user_id)
        if not is_admin_role(actor.role):
            return [{"draft_id": d, "ok": False, "text": "🔒 Chỉ Quản lý/Chủ quán được duyệt."} for d in draft_ids]
        store = self._ensure_store()
        results = []
        for draft_id in draft_ids:
            sub = store.get_ocr_draft_by_id(draft_id)
            if not sub or sub.get("status") != "SUBMITTED" or sub.get("store_id") != actor.store_id:
                results.append({"draft_id": draft_id, "ok": False, "text": "Báo cáo này không còn chờ duyệt."})
                continue
            label = f"{sub.get('shift_code')} {sub.get('business_date')}"
            if not approve:
                store.mark_ocr_draft(draft_id, "REJECTED", {"rejected_by": actor.user_id, "rejection_reason": reason,
                                                            "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                results.append({"draft_id": draft_id, "ok": True, "text": f"Đã từ chối {label}."})
                continue
            existing = self.conversation_history(user_role, user_name, user_id=user_id).get("pending_approval")
            if existing:
                results.append({"draft_id": draft_id, "ok": False,
                                "text": "Đang có một yêu cầu khác chờ bạn trả lời trong Trợ lý Tuyết Vương; xử lý nó trước."})
                break
            opened = self.open_staff_submission(draft_id, user_role, user_name, user_id=user_id)
            if not opened.get("pending_approval"):
                results.append({"draft_id": draft_id, "ok": False, "text": opened.get("text", "Không mở được báo cáo.")})
                continue
            decided = self.resume_approval(True, user_role, user_name, user_id=user_id)
            ok = "ĐÃ XÁC NHẬN" in (decided.get("text") or "")
            store.mark_ocr_draft(draft_id, "APPROVED" if ok else "FORWARDED",
                                 {"approved_by": actor.user_id,
                                  "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            results.append({"draft_id": draft_id, "ok": ok, "text": f"Đã duyệt và ghi sổ {label}." if ok else decided.get("text", "")})
        return results

    _OCR_CONFIRM_PHRASES = (
        "xac nhan luu", "luu chot ca", "xac nhan chot ca", "dong y luu", "duyet chot ca",
        "phe duyet luu", "yeu cau phe duyet", "luu bao cao chot ca", "gui phe duyet",
    )
    _OCR_UPDATE_FIELDS = frozenset({
        "report_date", "shift_code", "signed_by", "cash_vnd", "cash_diff_vnd", "petty_cash_kept_vnd",
        "bank_transfer_vnd", "shopee_food_vnd", "be_food_vnd", "grab_food_vnd", "expenses_vnd",
        "total_collected_vnd", "pos_revenue_vnd", "pos_collected_vnd",
    })

    def _route_ocr_intent(self, user_query: str, q_norm: str, active_ocr: dict[str, Any] | None) -> dict[str, Any] | None:
        """Map OCR/governance requests to a trusted server-side tool call.

        The same routing applies with an LLM and in offline_rules mode, so the three-step
        chat OCR flow (inspect -> update -> request confirmation) is deterministic. Calls
        still pass through the graph's authorize node (RBAC + schema) and approval interrupt.
        """
        upper = user_query.upper()
        file_ids = list(dict.fromkeys(re.findall(r"\bFILE_[A-F0-9]{16}\b", upper)))
        mentions_plan = bool(re.search(r"\bPLAN_(?:PO|PREP)_[A-Z0-9]{8}\b", upper))
        draft_ref = re.search(r"\b(?:DRAFT_OCR_[A-F0-9]{12}|OCR_DRAFT_[A-F0-9]{10})\b", upper)
        ocr_topic = any(w in q_norm for w in ("chot ca", "ocr", "du thao", "so tay", "hoa don pos")) or bool(draft_ref)

        # Governance / HITL overview (RBAC is read from the authenticated actor, not the text).
        if "hitl" in q_norm or (any(w in q_norm for w in ("quyen han", "phan quyen"))
                                and any(w in q_norm for w in ("phe duyet", "lich su", "interrupt"))):
            return {"forced_call": {"name": "get_governance_overview", "args": {}}}

        # Step 1 by text: explicit server-issued file ids.
        if file_ids:
            args: dict[str, Any] = {"file_ids": file_ids[:6]}
            for code, words in (("CA_SANG", "ca sang"), ("CA_CHIEU", "ca chieu"), ("CA_TOI", "ca toi")):
                if words in q_norm:
                    args["shift_code"] = code
            report_date, _ = _parse_query_date_range(user_query)
            if report_date:
                args["report_date"] = report_date
            return {"forced_call": {"name": "inspect_attached_shift_image", "args": args}}

        # Step 3: request approval -> request_shift_draft_confirmation -> interrupt().
        wants_confirm = any(p in q_norm for p in self._OCR_CONFIRM_PHRASES) or (
            draft_ref and re.search(r"\b(?:duyet|xac nhan|luu)\b", q_norm))
        if wants_confirm and not mentions_plan and (active_ocr or ocr_topic):
            if not active_ocr:
                return {"direct_text": ("Hiện chưa có dự thảo chốt ca OCR nào đang chờ để gửi phê duyệt. "
                                        "Hãy đính kèm ảnh sổ chốt ca/hóa đơn POS ở mục **📸** bên dưới khung chat trước."),
                        "tool_called": "request_shift_draft_confirmation"}
            return {"forced_call": {"name": "request_shift_draft_confirmation",
                                    "args": {"draft_id": active_ocr["draft_id"]}}}

        # Same photos, another shift: "đọc lại ảnh cho ca chiều" (the page reading is cached, no new model call).
        shift_words = [code for code, words in (("CA_SANG", "ca sang"), ("CA_CHIEU", "ca chieu"), ("CA_TOI", "ca toi"))
                       if words in q_norm]
        if active_ocr and shift_words and re.search(r"\bdoc( lai)?\b", q_norm) and active_ocr.get("file_ids"):
            args = {"file_ids": active_ocr["file_ids"][:6], "shift_code": shift_words[0]}
            if (active_ocr.get("fields") or {}).get("report_date"):
                args["report_date"] = active_ocr["fields"]["report_date"]
            return {"forced_call": {"name": "inspect_attached_shift_image", "args": args}}

        # Step 2a: accept the highlighted suggestions for every still-empty field in one message.
        if active_ocr and "goi y" in q_norm and any(w in q_norm for w in ("dung", "dong y", "lay", "ap dung", "chap nhan")):
            fields = active_ocr.get("fields") or {}
            hints = (active_ocr.get("meta") or {}).get("suggestions") or {}
            edits = {k: v["value"] for k, v in hints.items()
                     if k in self._OCR_UPDATE_FIELDS and fields.get(k) is None and v.get("value") is not None}
            if not edits:
                return {"direct_text": "Dự thảo hiện không còn ô trống nào có số gợi ý.",
                        "tool_called": "update_shift_ocr_draft"}
            return {"forced_call": {"name": "update_shift_ocr_draft",
                                    "args": {"draft_id": active_ocr["draft_id"], **edits}}}

        # Step 2: natural-language edits of uncertain fields.
        if active_ocr:
            edits = {k: v for k, v in self._parse_conversational_ocr_edits(user_query).items()
                     if k in self._OCR_UPDATE_FIELDS}
            if edits:
                return {"forced_call": {"name": "update_shift_ocr_draft",
                                        "args": {"draft_id": active_ocr["draft_id"], **edits}}}

        reads_image = re.search(r"\bdoc\b", q_norm) and "anh" in q_norm and any(
            w in q_norm for w in ("chot ca", "so ", "hoa don", "pos", "viet tay"))
        views_draft = "du thao" in q_norm and any(w in q_norm for w in ("ocr", "chot ca", "dang cho")) and any(
            w in q_norm for w in ("xem", "cap nhat", "kiem tra", "dang cho", "trang thai"))
        if views_draft or (reads_image and active_ocr):
            return {"forced_call": {"name": "get_shift_ocr_draft", "args": {}}}
        if reads_image:
            return {"direct_text": (
                "📸 **Quy trình đọc & đối soát ảnh chốt ca (Verifiable OCR):**\n\n"
                "1. Mở mục **📸 Đính kèm ảnh chứng từ** ngay dưới khung chat, chọn ảnh sổ chốt ca viết tay và/hoặc hóa đơn POS "
                "(hoặc bấm một ảnh mẫu của ngày 14/10/2026), rồi bấm **Gửi cho Tuyết Vương đọc**.\n"
                "2. Mình gọi `inspect_attached_shift_image`: tách vùng 🧾 POS và ✍️ sổ tay, kiểm tra độ mờ, giữ chuỗi đọc thô, "
                "đọc mọi ca có trên trang, gợi ý số cho ô viết tắt (653 → 653.000, `962 + 629` → 1.591.000) nhưng vẫn đánh dấu ⚠️, và đối soát cộng ngang.\n"
                "3. Nhắn `dùng số gợi ý` để điền các ô ⚠️, hoặc sửa bằng lời, ví dụ: `Sửa tiền mặt thành 653000`.\n"
                "4. Gõ `Yêu cầu phê duyệt lưu báo cáo chốt ca` — luồng LangGraph dừng ở `interrupt()` chờ Quản lý bấm **Phê duyệt**."),
                "tool_called": "ocr_guidance"}
        return None
