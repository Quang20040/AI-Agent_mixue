"""One-command evaluation for the thesis (chương thực nghiệm).

    python -m scripts.run_live_evaluation                 # live where the API is enabled, offline otherwise
    python -m scripts.run_live_evaluation --offline-only  # never calls a provider

Sections
  1. OCR · 4 synthetic labelled images (scripted reading; + live model if enabled)
  2. OCR · labelled real store photos (live: records readings; replay: re-verifies saved readings)
  3. Agent · behavioural scorecard (offline_rules; + live LLM if enabled)
  4. End-to-end · chat OCR -> edit -> request approval -> interrupt(), then CANCEL

Nothing here writes revenue: step 4 always cancels at the approval interrupt and uses a
temporary conversation store. Results go to reports/evaluation_<timestamp>.md (+ .json).
API keys are never printed.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent.config import AgentSettings  # noqa: E402
from src.engine.ocr_evaluation import (  # noqa: E402
    REAL_DATASET_PATH,
    TAXONOMY_7,
    TAXONOMY_LABELS_VI,
    run_dataset_benchmark,
    run_ocr_benchmark,
)
from src.engine.vision_ocr import ocr_model_id  # noqa: E402


def _taxonomy_table(reports: dict[str, dict]) -> list[str]:
    names = list(reports)
    lines = ['| Nhóm | ' + ' | '.join(names) + ' |', '|---|' + '---:|' * len(names)]
    for key in TAXONOMY_7:
        lines.append(f'| `{key}` — {TAXONOMY_LABELS_VI[key]} | '
                     + ' | '.join(str(r['taxonomy_7'].get(key, 0)) for r in reports.values()) + ' |')
    lines.append('| Khác | ' + ' | '.join(', '.join(f'{k}: {v}' for k, v in r.get('other_counts', {}).items()) or '—'
                                        for r in reports.values()) + ' |')
    lines.append('| **Số sai lọt vào biểu mẫu** | ' + ' | '.join(f"**{r['errors_reaching_form']}**" for r in reports.values()) + ' |')
    lines.append('| Trường được chấm | ' + ' | '.join(str(r['fields_evaluated']) for r in reports.values()) + ' |')
    return lines


def _ocr_section(title: str, report: dict) -> list[str]:
    lines = [f'### {title} (`{report["mode"]}`)', '']
    skipped = [c for c in report['cases'] if c.get('skipped_reason')]
    scored = [c for c in report['cases'] if 'verified' in c]
    lines.append(f'Chấm {len(scored)}/{len(report["cases"])} ảnh.' + (' Bỏ qua: ' + '; '.join(
        f'{c["case_id"]} ({c["skipped_reason"]})' for c in skipped) if skipped else ''))
    rt = report.get('runtime') or {}
    if rt.get('calls'):
        lines.append(f'Mô hình gọi {rt["calls"]} lần · độ trễ TB {rt["avg_latency_s"]} s · token vào/ra {rt["input_tokens"]}/{rt["output_tokens"]}.')
    lines.append('')
    if scored:
        lines += _taxonomy_table({'Bản đọc thô': report['raw_summary'], 'Có kiểm chứng': report['verified_summary']})
        lines.append('')
        for case in scored:
            wrong = {n: r['outcome'] for n, r in case['verified']['field_results'].items()
                     if not r['passed'] and r['outcome'] != 'correct_not_present'}
            lines.append(f'- `{case["case_id"]}`: {case["verified"]["passed_fields"]}/{case["verified"]["total_fields"]} trường đạt'
                         + (f'; lỗi: {wrong}' if wrong else '')
                         + ('' if case['verified']['consistency_check_passed'] else '; ⚠️ kiểm tra số học chưa đạt'))
    lines.append(f'\n> {report.get("note", "")}\n')
    return lines


def _agent_section(report: dict) -> list[str]:
    lines = [f'### Agent scorecard · `{report["dataset_name"]}` · `{report["mode"]}` · mô hình `{report["model_name"]}`', '',
             f'**{report["passed"]}/{report["total"]}** đạt ({report["pass_rate_pct"]}%) · trung vị độ trễ '
             f'{report["median_latency_seconds"]} s · token vào/ra {report["total_input_tokens"]}/{report["total_output_tokens"]}', '',
             '| Nhóm | Đạt |', '|---|---:|']
    lines += [f'| {name} | {v["passed"]}/{v["total"]} |' for name, v in sorted(report['categories'].items())]
    failed = [c for c in report['cases'] if not c['passed']]
    if failed:
        lines.append('')
        lines += [f'- ❌ `{c["id"]}` ({c["category"]}): status `{c["status"]}`, '
                  f'tiêu chí trượt {[k for k, ok in c["checks"].items() if not ok]}' for c in failed]
    return lines + ['']


def _end_to_end(settings: AgentSettings, live: bool, readings_dir: Path | None = None) -> dict:
    """Chat OCR flow on the real CA_SANG photo; always cancels at the interrupt."""
    from src.agent.conversation_store import ConversationStore
    from src.agent.mixue_agent import MixueOperationsAgent
    from src.engine.ocr_evaluation import _ScriptedReader, dataset_image_path, load_ocr_dataset

    case = next(c for c in load_ocr_dataset()['cases'] if c['case_id'] == 'REAL_CA_SANG_20261014')
    model = None
    if not live:
        saved = (readings_dir or REAL_DATASET_PATH.parent / 'readings') / f'{case["case_id"]}.json'
        if not saved.is_file():
            return {'status': 'SKIPPED', 'reason': 'Không có API và chưa có bản đọc đã lưu cho ảnh ca sáng.'}
        model = _ScriptedReader(json.loads(json.loads(saved.read_text(encoding='utf-8'))['raw_content']))
    with tempfile.TemporaryDirectory() as tmp:
        tmp_settings = settings.model_copy(update={'checkpoint_path': str(Path(tmp) / 'ckpt.sqlite'),
                                                   'audit_path': str(Path(tmp) / 'audit.jsonl')})
        if not live:
            tmp_settings = tmp_settings.model_copy(update={'llm_enabled': False})
        agent = MixueOperationsAgent(settings=tmp_settings, conversation_store=ConversationStore(Path(tmp) / 'conv.sqlite'))
        who = dict(user_role='MANAGER', user_name='Người kiểm thử', user_id='quanly')
        steps = []
        try:
            def timed(name, fn):
                started = time.monotonic()
                result = fn()
                steps.append({'step': name, 'seconds': round(time.monotonic() - started, 2),
                              'status': (result.get('raw_result') or {}).get('status') or result.get('status')})
                return result

            image = dataset_image_path(case['image'])
            timed('1 · inspect_attached_shift_image', lambda: agent.process_image_message(
                file_bytes=image.read_bytes(), filename=image.name, user_query='chốt ca sáng ngày 14/10/2026', ocr_model=model, **who))
            truth = {k: v['expected_value'] for k, v in case['fields'].items() if v['expected_value'] is not None}
            edit = ('Sửa tiền mặt thành {cash_vnd}, chuyển khoản {bank_transfer_vnd}, shopee {shopee_food_vnd}, grab {grab_food_vnd}, '
                    'be food {be_food_vnd}, lệch tiền mặt 0, giữ két {petty_cash_kept_vnd}, khoản chi 0, tổng thực thu {total_collected_vnd}, '
                    'ca sáng ngày 14/10/2026').format(**truth)
            timed('2 · update_shift_ocr_draft', lambda: agent.process_query(edit, **who))
            paused = timed('3 · request_shift_draft_confirmation → interrupt()',
                           lambda: agent.process_query('Yêu cầu phê duyệt lưu báo cáo chốt ca', **who))
            cancelled = timed('4 · resume(approve=False)', lambda: agent.resume_approval(False, **who))
        finally:
            agent.close()
    ok = bool(paused.get('pending_approval')) and (cancelled.get('raw_result') or {}).get('status') == 'CANCELLED'
    return {'status': 'PASS' if ok else 'FAIL', 'mode': 'live' if live else 'replay', 'steps': steps}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--offline-only', action='store_true', help='Không gọi nhà cung cấp AI.')
    parser.add_argument('--agent-dataset', default='experiments/agent_golden_holdout.jsonl')
    parser.add_argument('--agent-limit', type=int)
    parser.add_argument('--output-dir', default=str(ROOT / 'reports'))
    args = parser.parse_args()

    from experiments.agent_scorecard import run_scorecard

    settings = AgentSettings.from_env()
    live = bool(settings.llm_enabled and settings.allow_external_transfer and not args.offline_only)
    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    lines = [f'# Báo cáo kiểm định — {datetime.now():%d/%m/%Y %H:%M}', '',
             f'- Chế độ: **{"live + offline" if live else "offline"}**'
             + ('' if live else ' (chưa bật LLM_ENABLED/ALLOW_EXTERNAL_DATA_TRANSFER hoặc dùng --offline-only)'),
             f'- Nhà cung cấp: `{settings.provider or "—"}` · mô hình chat: `{settings.model or "—"}` · mô hình OCR: `{ocr_model_id(settings) or "—"}`',
             '- Đáp án ảnh thật: báo cáo chốt ca đã duyệt ngày 14/10/2026 (`data/ocr_eval/real_photos.json`).', '']
    results: dict = {'generated_at': datetime.now().isoformat(timespec='seconds'), 'live': live}

    print('[1/4] OCR · ảnh tổng hợp…', flush=True)
    lines += ['## 1. OCR · 4 ảnh tổng hợp có đáp án', '']
    results['ocr_synthetic_scripted'] = run_ocr_benchmark('scripted')
    lines += _ocr_section('Bản đọc mô phỏng lỗi đã gặp', results['ocr_synthetic_scripted'])
    if live:
        results['ocr_synthetic_live'] = run_ocr_benchmark('live', settings=settings)
        lines += _ocr_section('Mô hình Vision thật', results['ocr_synthetic_live'])

    print('[2/4] OCR · ảnh thật…', flush=True)
    lines += ['## 2. OCR · ảnh thật của cửa hàng', '']
    if live:
        results['ocr_real_live'] = run_dataset_benchmark(mode='live', settings=settings)
        lines += _ocr_section('Gọi mô hình và lưu bản đọc', results['ocr_real_live'])
    results['ocr_real_replay'] = run_dataset_benchmark(mode='replay', settings=settings)
    lines += _ocr_section('Phát lại bản đọc đã lưu bằng pipeline hiện tại', results['ocr_real_replay'])

    print('[3/4] Agent scorecard…', flush=True)
    lines += ['## 3. Agent · bộ câu hỏi hành vi', '']
    results['agent_offline'] = run_scorecard(args.agent_dataset, live=False, limit=args.agent_limit, verbose=False)
    lines += _agent_section(results['agent_offline'])
    if live:
        results['agent_live'] = run_scorecard(args.agent_dataset, live=True, limit=args.agent_limit, verbose=False)
        lines += _agent_section(results['agent_live'])

    print('[4/4] End-to-end OCR → interrupt…', flush=True)
    e2e = _end_to_end(settings, live)
    results['end_to_end'] = e2e
    lines += ['## 4. Luồng đầu-cuối trong chat (dừng ở interrupt rồi hủy, không ghi sổ)', '']
    if e2e['status'] == 'SKIPPED':
        lines.append(f'Bỏ qua: {e2e["reason"]}')
    else:
        lines += [f'Kết quả: **{e2e["status"]}** (`{e2e["mode"]}`)', '', '| Bước | Trạng thái | Thời gian (s) |', '|---|---|---:|']
        lines += [f'| {s["step"]} | `{s["status"]}` | {s["seconds"]} |' for s in e2e['steps']]
    lines += ['', '---', 'Mẫu ảnh thật còn nhỏ: dùng để phân tích lỗi theo nhóm, chưa đủ để công bố độ chính xác tổng quát.']

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = out / f'evaluation_{stamp}.md'
    md.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (out / f'evaluation_{stamp}.json').write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(f'Đã ghi {md}')


if __name__ == '__main__':
    main()
