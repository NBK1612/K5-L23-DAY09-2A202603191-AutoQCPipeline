# Báo cáo Day 09 — Nguyễn Bảo Khánh, 2A202603191

## 1. Kết luận trước
**Hold** (mã thoát 10). Vào **224** ảnh, cửa vào loại **22**, còn **202** ảnh được xuất ra `submission/export/clean_v1` dưới dạng **bản nháp, chưa phát hành**.
Không còn lỗi bắt buộc nào (`07_error_list_v3`: 0 ERROR). Tuy vậy **38/202 ảnh (18,8%)** vẫn còn cảnh báo mà người chưa duyệt, vượt ngưỡng 10%: hàng đợi có 125 ảnh nhưng ngân sách duyệt chỉ 80 ảnh.

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (tính trên 224 ảnh ở cửa vào, 202 ảnh ở QC nhãn) và `03_fixes.csv` (35 thay đổi).

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| DUP_IMAGE_EXACT | 8 ảnh / 224 | máy (loại ở cửa vào) | trùng từng byte (md5), chắc chắn |
| DUP_IMAGE_NEAR | 4 ảnh / 224 | máy (loại) | phash ≤ 12 (2 cặp phash 0, 2 cặp d=6/10 đã mở xem: trùng thật) |
| LEAK_TEST | 5 ảnh / 224 | máy (loại) | trùng ảnh test → nếu giữ thì làm phồng điểm test |
| BAD_SIZE / CORRUPT_IMAGE | 3 / 2 ảnh | máy (loại) | cạnh < 250px / không mở được |
| BAD_CLASS_ID, BAD_FORMAT, BOX_ZERO, DUP_BOX | 6 / 3 / 4 / 7 dòng | máy: `drop_line` (20 dòng) | sai cú pháp, không thể đoán ý định → xoá dòng, ghi log |
| BOX_OUT_OF_IMAGE | 8 dòng / 8 ảnh | máy: `clip_box` (8) | cắt về [0,1], giữ lớp; ảnh vẫn vào hàng đợi (FIXED_CLIP_BOX) để người xem lại |
| BAD_CLASS_NAME | 2 tên (data.yaml) | máy: `rename_classes` | viết hoa sai, có danh sách chuẩn trong cfg |
| MISSING_LABEL_FILE | 6 ảnh | **người** (`needs_label`) | máy không bịa nhãn; người gán cả 6 ảnh (đầu hàng đợi) |
| POSSIBLE_MISSING | 53 dòng / 52 ảnh | **người** | ý kiến của yolo26l: chỉ cảnh báo |
| POSSIBLE_WRONG_CLASS | 18 / 18 ảnh | **người** | car↔truck↔bus: cần người hiểu ngữ nghĩa |
| POSSIBLE_LOOSE_BOX | 28 / 24 ảnh | **người** | box lỏng hoặc lệch |
| POSSIBLE_FALSE_POS | 29 / 27 ảnh | **người** | box nhãn không khớp vật nào model thấy |
| EMPTY_LABEL, BOX_TINY, BOX_HUGE, CLASS_RARE | 12 / 6 / 3 / 4 | **người** | có thể là ảnh nền hoặc vật nhỏ hợp lệ, máy không quyết được |

**Hàng đợi (`05_review_queue.csv`, 125 ảnh).** Ảnh được xếp theo tổng trọng số cảnh báo × (1 + conf):
- `NEEDS_LABEL` có trọng số 10 nên 6 ảnh thiếu nhãn đứng gần đầu, vì đây là lỗi bắt buộc mà chỉ người sửa được.
- Kế đến là `POSSIBLE_WRONG_CLASS` (trọng số 3) và `POSSIBLE_MISSING` (trọng số 2).
- Ảnh đứng đầu là img_0020 (11,5 điểm, gồm FIXED_DROP_LINE + MISSING + WRONG_CLASS). Đây cũng chính là ảnh tôi tự thấy lỗi ở Bước 1.

