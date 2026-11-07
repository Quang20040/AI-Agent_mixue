# Xếp hạng tra cứu SOP bằng mô hình học (learning-to-rank)

## Vấn đề
Tra cứu SOP/công thức cũ cộng các tín hiệu (BM25, TF-IDF cosine, 3-gram ký tự, độ phủ từ, luật ý định)
bằng **trọng số chỉnh tay**, và từ chối câu ngoài phạm vi bằng **danh sách từ viết tay** (bánh bao, pizza, KFC…).
Trên bộ 30 câu dùng để chỉnh, nó đạt Hit@1 91,7% và từ chối 100%. Trên **70 câu hỏi mới viết sau**
(`tests/fixtures/sop_retrieval_heldout.json`: diễn đạt khác, không dấu, gõ sai, 10 câu ngoài phạm vi mới),
nó chỉ còn Hit@1 65% và **từ chối đúng 1/10** câu ngoài phạm vi — dấu hiệu quá khớp (overfitting) với bộ chỉnh tay.

## Cách làm
* Mỗi cặp (câu hỏi, đoạn tài liệu) → 16 đặc trưng (cùng các tín hiệu trên, ở dạng thô) + tùy chọn 1 đặc trưng
  ngữ nghĩa: khoảng cách cosine giữa vector câu hỏi và vector đoạn (Gemini embedding), tính tương đối so với
  đoạn gần nhất của câu hỏi.
* Nhãn: đoạn trả lời đúng câu hỏi (cùng quy tắc với bộ chấm `src/engine/sop_evaluation.py`).
* Mô hình: **tuyến tính listwise (ListNet top-1)** — softmax trên các ứng viên của một câu hỏi phải dồn xác suất
  vào đáp án đúng; huấn luyện bằng gradient descent (numpy), chuẩn hóa đặc trưng, L2.
* Ngưỡng từ chối: chọn trên câu hỏi huấn luyện (điểm đoạn đứng đầu thấp hơn ngưỡng ⇒ trả lời "không có").
  Không còn danh sách từ cấm.
* Đánh giá: **cross-validation 5-fold theo câu hỏi, lặp 10 lần** trên 100 câu (84 câu có đáp án, 16 câu ngoài phạm vi);
  một câu hỏi không bao giờ nằm cùng lúc ở tập huấn luyện và tập kiểm tra.
* Chạy app: chỉ đọc trọng số JSON (`src/agent/multi_agent/sop_ranker.json`), không cần scikit-learn/torch;
  ~100 ms/câu. Mô hình chỉ dùng khi tài liệu trùng với tài liệu lúc huấn luyện (dấu vân tay corpus);
  `SOP_RANKER=heuristic` quay về trọng số chỉnh tay.

## Kết quả (`python scripts/train_sop_ranker.py`)
| Bộ xếp hạng | Hit@1 | Hit@3 | MRR | Từ chối đúng câu ngoài phạm vi |
|---|---|---|---|---|
| Chỉnh tay, trên 70 câu mới | 65,0% | 78,3% | 0,727 | 10% |
| Chỉnh tay, trên cả 100 câu (gồm 30 câu nó được chỉnh theo) | 72,6% | 83,3% | 0,786 | 43,8% |
| **Học từ dữ liệu, 16 đặc trưng** (CV 5×10) | 70,2 ± 1,5% | 80,4 ± 1,9% | 0,760 | **93,8 ± 7,4%** |
| Học + vector ngữ nghĩa (thử bằng multilingual-e5-base, CV 5×5) | 77,6 ± 1,2% | 86,9 ± 1,7% | — | 90,0 ± 3,1% |

Thí nghiệm phụ (vector đơn thuần, không kết hợp): e5-small Hit@1 57%, e5-base 45%, MiniLM 27% — vector
một mình kém hơn tìm theo từ khóa trên tài liệu chuyên ngành ngắn; giá trị nằm ở **kết hợp có học trọng số**.

Hạn chế: chỉ 100 câu hỏi do một người viết; train riêng trên 30 câu cũ rồi thử 70 câu mới cho Hit@1 41,7%
(quá ít dữ liệu để học ngưỡng). Cần thêm câu hỏi thật của nhân viên để mô hình ổn định hơn.

## Vector ngữ nghĩa trong bản chạy thật
`scripts/build_sop_embeddings.py` (workflow **SOP embeddings**, cần secret `GEMINI_API_KEY`) nhúng ~430 đoạn
SOP/công thức/quy định — không nhúng các dòng nhật ký bán hàng, nhập hàng, kiểm kê — rồi huấn luyện lại cả hai
biến thể. Khi chạy, chỉ câu hỏi được gửi đi nhúng (một lời gọi nhỏ, có cache); AI tắt, không cho gửi dữ liệu,
hết hạn mức hoặc quá 4 giây thì tự dùng biến thể không vector.
