"""Error-taxonomy benchmark: raw vision reading vs. the verifiable OCR pipeline."""
from src.agent.config import AgentSettings
from src.engine.ocr_evaluation import TAXONOMY_7, run_ocr_benchmark


def test_scripted_benchmark_covers_four_images_and_seven_groups():
    report = run_ocr_benchmark('scripted')
    assert [c['image_key'] for c in report['cases']] == ['printed_pos', 'handwritten_ledger', 'blurry_image', 'composite_multi_doc']
    assert all(c['status'] == 'NEEDS_REVIEW' for c in report['cases'])
    assert list(report['verified_summary']['taxonomy_7']) == list(TAXONOMY_7)
    assert report['verified_summary']['fields_evaluated'] == 4 * 11


def test_verification_layer_stops_every_scripted_trap():
    report = run_ocr_benchmark('scripted')
    raw, verified = report['raw_summary']['taxonomy_7'], report['verified_summary']['taxonomy_7']
    # Each failure family is present in the raw reading...
    for outcome in ('digit_error', 'unit_error', 'layout_error', 'wrong_document_source', 'unflagged_inconsistency'):
        assert raw[outcome] >= 1, outcome
    # ...and none of them reaches the form after verification; they are flagged instead.
    assert report['verified_summary']['errors_reaching_form'] == 0
    assert verified['correctly_flagged_uncertain'] > 0
    # Clean printed values are not over-flagged.
    printed = report['cases'][0]['verified']['error_taxonomy_counts']
    assert printed['correct_read'] == 5


def test_handwritten_ledger_case_keeps_raw_text_and_never_scales_units():
    case = run_ocr_benchmark('scripted')['cases'][1]
    readings = case['field_readings']
    assert readings['cash_vnd']['raw_text'] == '653' and readings['cash_vnd']['normalized_value'] is None
    assert readings['bank_transfer_vnd']['is_calculated'] is True
    assert case['verified']['field_results']['expenses_vnd']['outcome'] == 'correctly_flagged_uncertain'
    assert case['raw']['field_results']['expenses_vnd']['outcome'] == 'layout_error'


def test_live_mode_without_provider_skips_instead_of_inventing_results():
    report = run_ocr_benchmark('live', settings=AgentSettings())
    assert all(c.get('skipped_reason') for c in report['cases'])
    assert report['verified_summary']['fields_evaluated'] == 0


# --- Labelled real-photo dataset -------------------------------------------------
import json  # noqa: E402
from pathlib import Path  # noqa: E402

from src.engine.ocr_evaluation import load_ocr_dataset, run_dataset_benchmark  # noqa: E402
from src.engine.vision_ocr import MONEY_FIELDS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / 'data' / 'ocr_eval' / 'real_photos.json'


def test_real_photo_labels_match_the_approved_shift_reports():
    dataset = load_ocr_dataset(DATASET)
    approved = {r['shift_code']: r for r in json.loads((ROOT / 'data' / 'shift_reports.json').read_text(encoding='utf-8'))
                if str(r.get('business_date')).startswith('2026-10-14') and r.get('status') == 'APPROVED'}
    for case in dataset['cases']:
        assert (ROOT / case['image']).is_file(), case['image']
        report = approved[case['shift_hint']]
        for field, gt in case['fields'].items():
            if gt['expected_value'] is not None:
                assert gt['expected_value'] == report[field], (case['case_id'], field)


def _write_reading(folder, case_id, fields):
    reading = {'fields': {n: {'value': None, 'status': 'not_present', 'evidence': '', 'raw_text': '', 'source': 'not_applicable'}
                          for n in MONEY_FIELDS},
               'document_date': '2026-10-14', 'signed_by': 'Hà', 'bank_transfer_formula': '', 'raw_text': 'Ca sáng bàn giao',
               'warnings': [], 'document_type': 'handwritten_ledger', 'pos_region_text': '', 'handwritten_region_text': 'Ca sáng'}
    reading['fields'].update(fields)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{case_id}.json').write_text(json.dumps({'model': 'test-model', 'latency_s': 1.5, 'usage': {},
                                                        'raw_content': json.dumps(reading, ensure_ascii=False)}), encoding='utf-8')


def test_replay_scores_saved_reading_and_skips_unrecorded_photos(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    hw = 'handwritten_ledger'
    _write_reading(tmp_path, 'REAL_CA_SANG_20261014', {
        'cash_vnd': {'value': 653000, 'status': 'read', 'raw_text': '653', 'source': hw, 'evidence': 'Tiền mặt: 653'},
        'bank_transfer_vnd': {'value': 1591000, 'status': 'read', 'raw_text': '962 + 629', 'source': hw, 'evidence': 'CK: 962 + 629'},
        'petty_cash_kept_vnd': {'value': 1000000, 'status': 'read', 'raw_text': '1.000.000đ', 'source': hw, 'evidence': 'Cố định két: 1.000.000đ'},
    })
    report = run_dataset_benchmark(DATASET, mode='replay', readings_dir=tmp_path)
    scored = [c for c in report['cases'] if 'verified' in c]
    assert [c['case_id'] for c in scored] == ['REAL_CA_SANG_20261014']
    assert all(c['status'] == 'NO_SAVED_READING' for c in report['cases'] if 'verified' not in c)
    results = scored[0]['verified']['field_results']
    assert results['cash_vnd']['outcome'] == 'correctly_flagged_uncertain'
    assert results['petty_cash_kept_vnd']['outcome'] == 'correct_read'
    assert scored[0]['raw']['field_results']['cash_vnd']['outcome'] == 'unit_error'
    assert scored[0]['reading_meta']['model'] == 'test-model'


def test_live_dataset_run_without_provider_is_skipped_not_invented(tmp_path, monkeypatch):
    from src.agent.config import AgentSettings
    monkeypatch.chdir(ROOT)
    report = run_dataset_benchmark(DATASET, mode='live', settings=AgentSettings(), readings_dir=tmp_path)
    assert all(c['status'] == 'OCR_DISABLED' for c in report['cases'])
    assert not list(tmp_path.iterdir())


def test_evaluation_script_end_to_end_stops_at_interrupt_and_cancels(tmp_path, monkeypatch):
    from scripts.run_live_evaluation import _end_to_end
    hw = 'handwritten_ledger'
    _write_reading(tmp_path, 'REAL_CA_SANG_20261014', {
        'cash_vnd': {'value': 653000, 'status': 'read', 'raw_text': '653', 'source': hw, 'evidence': 'Tiền mặt: 653'},
    })
    writes = []
    monkeypatch.setattr('src.engine.shift_service.upsert_shift_report', lambda *a, **k: writes.append(a) or (True, '', {}))
    result = _end_to_end(AgentSettings(), live=False, readings_dir=tmp_path)
    assert result['status'] == 'PASS', result
    assert [s['status'] for s in result['steps']] == ['SUCCESS', 'SUCCESS', 'PENDING_APPROVAL', 'CANCELLED']
    assert writes == []
