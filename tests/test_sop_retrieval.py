from itertools import pairwise
from pathlib import Path

from src.agent.multi_agent.repo_docs_agent import RepoDocsAgent
from src.engine.sop_evaluation import evaluate_sop_retrieval


def test_long_sop_tail_is_indexed_and_retrieved(tmp_path):
    folder = tmp_path / 'DU_LIEU_CAN_NHAP'
    folder.mkdir()
    content = '# Quy trình\n' + 'Hướng dẫn khuấy trà.\n' * 160 + '\nCảnh báo: KHONG_DE_QUA_DEM phải hủy cuối ngày.'
    (folder / 'sop.md').write_text(content, encoding='utf-8')
    agent = RepoDocsAgent(tmp_path)
    hits = agent.search('KHONG_DE_QUA_DEM', category_filter='SOP_QUY_CHUAN')
    assert hits and 'KHONG_DE_QUA_DEM' in hits[0]['content']
    assert hits[0]['metadata']['char_start'] > 1500
    assert max(len(chunk.content) for chunk in agent.chunks) <= 1500
    # Overlapping windows collectively retain every character, including the tail.
    spans = sorted((chunk.metadata['char_start'], chunk.metadata['char_end']) for chunk in agent.chunks)
    assert spans[0][0] == 0
    assert all(a[1] >= b[0] for a, b in pairwise(spans))


def test_sop_retrieval_benchmark_evaluator():
    """Kiểm tra benchmark 30 ca tra cứu SOP: Hit@1 >= 90%, MRR >= 0.90, Rejection >= 90%."""
    report = evaluate_sop_retrieval()
    metrics = report["metrics"]
    assert metrics["Hit@1"] >= 90.0, f"Hit@1 too low: {metrics['Hit@1']}%"
    assert metrics["Hit@3"] >= 90.0, f"Hit@3 too low: {metrics['Hit@3']}%"
    assert metrics["MRR"] >= 0.90, f"MRR too low: {metrics['MRR']}"
    assert metrics["Negative_Rejection_Rate_pct"] >= 90.0, f"Rejection too low: {metrics['Negative_Rejection_Rate_pct']}%"


def test_sop_metadata_integrity():
    """Kiểm tra tính toàn vẹn metadata cấu trúc trong các chunk bảng nghiệp vụ."""
    agent = RepoDocsAgent(Path("."))
    # Chunks from 09_Cong_thuc_so_che_theo_me.csv should have doc_type, code, ingredient_name, batch_size
    batch_chunks = [c for c in agent.chunks if c.metadata.get("doc_type") == "sop_batch_formula"]
    assert len(batch_chunks) > 0, "No batch formula chunks found"
    for c in batch_chunks[:5]:
        assert c.metadata.get("code"), "Missing code in batch chunk"
        assert c.metadata.get("ingredient_name"), "Missing ingredient_name in batch chunk"
        assert "batch_size" in c.metadata, "Missing batch_size in batch chunk"
        assert c.metadata.get("verification_status") is not None, "Missing verification_status"

    # Chunks from 10_Quy_dinh_bao_quan_theo_anh.csv
    storage_chunks = [c for c in agent.chunks if c.metadata.get("doc_type") == "storage_rule"]
    assert len(storage_chunks) > 0, "No storage rule chunks found"
    for c in storage_chunks[:5]:
        assert c.metadata.get("shelf_life"), "Missing shelf_life in storage chunk"
        assert c.metadata.get("condition"), "Missing condition in storage chunk"


def test_negative_query_rejection():
    """Kiểm tra từ chối tìm kiếm cho câu hỏi ngoài phạm vi ẩm thực Mixue."""
    agent = RepoDocsAgent(Path("."))
    assert agent.search("Cách làm bánh bao nhân thịt Mixue") == []
    assert agent.search("quy trinh chien ga ran kfc tai quay") == []
    assert agent.search("Định lượng pizza phô mai xúc xích") == []
    assert agent.search("Công thức nấu lẩu thái tomyum Mixue") == []
    assert agent.search("Cách nấu topping KHONG_TON_TAI_999") == []


def test_citations_identify_exact_content_and_are_stable():
    import hashlib
    agent = RepoDocsAgent(Path('.'))
    hits = agent.search('TP02', top_k=2)
    assert hits
    for hit in hits:
        citation = hit['citation']
        assert citation['content_sha256'] == hashlib.sha256(hit['content'].encode('utf-8')).hexdigest()
        assert citation['source_ref'].endswith('#chunk=' + citation['chunk_id'])
        assert citation['score_kind'] == 'heuristic_relevance_not_probability'
    assert agent.search('TP02', top_k=0) == []
    assert agent.search('TP02', top_k=-1) == []


def test_benchmark_requires_both_file_and_entity():
    from types import SimpleNamespace
    from src.engine.sop_evaluation import SOPEvaluationEngine
    evaluator = SOPEvaluationEngine.__new__(SOPEvaluationEngine)
    case = {'query_id': 'strict', 'query': 'TP02', 'expected_codes': ['TP02'],
            'expected_files': ['expected.csv'], 'expected_keywords': ['pearl']}
    for filename, code in [('expected.csv', 'TP06'), ('other.csv', 'TP02')]:
        evaluator.agent = SimpleNamespace(search=lambda *a, **kw: [
            {'file_path': filename, 'metadata': {'code': code}, 'content': 'pearl'}])
        assert evaluator.evaluate_case(case)['passed'] is False

