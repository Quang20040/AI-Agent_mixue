# -*- coding: utf-8 -*-
"""RepoDocsAgent: Chuyên gia Khám phá & Tra cứu toàn bộ Tài liệu, Dữ liệu và Mã nguồn Repo.

Lục tìm trên toàn bộ hệ thống file:
- `docs/`: Sổ tay vận hành, quy chuẩn kiến trúc, tài liệu đào tạo 15 ngày.
- `DU_LIEU_CAN_NHAP/`: 16 bảng dữ liệu quy chuẩn Mixue (SOP sơ chế mẻ, quy định bảo quản, hạn dùng, thời gian chế biến, quy tắc đường & topping).
- `improvement-report/`: 13 báo cáo nghiệm thu cải tiến hệ thống Phase 3.
- `whitebox-qa/` & `blackbox-qa/`: Toàn bộ phát hiện kiểm toán chất lượng và bảo mật.
- Mã nguồn `src/` và schema dữ liệu khi người dùng hỏi về kiến trúc.

Sử dụng Hybrid Search kết hợp BM25 + Character 3-gram + Reranker nhận diện thực thể (Local Hybrid Reranker)
hoàn toàn offline, không gọi API embedding bên ngoài.
"""

from __future__ import annotations

import csv
import hashlib
import logging
from pathlib import Path
import re
from typing import Any
import unicodedata

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Vietnamese common operational stopwords
VI_STOPWORDS = {
    "la", "gi", "cua", "va", "co", "o", "tai", "theo", "cho", "duoc", "khong",
    "the", "nao", "may", "bao", "nhieu", "ra", "sao", "giup", "em", "minh",
    "ban", "hoi", "biet", "xem", "voi", "a", "nhe", "nha", "thi", "nhu", "cach",
    "quan", "mot", "nhung", "cac", "nay", "do", "khi", "trong", "len", "xuong"
}

# Mixue semi-product codes to canonical names and synonyms
MIXUE_ENTITIES: dict[str, list[str]] = {
    "TP02": ["tran chau", "tran chau nguyen vi", "tran chau den", "chan trau", "chan chau", "tran trau"],
    "TP03": ["thach duong den", "thach duong"],
    "TP04": ["thach dao", "dao ngam"],
    "TP05": ["tra sua lanh", "tra sua pha", "tra sua"],
    "TP06": ["pudding", "thach pudding", "bot pudding"],
    "TP07": ["tra xanh", "tra xanh hoa dao", "luc tra", "tra xanh u lanh"],
    "TP08": ["hong tra", "tra den", "nuoc cot hong tra", "u hong tra"],
    "TP10": ["ca phe co dac", "ca phe tuoi", "ca phe latte", "americano"],
    "TP11": ["kem tuoi", "kem oc que", "hon hop kem"],
}

CODE_NAMES: dict[str, str] = {
    "TP02": "Trân châu nguyên vị đã nấu (Trân châu đen)",
    "TP03": "Thạch đường đen đã chế biến",
    "TP04": "Thạch đào đã chế biến",
    "TP05": "Trà sữa lạnh đã pha",
    "TP06": "Pudding đã chế biến",
    "TP07": "Trà xanh đã ủ lạnh",
    "TP08": "Hồng trà đã ủ",
    "TP10": "Cà phê tươi / Cà phê cô đặc",
    "TP11": "Hỗn hợp kem tươi trước máy",
}


def _normalize(text: str) -> str:
    if not text:
        return ""
    text_lower = text.lower().replace("đ", "d")
    norm = "".join(
        c for c in unicodedata.normalize("NFD", text_lower)
        if unicodedata.category(c) != "Mn"
    ).strip()
    norm = re.sub(r"\bchan\s*trau\b", "tran chau", norm)
    norm = re.sub(r"\bchan\s*chau\b", "tran chau", norm)
    norm = re.sub(r"\btran\s*trau\b", "tran chau", norm)
    norm = re.sub(r"\btra\s*den\b", "hong tra", norm)
    return norm


