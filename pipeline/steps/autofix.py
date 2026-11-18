"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _fmt(v):
    return f"{v:.6f}".rstrip("0").rstrip(".") or "0"


def _clip(text):
    """Cắt box về [0,1]. Trả về dòng mới, hoặc None nếu sau khi cắt box không còn diện tích."""
    c, cx, cy, w, h = parse_yolo_line(text)
    x1, x2 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    y1, y2 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    return " ".join([str(c), _fmt((x1 + x2) / 2), _fmt((y1 + y2) / 2), _fmt(x2 - x1), _fmt(y2 - y1)])


def _remove_image(ds, stem):
    """Xoá mọi ảnh có stem này + file nhãn của nó. Trả về True nếu có xoá gì."""
    removed = False
    for p in ds.image_files():
        if p.stem == stem:
            p.unlink()
            removed = True
    lp = ds.label_path(stem)
    if lp.exists():
        lp.unlink()
        removed = True
    return removed


def _rename_classes(ds, cfg):
    if not ds.yaml_path.exists():
        return None
    data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
    before = data.get("names")
    want = {i: n for i, n in enumerate(cfg["classes"])}
    if before == want or before == list(cfg["classes"]):
        return None
    data["names"] = want
    data["nc"] = len(want)
    ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"image": "data.yaml", "line": None, "action": "rename_classes", "before": str(before), "after": str(want)}


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]     # không bao giờ đụng tới WARN
    fixes = []

    # 1) Xoá ảnh trước: issue dòng của ảnh đã xoá sẽ được bỏ qua êm.
    removed = set()
    for stem in sorted({i.image for i in errors if i.code in REMOVE_CODES}):
        if _remove_image(ds, stem):
            codes = sorted({i.code for i in errors if i.image == stem and i.code in REMOVE_CODES})
            fixes.append({"image": stem, "line": None, "action": "remove_image",
                          "before": ",".join(codes), "after": "(đã xoá ảnh + nhãn)"})
        removed.add(stem)

    # 2) data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        f = _rename_classes(ds, cfg)
        if f:
            fixes.append(f)

    # 3) Ảnh thiếu file nhãn: không bịa nhãn, chỉ chuyển người gán.
    for stem in sorted({i.image for i in errors if i.code == "MISSING_LABEL_FILE"} - removed):
        if not ds.label_path(stem).exists():
            fixes.append({"image": stem, "line": None, "action": "needs_label",
                          "before": "(không có file)", "after": "chuyển người gán"})

    # 4) Lỗi theo dòng: gom theo file, quyết định cho từng dòng GỐC, ghi lại file MỘT lần.
    by_file = defaultdict(lambda: defaultdict(set))           # stem -> line_no -> {codes}
    for i in errors:
        if i.line is not None and i.code in DROP_CODES | CLIP_CODES and i.image not in removed:
            by_file[i.image][i.line].add(i.code)

    for stem in sorted(by_file):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines = []
        changed = False
        for no, text in enumerate(raw_lines, 1):                # đếm cả dòng trống -> khớp số dòng gốc
            codes = by_file[stem].get(no)
            if not codes or not text.strip():
                new_lines.append(text)
                continue
            if codes & DROP_CODES:                              # xoá thắng cắt
                fixes.append({"image": stem, "line": no, "action": "drop_line", "before": text, "after": ""})
                changed = True
                continue
            try:
                clipped = _clip(text)
            except ValueError:                                  # dòng không parse được: an toàn nhất là xoá
                clipped = None
            if clipped is None:
                fixes.append({"image": stem, "line": no, "action": "drop_line", "before": text,
                              "after": "(box nằm ngoài ảnh)"})
            else:
                fixes.append({"image": stem, "line": no, "action": "clip_box", "before": text, "after": clipped})
                new_lines.append(clipped)
            changed = True
        if changed:
            lp.write_text("".join(l + "\n" for l in new_lines), encoding="utf-8")

    return fixes
