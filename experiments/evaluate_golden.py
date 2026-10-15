import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from datetime import date
from src.agent.mixue_agent import MixueOperationsAgent
from src.engine.validator import IndependentPlanValidator


def run_golden_evaluation():
    golden_path = os.path.join(os.path.dirname(__file__), "golden_cases.jsonl")
    if not os.path.exists(golden_path):
        print(f"Error: {golden_path} not found.")
        return

    with open(golden_path, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    agent = MixueOperationsAgent()
    val = IndependentPlanValidator()

    passed = 0
    failed = 0
    results = []

    print(f"=== CHẠY ĐÁNH GIÁ {len(cases)} KỊCH BẢN GOLDEN DATASET ===")

    for idx, case in enumerate(cases, 1):
        cid = case["id"]
        category = case["category"]
        query = case["query"]
        must_include = case.get("must_include", [])
        status = "FAIL"
        details = ""

        try:
            # 1. Validation category
            if category == "validation":
                if "âm" in query:
                    v_res = val.verify_topping_prep_plan([{"ingredient_id": "TP02", "recommended_prep_qty": -5000.0, "batch_size": 5000.0, "unit": "ml"}])
                elif "đơn vị" in query:
                    v_res = val.verify_topping_prep_plan([{"ingredient_id": "TP02", "recommended_prep_qty": 5000.0, "batch_size": 5000.0, "unit": "kg"}])
                elif "tròn mẻ" in query:
                    v_res = val.verify_topping_prep_plan([{"ingredient_id": "NL06", "recommended_prep_qty": 1500.0, "batch_size": 1000.0, "unit": "g"}])
                else:
                    v_res = val.verify_replenishment_plan([{"ingredient_id": "GHOST_ING_99", "recommended_order_qty": 1000.0, "pack_size": 1000.0, "unit": "g"}])

                if not v_res["is_valid"] and v_res["status"] == "REJECTED":
                    viol_text = " ".join(v_res["violations"])
                    if any(mi.lower() in viol_text.lower() for mi in must_include):
                        status = "PASS"
                        details = f"Đã bắt và từ chối vi phạm: {v_res['violations'][0]}"
                    else:
                        details = f"Vi phạm không chứa từ khóa: {viol_text}"
                else:
                    details = f"Validator chấp nhận kế hoạch sai!"

            # 2. RBAC governance category
            elif category == "rbac_governance":
                role = case.get("expected_role", "STAFF")
                res = agent.tool_approve_plan("PLAN_DRAFT_MOCK", user_role=role, user_name="Test User")
                if role == "STAFF":
                    if res["status"] == "UNAUTHORIZED" and not res["is_approved"]:
                        status = "PASS"
                        details = f"Đã chặn Staff thành công: {res['message']}"
                    else:
                        details = f"Lỗi: Staff không bị chặn!"
                else:
                    # Manager / Owner should pass permission check
                    if res["status"] in ["NOT_FOUND", "SUCCESS"]:  # NOT_FOUND means permission passed, plan id was mock
                        status = "PASS"
                        details = f"Quyền {role} được chấp thuận."
                    else:
                        details = f"Lỗi quyền {role}: {res.get('message')}"

            # 3. All Agent process_query interactions
            else:
                resp = agent.process_query(query)
                full_text = resp["text"] + " " + json.dumps(resp.get("raw_result", {}), ensure_ascii=False, default=str) + " " + json.dumps(resp.get("evidence_refs", []), default=str)
                
                # Check expected tool if specified
                exp_tool = case.get("expected_tool")
                tool_match = (exp_tool is None) or (resp.get("tool_called") == exp_tool)

                # Check must include keywords
                all_found = all(mi.lower() in full_text.lower() for mi in must_include)

                if all_found:
                    status = "PASS"
                    details = f"Tool: {resp.get('tool_called')} | Khớp tất cả từ khóa: {must_include}"
                else:
                    missing = [mi for mi in must_include if mi.lower() not in full_text.lower()]
                    details = f"Thiếu từ khóa: {missing}"

        except Exception as e:
            status = "ERROR"
            details = str(e)

        if status == "PASS":
            passed += 1
            print(f"[{idx:02d}/30] ✅ {cid} ({category}): PASS - {details[:70]}")
        else:
            failed += 1
            print(f"[{idx:02d}/30] ❌ {cid} ({category}): {status} - {details[:70]}")

        results.append({
            "id": cid,
            "category": category,
            "query": query,
            "status": status,
            "details": details
        })

    pass_rate = round(passed / len(cases) * 100, 1)
    print("\n" + "="*50)
    print(f"TỔNG KẾT ĐÁNH GIÁ: {passed}/{len(cases)} ĐẠT ({pass_rate}%) | THẤT BẠI: {failed}")
    print("="*50)

    agent.close()
    val.close()
    return results


if __name__ == "__main__":
    run_golden_evaluation()
