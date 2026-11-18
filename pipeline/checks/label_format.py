"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401

NAME = "label_format"


def _overflow(cx, cy, w, h):
    """Mức tràn lớn nhất ra ngoài [0,1] của 4 mép box (<= 0 nghĩa là nằm trong ảnh)."""
    return max(-(cx - w / 2), (cx + w / 2) - 1, -(cy - h / 2), (cy + h / 2) - 1)


def run(ds, cfg):
    p = cfg["label_format"]
    tol, min_px, max_frac, dup_iou = p["overflow_tol"], p["min_box_px"], p["max_box_frac"], p["dup_box_iou"]
    n_cls = len(ds.classes)
    issues = []

    for lp in ds.label_files():
        stem = lp.stem
        size = None
        size_loaded = False
        seen = []                                   # (line_no, box) các dòng hợp lệ trước đó

        for line_no, text in ds.read_label_lines(stem) or []:   # dòng trống đã bị bỏ, số dòng giữ nguyên
            try:
                c, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue(NAME, ERROR, "BAD_FORMAT", stem, f"dòng không hợp lệ ({e}): {text.strip()!r}", line_no))
                continue
            if not 0 <= c < n_cls:
                issues.append(Issue(NAME, ERROR, "BAD_CLASS_ID", stem, f"id lớp {c} ngoài 0..{n_cls - 1}", line_no))
                continue
            if w <= 0 or h <= 0:
                issues.append(Issue(NAME, ERROR, "BOX_ZERO", stem, f"box rộng/cao <= 0 (w={w}, h={h})", line_no))
                continue

            over = _overflow(cx, cy, w, h)
            if over > tol:
                issues.append(Issue(NAME, ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {over:.4f}", line_no,
                                    {"overflow": round(over, 6)}))

            box = (cx, cy, w, h)
            for prev_no, (pc, pbox) in seen:
                if pc == c and iou_xywh(pbox, box) > dup_iou:
                    issues.append(Issue(NAME, ERROR, "DUP_BOX", stem, f"trùng box dòng {prev_no} (cùng lớp {c})", line_no,
                                        {"dup_of": prev_no}))
                    break
            seen.append((line_no, (c, box)))

            if not size_loaded:
                size, size_loaded = ds.image_size(stem), True
            if size:
                short_px = min(w * size[0], h * size[1])
                if short_px < min_px:
                    issues.append(Issue(NAME, WARN, "BOX_TINY", stem, f"cạnh ngắn {short_px:.1f}px < {min_px}px", line_no,
                                        {"short_px": round(short_px, 1)}))
            if w * h > max_frac:
                issues.append(Issue(NAME, WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.0%} ảnh", line_no))

    return issues