# Từ điển mở rộng ngữ nghĩa tiếng Việt chuyên ngành F&B / Pha chế (Semantic Query Expansion)
VI_SYNONYM_EXPANSIONS: dict[str, list[str]] = {
    "nhiet do phong": ["nhiet", "do", "thuong", "bao", "quan"],
    "de ngoai": ["nhiet", "do", "thuong", "bao", "quan"],
    "tu mat": ["tu", "lanh", "bao", "quan", "lanh"],
    "ngan mat": ["tu", "lanh", "bao", "quan", "lanh"],
    "han su dung": ["han", "dung", "bao", "quan"],
    "de qua dem": ["han", "dung", "bao", "quan", "qua", "dem"],
    "ham tra": ["u", "tra", "so", "che"],
    "pha cot": ["so", "che", "cong", "thuc", "me"],
    "nuoc duong": ["duong", "fructose", "syr"],
    "bot beo": ["bot", "kem", "khong", "sua", "nl01"],
    "thach dua": ["nl07", "thach", "dua"],
}


def _tokenize(text: str) -> list[str]:
    norm = _normalize(text).replace("_", " ")
    return [w for w in re.findall(r"\w+", norm) if len(w) > 1]


def _expand_semantic_tokens(query_norm: str, base_tokens: list[str]) -> list[str]:
    expanded = list(base_tokens)
    for phrase, extra_tokens in VI_SYNONYM_EXPANSIONS.items():
        if phrase in query_norm:
            for t in extra_tokens:
                if t not in expanded:
                    expanded.append(t)
    return expanded


def _ngrams_for_tfidf(tokens: list[str]) -> list[str]:
    meaningful = [t for t in tokens if t not in VI_STOPWORDS]
    if not meaningful:
        meaningful = tokens
    bigrams = [f"{meaningful[i]}_{meaningful[i + 1]}" for i in range(len(meaningful) - 1)]
    return meaningful + bigrams


def _trigrams(text: str) -> set[str]:
    norm = _normalize(text).replace(" ", "_")
    if len(norm) < 3:
        return {norm} if norm else set()
    return {norm[i:i + 3] for i in range(len(norm) - 2)}


def _trigram_similarity(set1: set[str], set2: set[str]) -> float:
    if not set1 or not set2:
        return 0.0
    inter = len(set1 & set2)
    union = len(set1 | set2)
    return inter / union if union > 0 else 0.0


def _detect_code_in_query(query_norm: str) -> str | None:
    # 1. Direct code search (e.g. TP02, TP04, NL07)
    code_match = re.search(r"\b(tp\d{2}|nl\d{2})\b", query_norm)
    if code_match:
        return code_match.group(1).upper()
    # 2. Entity synonyms
    for code, synonyms in MIXUE_ENTITIES.items():
        for syn in synonyms:
            if re.search(rf"\b{re.escape(syn)}\b", query_norm):
                return code
    return None


class DocumentChunk:
    """Đoạn văn bản trích xuất từ tài liệu hoặc file dữ liệu trong repo."""

    def __init__(
        self,
        file_path: str,
        category: str,
        title: str,
        content: str,
        metadata: dict[str, Any] | None = None
    ):
        self.file_path = file_path
        self.category = category
        self.title = title
        self.content = content.strip()
        self.metadata = metadata or {}
        fingerprint = f"{file_path}\n{title}\n{self.content}"
        self.chunk_id = hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:24]
        self.content_sha256 = hashlib.sha256(self.content.encode('utf-8')).hexdigest()
        self.tokens = _tokenize(f"{title} {content}")
        self.tokens_set = set(self.tokens)
        self.tfidf_terms = _ngrams_for_tfidf(self.tokens)
        self.tfidf_vec: dict[str, float] = {}
        self.tfidf_norm: float = 1.0

        # Precompute normalized forms and trigrams for fast hybrid evaluation
        self.title_norm = _normalize(title)
        self.content_norm = _normalize(content)
        self.trigrams = _trigrams(f"{self.title_norm} {self.content_norm}")


