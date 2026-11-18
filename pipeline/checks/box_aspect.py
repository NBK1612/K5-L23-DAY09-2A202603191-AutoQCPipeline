"""CHECK THƯỞNG — BOX_ASPECT: box có tỉ lệ khung hình "ngược" với lớp được gán.   (bonus +3)

Test:  pytest tests/test_box_aspect.py -q
Chạy riêng (không nằm trong QC_CHECKS vì `pipeline/checks/__init__.py` là file ghim):
    python -m pipeline.checks.box_aspect data/raw --out submission/bonus/box_aspect_raw.csv

Ý tưởng (từ phân bố tỉ lệ w/h tính bằng PIXEL trên lô raw):
- `person` đứng: box cao-hẹp là bình thường (w/h xuống tới 0.1). Box person DẸT NGANG (w/h > max_ratio) đáng ngờ:
  người nằm? hay một chiếc xe bị gán nhầm thành person?
- Xe (`car`, `truck`, `bus`): box dẹt là bình thường. Box CAO-HẸP (h/w > max_ratio) đáng ngờ:
  thường là một người bị gán nhầm thành xe, hoặc box vẽ hỏng.
Một tỉ lệ chung cho mọi lớp sẽ báo nhầm hàng loạt người đứng (99% box raw có tỉ lệ ≤ 5.9, toàn là person).

| code       | severity | khi nào                                                                          |
|------------|----------|----------------------------------------------------------------------------------|
| BOX_ASPECT | WARN     | lớp trong `tall_classes` mà w/h > max_ratio, hoặc lớp khác mà h/w > max_ratio     |

Chỉ CẢNH BÁO (người xem): một chiếc xe nhìn thẳng từ đầu xe vẫn có thể cao-hẹp. Ngưỡng đọc từ
`cfg["box_aspect"]` nếu có; `configs/pipeline.yaml` bị ghim (không được thêm khoá) nên dùng giá trị mặc định DEFAULTS.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ..common import WARN, Issue, parse_yolo_line

NAME = "box_aspect"
DEFAULTS = {"max_ratio": 2.5, "tall_classes": ["person"]}


def _params(cfg):
    p = dict(DEFAULTS)
    p.update((cfg or {}).get("box_aspect") or {})
    return p


def run(ds, cfg):
    p = _params(cfg)
    max_ratio = float(p["max_ratio"])
    tall = set(p["tall_classes"])
    issues = []
    for lp in ds.label_files():
        stem = lp.stem
        size = ds.image_size(stem)
        if not size:
            continue
        W, H = size
        for no, text in ds.read_label_lines(stem) or []:
            try:
                c, _, _, w, h = parse_yolo_line(text)
            except ValueError:
                continue                                   # label_format báo BAD_FORMAT
            if not 0 <= c < len(ds.classes) or w <= 0 or h <= 0:
                continue                                   # label_format báo BAD_CLASS_ID / BOX_ZERO
            wp, hp = w * W, h * H
            name = ds.classes[c]
            if name in tall:
                ratio, shape = wp / hp, "dẹt ngang"
            else:
                ratio, shape = hp / wp, "cao-hẹp"
            if ratio > max_ratio:
                issues.append(Issue(NAME, WARN, "BOX_ASPECT", stem,
                                    f"box {name} {shape} bất thường (tỉ lệ {ratio:.2f} > {max_ratio}, {wp:.0f}x{hp:.0f}px)",
                                    no, {"ratio": round(ratio, 2), "class": name}))
    return issues


def main(argv=None):
    from ..common import Dataset, load_config, write_issues_csv
    ap = argparse.ArgumentParser(description="Chạy riêng check BOX_ASPECT trên một thư mục dataset YOLO (chỉ đọc).")
    ap.add_argument("root", help="thư mục có images/ và labels/, vd. data/raw")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None, help="ghi CSV (tuỳ chọn)")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    ds = Dataset(a.root, cfg["classes"])
    issues = run(ds, cfg)
    print(f"đã quét {len(ds.label_files())} file nhãn trong {a.root}: {len(issues)} cảnh báo BOX_ASPECT")
    for i in issues:
        print(f"  [{i.severity.upper()}] {i.code} {i.image}:{i.line}  {i.message}")
    if a.out:
        write_issues_csv(issues, a.out)
        print(f"-> {Path(a.out)}")


if __name__ == "__main__":
    main()