**Ngân sách 80 ảnh** phủ được:
- 74/80 ảnh có cảnh báo ngữ nghĩa, trong đó có **18/18 ảnh WRONG_CLASS** và **50/52 ảnh MISSING**.
- 45 ảnh **không được duyệt** có điểm thấp (≤ 3,33), phần lớn là LOOSE_BOX (16) và FALSE_POS (11).
- Sau khi duyệt, `07_error_list_v3` chỉ còn 13 MISSING, 3 WRONG_CLASS, 20 LOOSE_BOX, 21 FALSE_POS.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | DUP_NEAR 1.00/0.50 → 1.00/0.67 (EXACT giữ 1.00/1.00) | Trên calib, recall đứng yên từ 4 đến 14, lên 16 mới đạt 0.83. Trên raw, 12 là mức lớn nhất mà **mọi** cặp bị bắt đều là trùng thật (đã mở xem): bắt thêm img_0101 (rò rỉ test_039), img_0223 (d=6), img_0186 (d=10). Lên 16 thì precision trên raw sập (xem dưới). |
| `second_opinion.conf` | 0.25 | **0.6** | WRONG_CLASS 0.56/0.83 → 0.62/0.83; MISSING 0.50/1.00 → 0.57/1.00; LOOSE_BOX 0.29/0.40 → 0.20/0.20 | Tăng precision mà **giữ recall MISSING = 1.00**. Ở 0.7–0.8, MISSING tụt còn 0.88–0.75 (bỏ sót vật thiếu nhãn), dù 0.8 cho WRONG_CLASS precision 1.00 và kết luận Release. Tôi không chọn 0.8 vì như vậy là chỉnh ngưỡng để "đạt" Release, đổi lấy việc bỏ sót nhãn. Cái giá: LOOSE_BOX recall giảm (1/5). Trên raw, hàng đợi giảm từ 145 → 125 ảnh. |