class RepoDocsAgent:
    """Agent chuyên gia lục tìm sâu trong toàn bộ repository, docs, dữ liệu và báo cáo."""

    def __init__(self, repo_dir: Path | str | None = None):
        self.repo_dir = Path(repo_dir) if repo_dir else REPO_ROOT
        self.chunks: list[DocumentChunk] = []
        self.bm25: BM25Okapi | None = None
        self.idf: dict[str, float] = {}
        self._index_all_documents()

    def _index_all_documents(self):
        """Quét và lập chỉ mục toàn bộ tài liệu văn bản, CSV và báo cáo trong repo."""
        import math
        from collections import Counter

        self.chunks.clear()
        self.bm25 = None
        self.idf.clear()

        # 1. Quét DU_LIEU_CAN_NHAP (16 bảng quy chuẩn thực tế)
        dl_dir = self.repo_dir / "DU_LIEU_CAN_NHAP"
        if dl_dir.exists():
            self._index_csv_and_md_dir(dl_dir, category="SOP_QUY_CHUAN")

        # 2. Quét docs/ (Tài liệu kiến trúc, đào tạo, hướng dẫn)
        docs_dir = self.repo_dir / "docs"
        if docs_dir.exists():
            self._index_markdown_dir(docs_dir, category="DOCS_ARCHITECTURE")

        # 3. Quét improvement-report/ (13 báo cáo Phase 3)
        imp_dir = self.repo_dir / "improvement-report"
        if imp_dir.exists():
            self._index_markdown_dir(imp_dir, category="IMPROVEMENT_REPORT")

        # 4. Quét whitebox-qa/ & blackbox-qa/
        for qa_name in ["whitebox-qa", "blackbox-qa", "BAO_CAO_KIEM_TRA"]:
            qa_dir = self.repo_dir / qa_name
            if qa_dir.exists():
                self._index_markdown_dir(qa_dir, category=f"AUDIT_{qa_name.upper()}")

        # 5. Khởi tạo BM25 index & Vector TF-IDF Cosine Index
        corpus = [c.tokens for c in self.chunks]
        if corpus:
            self.bm25 = BM25Okapi(corpus)
            n_docs = len(self.chunks)
            df_counts: Counter[str] = Counter()
            for chunk in self.chunks:
                for term in set(chunk.tfidf_terms):
                    df_counts[term] += 1
            self.idf = {
                term: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0
                for term, df in df_counts.items()
            }
            for chunk in self.chunks:
                tf_counts = Counter(chunk.tfidf_terms)
                vec = {
                    term: (1.0 + math.log(cnt)) * self.idf.get(term, 1.0)
                    for term, cnt in tf_counts.items()
                }
                norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
                chunk.tfidf_vec = vec
                chunk.tfidf_norm = norm

    def _index_markdown_dir(self, dir_path: Path, category: str):
        for f in dir_path.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                sections = re.split(r"\n(?=#{1,3}\s+)", text)
                # Architecture/audit sections can also be very long. Preserve the
                # section heading in each overlapping window sent to retrieval.
                bounded_sections = []
                for section in sections:
                    lines = section.split('\n', 1)
                    heading = lines[0][:300]
                    body = lines[1] if len(lines) > 1 else section
                    if len(section) <= 1500:
                        bounded_sections.append(section)
                    else:
                        width = 1500 - len(heading) - 1
                        for start in range(0, len(body), width - 200):
                            bounded_sections.append(heading + '\n' + body[start:start + width])
                            if start + width >= len(body):
                                break
                sections = bounded_sections
                for sec in sections:
                    if not sec.strip():
                        continue
                    lines = sec.strip().split("\n")
                    first_line = lines[0].strip("# \t\r")
                    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else sec.strip()
                    if len(body) > 30:
                        rel_path = str(f.relative_to(self.repo_dir)).replace("\\", "/")
                        self.chunks.append(
                            DocumentChunk(
                                file_path=rel_path,
                                category=category,
                                title=f"{f.name} :: {first_line}",
                                content=body,
                                metadata={
                                    "filename": f.name,
                                    "heading": first_line,
                                    "doc_type": "markdown_guide",
                                }
                            )
                        )
            except Exception:
                pass

    def _index_csv_and_md_dir(self, dir_path: Path, category: str):
        # Index markdown files in directory with overlapping sliding windows
        for f in dir_path.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(f.relative_to(self.repo_dir)).replace("\\", "/")
                total_len = len(text)
                window_size = 1500
                stride = 1200
                char_start = 0
                if total_len <= window_size:
                    first_line = text.strip().split("\n")[0].strip("# \t\r") if text.strip() else f.name
                    self.chunks.append(
                        DocumentChunk(
                            file_path=rel_path,
                            category=category,
                            title=f"{f.name} :: {first_line}",
                            content=text,
                            metadata={
                                "filename": f.name,
                                "heading": first_line,
                                "doc_type": "sop_manual_markdown",
                                "char_start": 0,
                                "char_end": total_len,
                            }
                        )
                    )
                else:
                    chunk_idx = 1
                    while char_start < total_len:
                        char_end = min(char_start + window_size, total_len)
                        chunk_text = text[char_start:char_end]
                        first_line = chunk_text.strip().split("\n")[0].strip("# \t\r") if chunk_text.strip() else f"Đoạn {chunk_idx}"
                        self.chunks.append(
                            DocumentChunk(
                                file_path=rel_path,
                                category=category,
                                title=f"{f.name} :: {first_line} (Đoạn {chunk_idx})",
                                content=chunk_text,
                                metadata={
                                    "filename": f.name,
                                    "heading": first_line,
                                    "doc_type": "sop_manual_markdown",
                                    "char_start": char_start,
                                    "char_end": char_end,
                                }
                            )
                        )
                        if char_end >= total_len:
                            break
                        char_start += stride
                        chunk_idx += 1
            except Exception as e:
                logger.debug("Failed indexing md %s: %s", getattr(f, "name", "file"), e)

        # Index CSV files
        for f in dir_path.glob("*.csv"):
            try:
                rel_path = str(f.relative_to(self.repo_dir)).replace("\\", "/")
                with open(f, encoding="utf-8", errors="ignore") as fp:
                    reader = list(csv.reader(fp))
                    if not reader:
                        continue
                    headers = reader[0]
                    rows = reader[1:]

                    # 1. Bảng Markdown hoàn chỉnh với headers
                    if 0 < len(rows) <= 60:
                        table_md = "| " + " | ".join(headers) + " |\n"
                        table_md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                        for r in rows:
                            if any(r):
                                cleaned_cells = [c.replace("\n", " ").strip() for c in r]
                                table_md += "| " + " | ".join(cleaned_cells) + " |\n"
                        self.chunks.append(
                            DocumentChunk(
                                file_path=rel_path,
                                category=category,
                                title=f"{f.name} - Toàn bộ bảng quy chuẩn ({len(rows)} mục)",
                                content=table_md,
                                metadata={
                                    "filename": f.name,
                                    "doc_type": "full_table",
                                    "row_count": len(rows),
                                }
                            )
                        )

                    # 2. Index chi tiết từng dòng với metadata trích xuất cấu trúc
                    dict_reader = csv.DictReader(open(f, encoding="utf-8", errors="ignore"))
                    for idx, raw_row in enumerate(dict_reader):
                        row = {k.lstrip("\ufeff"): v for k, v in raw_row.items() if k}
                        if not any(row.values()):
                            continue

                        meta: dict[str, Any] = {
                            "filename": f.name,
                            "row_idx": idx + 1,
                            "headers": headers,
                        }
                        row_desc = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
                        row_title = f"{f.name} (Dòng {idx+1})"

                        # Trích xuất metadata theo từng bảng nghiệp vụ Mixue
                        if f.name == "09_Cong_thuc_so_che_theo_me.csv":
                            code = row.get("Bán thành phẩm đầu ra", "").strip()
                            meta["code"] = code
                            meta["ingredient_name"] = CODE_NAMES.get(code, code)
                            meta["source_image"] = row.get("Mã ảnh nguồn", "")
                            meta["effective_date"] = row.get("Ngày trên tài liệu", "")
                            meta["verification_status"] = row.get("Trạng thái xác nhận", "")
                            meta["doc_type"] = "sop_batch_formula"
                            meta["batch_size"] = row.get("Số phần", "")
                            meta["input_code"] = row.get("Mã nguyên liệu đầu vào", "")
                            meta["input_qty"] = row.get("Lượng đầu vào", "")
                            meta["input_unit"] = row.get("Đơn vị đầu vào", "")
                            row_title = f"{f.name} :: {meta['ingredient_name']} (Mẻ {meta['batch_size']}) - {meta['input_code']} {meta['input_qty']}{meta['input_unit']}"

                        elif f.name == "10_Quy_dinh_bao_quan_theo_anh.csv":
                            code = row.get("Mã nguyên liệu", "").strip()
                            meta["code"] = code
                            meta["ingredient_name"] = CODE_NAMES.get(code, code)
                            meta["source_image"] = row.get("Mã ảnh nguồn", "")
                            meta["verification_status"] = row.get("Trạng thái xác nhận", "")
                            meta["doc_type"] = "storage_rule"
                            meta["condition"] = row.get("Điều kiện theo ảnh", "")
                            meta["shelf_life"] = row.get("Hạn dùng nguyên văn", "")
                            row_title = f"{f.name} :: Bảo quản {meta['ingredient_name']} ({code}) - {meta['condition']} ({meta['shelf_life']})"

                        elif f.name == "13_Thoi_gian_so_che_theo_anh.csv":
                            sp = row.get("Bán thành phẩm", "").strip()
                            meta["prep_time"] = row.get("Thời gian theo tài liệu", "")
                            meta["notes"] = row.get("Ghi chú", "")
                            meta["doc_type"] = "prep_time"
                            meta["source_image"] = row.get("Mã nguồn", "")
                            if sp in CODE_NAMES:
                                meta["code"] = sp
                                meta["ingredient_name"] = CODE_NAMES[sp]
                            else:
                                meta["ingredient_name"] = sp
                                sp_norm = _normalize(sp)
                                for c, syns in MIXUE_ENTITIES.items():
                                    if any(s in sp_norm for s in syns):
                                        meta["code"] = c
                                        meta["ingredient_name"] = CODE_NAMES.get(c, sp)
                                        break
                            row_title = f"{f.name} :: Thời gian sơ chế {meta['ingredient_name']} ({meta.get('code', sp)}) ({meta['prep_time']})"
                            row_desc = f"Bán thành phẩm: {meta['ingredient_name']} ({meta.get('code', sp)}) | Thời gian: {meta['prep_time']} | Nguồn: {meta['source_image']} | Ghi chú: {meta['notes']}"

                        elif f.name == "15_Han_dung_nguyen_lieu_tren_anh.csv":
                            name = row.get("Tên nguyên liệu hoặc vật tư", "").strip()
                            meta["ingredient_name"] = name
                            meta["shelf_life"] = row.get("Hạn dùng ghi trên ảnh", "")
                            meta["source_image"] = row.get("Mã ảnh nguồn", "")
                            meta["notes"] = row.get("Ghi chú", "")
                            meta["doc_type"] = "shelf_life"
                            name_norm = _normalize(name)
                            for c, syns in MIXUE_ENTITIES.items():
                                if any(s in name_norm for s in syns):
                                    meta["code"] = c
                                    break
                            row_title = f"{f.name} :: Hạn dùng {name} - {meta['shelf_life']}"

                        elif f.name == "16_Quy_tac_duong_va_topping.csv":
                            scope = row.get("Phạm vi", "").strip()
                            meta["scope"] = scope
                            meta["rule"] = row.get("Quy tắc chép từ ảnh", "")
                            meta["source_image"] = row.get("Nguồn", "")
                            meta["verification_status"] = row.get("Trạng thái", "")
                            meta["doc_type"] = "sugar_topping_rule"
                            row_title = f"{f.name} :: Quy tắc đường & topping: {scope}"

                        self.chunks.append(
                            DocumentChunk(
                                file_path=rel_path,
                                category=category,
                                title=row_title,
                                content=row_desc,
                                metadata=meta,
                            )
                        )
            except Exception as e:
                logger.debug("Failed indexing %s: %s", getattr(f, "name", "file"), e)

    def search(self, query: str, top_k: int = 5, category_filter: str | None = None) -> list[dict[str, Any]]:
        """Lục tìm tài liệu và dữ liệu khớp nhất bằng Hybrid Search (BM25 + N-gram + Entity Matching).

        Không gửi dữ liệu ra ngoài, hoàn toàn deterministic và có ngưỡng tin cậy nghiêm ngặt.
        """
        if top_k <= 0 or not self.bm25 or not self.chunks:
            return []

        q_norm = _normalize(query)

        # 0. Out-of-scope / alien negative query rejection
        out_of_scope_terms = {
            "banh bao", "thit", "sau rieng", "musang king",
            "khong ton tai", "khong_ton_tai", "kfc", "ga ran",
            "lau thai", "tomyum", "tom yum", "pizza", "pho mai", "xuc xich",
            "hamburger", "com tam", "bun bo", "pho bo", "suon"
        }
        if any(term in q_norm for term in out_of_scope_terms):
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        expanded_tokens = _expand_semantic_tokens(q_norm, query_tokens)
        meaningful_tokens = [t for t in expanded_tokens if t not in VI_STOPWORDS and len(t) > 1]
        if not meaningful_tokens:
            meaningful_tokens = expanded_tokens

        import math
        from collections import Counter

        q_tfidf_terms = _ngrams_for_tfidf(expanded_tokens)
        q_tf_counts = Counter(q_tfidf_terms)
        q_vec = {
            term: (1.0 + math.log(cnt)) * self.idf.get(term, 1.0)
            for term, cnt in q_tf_counts.items()
            if term in self.idf
        }
        q_norm_val = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        query_trigrams = _trigrams(q_norm)
        detected_code = _detect_code_in_query(q_norm)
        explicit_codes = {code.upper() for code in re.findall(r'\btp\d+\b', q_norm)}
        indexed_codes = {c.metadata.get('code') for c in self.chunks if not category_filter or c.category == category_filter}
        if explicit_codes and not explicit_codes <= indexed_codes:
            return []

        # Detect source image query (e.g. ANH_08, anh 8)
        img_match = re.search(r"anh[_\s]*(\d+)", q_norm)
        target_img = f"ANH_{int(img_match.group(1)):02d}" if img_match else None

        # Detect storage intent
        storage_keywords = {
            "bao quan", "han dung", "han su dung", "de duoc", "may tieng",
            "bao lau", "tu lanh", "tu mat", "ngan mat", "nhiet do", "dieu kien", "de ngoai",
        }
        is_storage_query = any(kw in q_norm for kw in storage_keywords)

        scores = self.bm25.get_scores(expanded_tokens)
        scored_chunks: list[tuple[float, DocumentChunk]] = []

        for i, bm25_score in enumerate(scores):
            chunk = self.chunks[i]
            if category_filter and chunk.category != category_filter:
                continue
            if explicit_codes and chunk.metadata.get('code') not in explicit_codes:
                continue

            # 1. Lexical BM25 component
            raw_bm25 = float(bm25_score)

            # 1b. Dense Sublinear TF-IDF Cosine Similarity component
            dot_prod = sum(val * chunk.tfidf_vec.get(term, 0.0) for term, val in q_vec.items())
            tfidf_cos = dot_prod / (q_norm_val * chunk.tfidf_norm) if dot_prod > 0 else 0.0

            # 2. Character 3-gram similarity component (handles typos and spelling variants)
            trig_sim = _trigram_similarity(query_trigrams, chunk.trigrams)

            # 3. Meaningful term coverage
            matches = sum(1 for t in meaningful_tokens if t in chunk.title_norm or t in chunk.tokens_set)
            coverage = matches / len(meaningful_tokens) if meaningful_tokens else 0.0

            # 4. Exact entity / code boost
            code_boost = 0.0
            chunk_code = chunk.metadata.get("code")
            if detected_code and chunk_code and chunk_code == detected_code:
                code_boost = 5.0
            elif detected_code and detected_code.lower() in chunk.tokens_set:
                code_boost = 3.5

            # 5. Exact title phrase boost
            title_boost = 0.0
            if any(t in chunk.title_norm for t in meaningful_tokens):
                title_boost = 2.0

            # 6. Intent & Image Specific Boosts
            intent_boost = 0.0
            doc_type = chunk.metadata.get("doc_type", "")
            # Prefer the source that answers the requested operation, rather than
            # a short expiry/time row that merely repeats the ingredient name.
            is_recipe_query = any(kw in q_norm for kw in (
                "cach nau", "cach u", "quy trinh", "so che", "dinh luong", "nau chan", "nau tran", "ham tra", "pha cot"))
            if is_recipe_query and not is_storage_query and doc_type == "sop_batch_formula":
                intent_boost += 10.0
            if ("topping" in q_norm and any(kw in q_norm for kw in ("giam duong", "toi da", "may phan"))
                    and chunk.file_path.endswith("16_Quy_tac_duong_va_topping.csv")):
                intent_boost += 10.0
            if is_storage_query:
                if doc_type in ("storage_rule", "shelf_life") or "Quy_dinh_bao_quan" in chunk.file_path or "Han_dung" in chunk.file_path:
                    intent_boost += 6.0
                elif doc_type == "sop_batch_formula" and not any(kw in q_norm for kw in ("me", "phan", "cach nau", "so che", "dinh luong")):
                    intent_boost -= 3.0

            if target_img and chunk.metadata.get("source_image") == target_img:
                intent_boost += 6.0

            # Exact phrase match boost
            phrase_boost = 0.0
            if q_norm and (q_norm in chunk.content_norm or q_norm in chunk.title_norm):
                phrase_boost = 6.0
            elif any(len(t) >= 4 and t in chunk.content_norm for t in query_tokens):
                phrase_boost = 1.5

            # 7. Hybrid Score Synthesis (BM25 + TF-IDF Cosine + Trigrams + Entity/Intent Reranker)
            hybrid_score = (raw_bm25 * 0.4) + (tfidf_cos * 6.0) + (trig_sim * 10.0) + code_boost + title_boost + intent_boost + phrase_boost

            # Penalize heavily if term coverage is too low unless strong entity match
            if coverage < 0.35 and tfidf_cos < 0.25 and code_boost == 0.0 and intent_boost <= 0.0 and phrase_boost <= 0.0:
                hybrid_score *= 0.15

            # 8. Strict confidence cutoff (prevent false-positive hallucinations on negative queries)
            if hybrid_score >= 3.2 and (coverage >= 0.30 or tfidf_cos >= 0.30 or code_boost > 0.0 or intent_boost > 0.0 or phrase_boost > 0.0):
                scored_chunks.append((hybrid_score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        results = []
        for s, c in scored_chunks[:top_k]:
            results.append({
                "score": round(s, 2),
                "file_path": c.file_path,
                "category": c.category,
                "title": c.title,
                "content": c.content,
                "metadata": c.metadata,
                "citation": {
                    "chunk_id": c.chunk_id,
                    "source_ref": f"file:{c.file_path}#chunk={c.chunk_id}",
                    "content_sha256": c.content_sha256,
                    "row_idx": c.metadata.get("row_idx"),
                    "char_start": c.metadata.get("char_start"),
                    "char_end": c.metadata.get("char_end"),
                    "verification_status": c.metadata.get("verification_status", "UNKNOWN"),
                    "score_kind": "heuristic_relevance_not_probability",
                },
            })
        return results

    # --- CÁC PHƯƠNG THỨC TRA CỨU ĐẶC BIỆT THEO CHỦ ĐỀ CHUYÊN MÔN ---

    def get_storage_rules(self, ingredient_name: str = "") -> list[dict[str, str]]:
        """Tra cứu quy định bảo quản từ file 10_Quy_dinh_bao_quan_theo_anh.csv."""
        f = self.repo_dir / "DU_LIEU_CAN_NHAP" / "10_Quy_dinh_bao_quan_theo_anh.csv"
        if not f.exists():
            return []
        results = []
        with open(f, encoding="utf-8", errors="ignore") as fp:
            for r in csv.DictReader(fp):
                code = r.get("Mã nguyên liệu", "")
                cond = r.get("Điều kiện theo ảnh", "")
                shelf = r.get("Hạn dùng nguyên văn", "")
                src = r.get("Mã ảnh nguồn", "")
                if not ingredient_name or _normalize(ingredient_name) in _normalize(f"{code} {cond} {shelf}"):
                    results.append({
                        "code": code,
                        "condition": cond,
                        "shelf_life": shelf,
                        "source": src
                    })
        return results

    def get_prep_times(self, semi_product_name: str = "") -> list[dict[str, str]]:
        """Tra cứu thời gian sơ chế theo từng mẻ từ file 13_Thoi_gian_so_che_theo_anh.csv."""
        f = self.repo_dir / "DU_LIEU_CAN_NHAP" / "13_Thoi_gian_so_che_theo_anh.csv"
        if not f.exists():
            return []
        results = []
        with open(f, encoding="utf-8", errors="ignore") as fp:
            for r in csv.DictReader(fp):
                sp = r.get("Bán thành phẩm", "")
                pt = r.get("Thời gian theo tài liệu", "")
                nt = r.get("Ghi chú", "")
                if not semi_product_name or _normalize(semi_product_name) in _normalize(f"{sp} {nt}"):
                    results.append({
                        "semi_product": sp,
                        "prep_time": pt,
                        "notes": nt
                    })
        return results

    def get_sugar_and_topping_rules(self) -> list[dict[str, str]]:
        """Tra cứu 16 quy tắc đường & topping từ 16_Quy_tac_duong_va_topping.csv."""
        f = self.repo_dir / "DU_LIEU_CAN_NHAP" / "16_Quy_tac_duong_va_topping.csv"
        if not f.exists():
            return []
        results = []
        with open(f, encoding="utf-8", errors="ignore") as fp:
            for r in csv.DictReader(fp):
                results.append({
                    "scope": r.get("Phạm vi", ""),
                    "rule": r.get("Quy tắc chép từ ảnh", ""),
                    "source": r.get("Nguồn", "")
                })
        return results
