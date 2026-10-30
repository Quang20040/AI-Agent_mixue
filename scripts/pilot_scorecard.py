# -*- coding: utf-8 -*-
"""Mixue Pilot Scorecard Generator.

Produces comprehensive pilot metrics including manual baseline time comparison,
OCR field error statistics, API/tool error rates, and plan vs actual sales/waste comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine.pilot_monitoring import PilotMonitoringService


def summarize(reports, ratings):
    reviews = [report['ocr_review'] for report in reports if report.get('ocr_review')]
    times = [review['review_seconds'] for review in reviews if review.get('review_seconds') is not None]
    return {
        'reviewed_shift_reports': len(reviews),
        'vision_reviewed_reports': sum(review.get('mode') == 'vision' for review in reviews),
        'ocr_fields_corrected': sum(len(review.get('corrected_fields', [])) for review in reviews),
        'fields_manually_completed': sum(len(review.get('manual_fields', [])) for review in reviews),
        'average_review_seconds': round(sum(times) / len(times), 1) if times else None,
        'rated_chat_answers': len(ratings),
        'helpful_votes': sum(ratings),
        'helpful_rate_among_rated': round(sum(ratings) / len(ratings), 3) if ratings else None,
        'limitations': [
            'Chỉ tính báo cáo có metadata xác nhận mới; báo cáo cũ không được coi là OCR thành công.',
            'Phản hồi người dùng và số ô sửa không phải độ chính xác đã kiểm định.',
            'Chưa có baseline thời gian thao tác tay hoặc bằng chứng giảm hao hụt thực tế.'
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Mixue Pilot Scorecard Generator")
    parser.add_argument("--reports", default="data/shift_reports.json")
    parser.add_argument("--history", default="data/agent_private/conversations.sqlite")
    parser.add_argument("--audit", default="data/agent_private/audit.jsonl")
    parser.add_argument("--output", default="data/agent_private/pilot-scorecard.json")
    args = parser.parse_args()

    service = PilotMonitoringService(
        conversations_db=args.history,
        shift_reports_path=args.reports,
        audit_log_path=args.audit,
    )
    report = service.generate_comprehensive_pilot_report(output_path=args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n✅ Pilot scorecard generated successfully: {args.output}")


if __name__ == "__main__":
    main()
