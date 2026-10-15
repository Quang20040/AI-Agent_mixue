# -*- coding: utf-8 -*-
"""RepoDocsAgent: Chuyên gia Khám phá & Tra cứu toàn bộ Tài liệu, Dữ liệu và Mã nguồn Repo.

Lục tìm trên toàn bộ hệ thống file:
- `docs/`: Sổ tay vận hành, quy chuẩn kiến trúc, tài liệu đào tạo 15 ngày.
- `DU_LIEU_CAN_NHAP/`: 16 bảng dữ liệu quy chuẩn Mixue (SOP sơ chế mẻ, quy định bảo quản, hạn dùng, thời gian chế biến, quy tắc đường & topping).
- `improvement-report/`: 13 báo cáo nghiệm thu cải tiến hệ thống Phase 3.
- `whitebox-qa/` & `blackbox-qa/`: Toàn bộ phát hiện kiểm toán chất lượng và bảo mật.
- Mã nguồn `src/` và schema dữ liệu khi người dùng hỏi về kiến trúc.
"""

from pathlib import Path
import csv
import re
import unicodedata
from typing import Any
from rank_bm25 import BM25Okapi

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _normalize(text: str) -> str:
    if not text:
        return ""
    text_lower = text.lower().replace("đ", "d")
    return "".join(
        c for c in unicodedata.normalize("NFD", text_lower)
        if unicodedata.category(c) != "Mn"
    ).strip()


def _tokenize(text: str) -> list[str]:
    norm = _normalize(text)
    return [w for w in re.findall(r"\w+", norm) if len(w) > 1]


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
        self.tokens = _tokenize(f"{title} {content}")


class RepoDocsAgent:
    """Agent chuyên gia lục tìm sâu trong toàn bộ repository, docs, dữ liệu và báo cáo."""

    def __init__(self, repo_dir: Path | str | None = None):
        self.repo_dir = Path(repo_dir) if repo_dir else REPO_ROOT
        self.chunks: list[DocumentChunk] = []
        self.bm25: BM25Okapi | None = None
        self._index_all_documents()

    def _index_all_documents(self):
        """Quét và lập chỉ mục toàn bộ tài liệu văn bản, CSV và báo cáo trong repo."""
        self.chunks.clear()

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

        # 5. Khởi tạo BM25 index
        corpus = [c.tokens for c in self.chunks]
        if corpus:
            self.bm25 = BM25Okapi(corpus)

    def _index_markdown_dir(self, dir_path: Path, category: str):
        for f in dir_path.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                # Tách theo heading ## hoặc ###
                sections = re.split(r"\n(?=#{1,3}\s+)", text)
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
                                content=body[:1500],
                                metadata={"filename": f.name, "heading": first_line}
                            )
                        )
            except Exception:
                pass

    def _index_csv_and_md_dir(self, dir_path: Path, category: str):
        # Index markdown files in directory
        for f in dir_path.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                sections = re.split(r"\n(?=#{1,3}\s+)", text)
                for sec in sections:
                    if not sec.strip():
                        continue
                    lines = sec.strip().split("\n")
                    first_line = lines[0].strip("# \t\r")
                    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else sec.strip()
                    rel_path = str(f.relative_to(self.repo_dir)).replace("\\", "/")
                    self.chunks.append(
                        DocumentChunk(
                            file_path=rel_path,
                            category=category,
                            title=f"{f.name} :: {first_line}",
                            content=body[:1500],
                            metadata={"filename": f.name}
                        )
                    )
            except Exception:
                pass

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

                    # 1. Nếu bảng nhỏ hoặc vừa (<= 60 dòng), index toàn bộ bảng dưới dạng Markdown
                    if 0 < len(rows) <= 60:
                        table_md = "| " + " | ".join(headers) + " |\n"
                        table_md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                        for r in rows:
                            if any(r):
                                # Làm sạch ngắt dòng trong ô nếu có
                                cleaned_cells = [c.replace("\n", " ").strip() for c in r]
                                table_md += "| " + " | ".join(cleaned_cells) + " |\n"
                        self.chunks.append(
                            DocumentChunk(
                                file_path=rel_path,
                                category=category,
                                title=f"{f.name} - Toàn bộ bảng quy chuẩn ({len(rows)} mục)",
                                content=table_md[:4000],
                                metadata={"filename": f.name, "type": "full_table", "row_count": len(rows)}
                            )
                        )

                    # 2. Gom các dòng riêng lẻ thành đoạn tài liệu chi tiết
                    for idx, row in enumerate(rows):
                        if not any(row):
                            continue
                        row_desc = " | ".join(f"{h}: {v}" for h, v in zip(headers, row, strict=False) if v)
                        self.chunks.append(
                            DocumentChunk(
                                file_path=rel_path,
                                category=category,
                                title=f"{f.name} (Dòng {idx+1})",
                                content=row_desc,
                                metadata={"filename": f.name, "row_idx": idx+1, "headers": headers, "values": row}
                            )
                        )
            except Exception:
                pass

    def search(self, query: str, top_k: int = 5, category_filter: str | None = None) -> list[dict[str, Any]]:
        """Lục tìm tài liệu và dữ liệu khớp nhất với câu hỏi ngôn ngữ tự nhiên."""
        if not self.bm25 or not self.chunks:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)
        scored_chunks: list[tuple[float, DocumentChunk]] = []

        q_norm = _normalize(query)
        for i, score in enumerate(scores):
            chunk = self.chunks[i]
            if category_filter and chunk.category != category_filter:
                continue

            final_score = float(score)
            # Boost nếu từ khóa xuất hiện chính xác trong title
            if any(t in _normalize(chunk.title) for t in tokens):
                final_score += 3.0
            # Boost nếu khớp chuỗi con
            if any(len(t) > 3 and t in _normalize(chunk.content) for t in tokens):
                final_score += 1.5

            if final_score > 0.5:
                scored_chunks.append((final_score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        results = []
        for s, c in scored_chunks[:top_k]:
            results.append({
                "score": round(s, 2),
                "file_path": c.file_path,
                "category": c.category,
                "title": c.title,
                "content": c.content,
                "metadata": c.metadata
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