**Calibration có thể đánh lừa:** trên calib, `phash_dist=16` cho F1 DUP_NEAR **cao nhất (0.91)**. Nhưng trên raw:
- Số ảnh bị loại nhảy từ **22 → 31**.
- Tôi mở xem 9 cặp mới: **8/9 cặp là hai ảnh khác nhau**, trong đó có 6 "LEAK_TEST" giả (img_0013, 0017, 0021, 0033, 0038, 0115 bị ghép sai với ảnh test) và 2 cặp DUP giả. Chỉ 1 cặp là trùng thật (img_0084~img_0074, d=16).
- Calib chỉ có 6 ca DUP_NEAR trên 39 ảnh, phân bố khác raw, nên một ngưỡng "khớp calib" lại vứt bỏ 8 ảnh tốt của raw.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`:
- Kết luận **Rework** với **mã thoát 20**, lý do "còn 6 lỗi bắt buộc (MISSING_LABEL_FILE)". 6 ảnh thiếu nhãn này không có người gán.
- Log ghi "KHÔNG xuất: còn lỗi bắt buộc (Rework)", và thư mục `work/exp_nb` **không được tạo**.
- So với lần chạy chính (ngân sách 80): người gán đủ 6 ảnh, nên kết luận hạ xuống Hold.
- `gate` đếm lỗi ERROR kể cả ở ảnh đã duyệt, nên duyệt không thể "che" lỗi bắt buộc.

**(b) Điểm mù (có bằng chứng):**
1. **Nhầm lớp mà pipeline không gọi đúng tên.** Ở img_0045, tôi tự thấy một người phụ nữ bị gán `car`. Pipeline chỉ báo `POSSIBLE_LOOSE_BOX` (IoU 0.33), không báo WRONG_CLASS, và ảnh đứng hạng 92/125 nên **không được duyệt** trong ngân sách 80.
2. **Ảnh trùng biến đổi mạnh.** img_0084 và img_0074 là cùng một ảnh (tôi đã mở xem) nhưng phash cách nhau 16 > 12, nên cả hai **lọt** vào dataset. Muốn bắt thì phải nâng ngưỡng lên 16, mà như thế lại loại sai 8 ảnh.
3. **Box lỏng nhẹ / box sai vị trí.** Ở img_0020, box person đánh sai. Pipeline bắt được (MISSING + WRONG_CLASS, hạng 1). Nhưng nói chung LOOSE_BOX chỉ có recall 0.20 trên calib, nên phần lớn box lỏng nhẹ sẽ không bị cờ.
4. **Model lớn nhầm giống người gán.** Ở img_0100, tôi tự thấy 2 box ở mép trái (dòng 4) và mép phải (dòng 2) đều gán `person` nhưng không phải người.
   - Pipeline chỉ cờ **dòng 4** (`POSSIBLE_FALSE_POS`, IoU 0.03).
   - **Dòng 2 không bị cờ gì**, vì yolo26l cũng dự đoán person ở đó, nên `second_opinion` coi là "đồng ý".
   - Ảnh này vẫn được duyệt (hạng 45 ≤ 80) chỉ nhờ dòng 4. Nếu chỉ có lỗi như dòng 2, ảnh sẽ không vào hàng đợi.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Thiết lập:** Google Colab T4, `yolo26n.pt`, 20 epoch, imgsz 640, batch 16, seed 0 và 1. Hai biến thể dùng cùng val (`gold_val`, 40 ảnh) và cùng test (100 ảnh). Nguồn: `submission/results/comparison.md`, sinh bởi `summarize_results.py`.

| biến thể | #ảnh train | số seed | mAP50 (TB ± độ lệch) | mAP50-95 | precision | recall |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

AP50 theo lớp, trung bình 2 seed (raw → clean):

| lớp | raw | clean |
|---|---|---|
| car | 0.74 | 0.74 |
| person | 0.82 | 0.82 |
| bus | 0.69 | 0.70 |
| truck | 0.65 | **0.54** |

**Kết luận trung thực: chưa kết luận được.**
- Chênh mAP50 (clean − raw) = **−0.025**, đúng bằng độ lệch giữa 2 seed của clean (0.718 và 0.683 → ±0.025).
- Với 2 seed và test 100 ảnh, chênh lệch này **nằm trong nhiễu**. Không nói được clean tốt hơn, cũng không nói được clean tệ hơn.
- Phần chênh tập trung gần hết ở lớp **truck**, lớp có ít box nhất (41 box trong clean), và AP truck của clean dao động mạnh giữa 2 seed (0.59 và 0.49).

**Giả thuyết và cách kiểm:**
1. **Rò rỉ test làm phồng điểm raw.**
   - `raw` train trên cả **5 ảnh trùng tập test** mà pipeline đã loại (`LEAK_TEST`: img_0049, 0101, 0167, 0174, 0221), thêm 12 ảnh trùng nhau.
   - Model raw đã "thấy" 5/100 ảnh test.
   - *Kiểm:* đánh giá lại cả hai model trên test **bỏ 5 ảnh** test_009, 033, 039, 044, 085. Nếu khoảng cách thu hẹp hoặc đảo chiều thì điểm raw đang bị thổi phồng.
2. **Clean ít dữ liệu hơn, và nhãn vẫn chưa sạch hẳn.**
   - Clean có ít hơn 22 ảnh (−10%).
   - Clean vẫn còn **38 ảnh có cảnh báo chưa duyệt** (Hold), ví dụ img_0069 có cột đèn và biển báo gán `person`, img_0045 có người gán `car`.
   - Người duyệt đã đổi lớp nhiều box: truck tăng từ 32 lên 41 box. Model 20 epoch có thể chưa học kịp nhãn mới.
   - *Kiểm:* chạy thêm biến thể `oracle` (nhãn người, chặn trên) và ≥ 3 seed; xem AP truck có ổn định không.
3. **Test nhỏ, lớp hiếm.** Test chỉ có 100 ảnh, truck/bus có ít ví dụ, nên mỗi box đúng hay sai làm AP lớp nhảy vài điểm.
   - *Kiểm:* thêm seed, báo khoảng tin cậy (bootstrap trên ảnh test).

**Việc tiếp theo:**
- duyệt nốt 45 ảnh còn lại trong hàng đợi;
- train lại với ≥ 3 seed và thêm biến thể `oracle`;
- đánh giá trên test đã bỏ 5 ảnh rò rỉ.

## 6. Quyết định và ghi chú AI
**(a) Quyết định: Hold.** Không phát hành `clean_v1`. Điều kiện để chuyển sang **Release**: số ảnh còn cảnh báo chưa duyệt phải < 10%, tức ≤ 20/202 ảnh.
- Cần duyệt thêm **≥ 18 ảnh** trong 45 ảnh còn lại của hàng đợi (hạng 81–125, chủ yếu LOOSE_BOX/FALSE_POS) ở một đợt duyệt sau. Hoặc dự án tăng ngân sách duyệt.
- Không đổi ngưỡng gate hay `conf` chỉ để đạt Release.
- Nếu có ảnh nào lại thiếu nhãn thì kết luận phải là Rework.

**(b) Có dùng AI (Claude Code) để viết 4 module.**
- *Prompt chính:* đọc docstring của stub và file test tương ứng, viết hàm đúng đặc tả đầu vào/đầu ra, đọc mọi ngưỡng từ `cfg`, không sửa `data/raw`.
- *Cách kiểm:*
  - chạy `pytest` từng file rồi toàn bộ: 79/79 xanh;
  - đọc lại từng dòng;
  - chạy `make run` và đối chiếu `02_error_list_v1` với ảnh `viz_labels.py`, thấy img_0020 bị cờ đúng như tôi tự nhìn;
  - chạy `--budget 0` để kiểm gate;
  - mở xem các cặp ảnh trùng trước khi chốt ngưỡng.
- *Một lần AI sai:* AI đề xuất cài thư viện và in báo cáo mà không đặt `PYTHONUTF8=1`. Trên Windows (cp1252), `pip install -r requirements.txt` chết vì comment tiếng Việt, và script in tiếng Việt bị `UnicodeEncodeError`. Phải đặt `PYTHONUTF8=1` mới chạy được.

**(c) Thưởng CVAT: lọc box nhỏ.** Tôi tạo project trên app.cvat.ai bằng `cvat/labels.json`. CVAT bản mới từ chối `"values": []` của thuộc tính checkbox, nên phải sửa thành `["false"]`.

- **Task:** 20 ảnh lấy từ `work/run/ds` (12 ảnh có box nhỏ và 8 ảnh đầu `05_review_queue`), import nhãn YOLO 1.1.
- **Lọc:** `width < 20` khớp **13 ảnh, 31 box**: img_0005 (1), 0007 (1), 0020 (3), 0022 (2), 0026 (6), 0030 (3), 0048 (2), 0051 (3), 0053 (1), 0067 (1), 0069 (2), 0117 (4), 0135 (2).
- **Ảnh chụp bộ lọc và kết quả lọc:** [1](bonus/cvat_filter_1.png) · [2](bonus/cvat_filter_2.png) · [3](bonus/cvat_filter_3.png) · [4](bonus/cvat_filter_4.png) · [5](bonus/cvat_filter_5.png) · [6](bonus/cvat_filter_6.png)
- **Đối chiếu `BOX_TINY` của pipeline:** pipeline dùng ngưỡng **cạnh ngắn < 12 px**, còn slide/CVAT dùng **width < 20 px**. Trong 13 ảnh này, pipeline chỉ báo `BOX_TINY` ở **3 ảnh** (img_0026, 0051, 0069), mỗi ảnh 1 box. 28 box còn lại rộng 12–20 px nên lọt ngưỡng 12. Ngưỡng 20 bắt rộng hơn nhưng cũng nhiều box hợp lệ hơn, ví dụ người ở xa.
- **Khi xem bằng mắt, CVAT cho thấy điều pipeline chưa xử lý:**
  - **img_0069:** 2 box `person` thực ra là **cột đèn và biển báo**. Pipeline có cờ `POSSIBLE_FALSE_POS` và `BOX_TINY`, nhưng ảnh không được duyệt (ngoài ngân sách 80), nên 2 box sai này **vẫn nằm trong `clean_v1`**.
  - **img_0022:** 1 người là **ảnh phản chiếu qua gương**.
  - **img_0053:** 1 box là **người trong một bức ảnh hoặc tranh**.
  - Hai ảnh 0022 và 0053 đã được người duyệt. Đây là ca **mơ hồ theo guideline** (có gán không?), máy không quyết được.
- **`can_review`:** người gán bật thuộc tính này cho những box mình **không chắc** (phản chiếu, người trong ảnh, vật bị che hoặc quá nhỏ), để người kiểm xem lại. Trên task này, mọi box đều mang giá trị mặc định false, vì định dạng YOLO 1.1 không lưu thuộc tính nên nhãn import không có thông tin này. Pipeline dùng thông tin tương tự ở các **cảnh báo WARN** (`POSSIBLE_*`, `BOX_TINY`) và ở `05_review_queue.csv`: đẩy ca nghi ngờ cho người thay vì tự sửa.

*Ghi chú:* `check_submission.py` trên Windows báo nhầm `pipeline\calibrate.py` (file viết sẵn, đã được ghim). Nguyên nhân là đường dẫn dùng `\` không khớp với `pipeline/calibrate.py` trong `_protected.json`. Trên Linux thì không báo.

## Thưởng: check mới `BOX_ASPECT`
**Check gồm:**
- **Code:** `pipeline/checks/box_aspect.py`
- **Test:** `tests/test_box_aspect.py`, 7 test xanh.
- **Quy tắc (WARN, theo lớp, tính bằng pixel):**
  - `person` mà box **dẹt ngang**, w/h > 2.5.
  - `car/truck/bus` mà box **cao-hẹp**, h/w > 2.5.
- **Vì sao theo lớp:** trên raw, 99% box có tỉ lệ ≤ 5.9, và mọi box cực đoan đều là person đứng (w/h tới 0.1). Một ngưỡng chung sẽ báo nhầm hàng loạt người đứng.

**Hạn chế:**
- `QC_CHECKS` nằm trong file ghim, nên check **chạy riêng**, không nằm trong `make run`: `python -m pipeline.checks.box_aspect data/raw --out submission/bonus/box_aspect_raw.csv`
- Config cũng bị ghim, nên ngưỡng nằm trong `DEFAULTS` của module. Nếu có `cfg["box_aspect"]` thì code đọc từ đó.

**Kết quả trên raw:** 12 cảnh báo. Tôi mở xem từng box (`submission/bonus/box_aspect_review.csv`), **7/12 là lỗi thật (precision 0.58)**.

| Nhánh quy tắc | Cảnh báo | Lỗi thật | Ví dụ |
|---|---:|---:|---|
| xe cao-hẹp | 9 | **7** | 5 người gán thành `car`; 1 biển báo gán `car` (img_0024); 1 mặt đường gán `bus` (img_0180) |
| person dẹt ngang | 3 | 0 | img_0148, img_0159 ×2: đúng là người (ngồi, nằm, bị che) |

**Đánh giá trung thực:**
- Cả 7 lỗi thật **đều đã bị `second_opinion` cờ** (5 `POSSIBLE_WRONG_CLASS`, 2 `POSSIBLE_FALSE_POS`). Trên lô này, `BOX_ASPECT` **không bắt thêm lỗi mới**.
- 3 box mà chỉ check này cờ (img_0073, 0133, 0148) đều là báo nhầm.
- Giá trị của check:
  - **xác nhận độc lập** với model, không cần GPU hay dự đoán;
  - 7 lỗi thật đều được 2 check cùng chỉ vào, nên có thể dùng để **tăng ưu tiên** trong hàng đợi.
  - Không thay được người: img_0045 (người gán `car`, mục 4) có box không đủ cao-hẹp nên cả hai check đều không gọi đúng tên lỗi.
- Việc tiếp theo: bỏ nhánh "person dẹt ngang" (0/3), chỉ giữ nhánh xe (7/9 ≈ 0.78), rồi kiểm lại trên một lô khác trước khi đưa vào pipeline.
