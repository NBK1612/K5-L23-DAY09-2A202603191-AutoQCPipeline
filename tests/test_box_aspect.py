"""Test cho check thưởng BOX_ASPECT (pipeline/checks/box_aspect.py). Ảnh giả 640x480."""
from pipeline.checks import box_aspect


def run(make_ds, cfg, lines, size=(640, 480)):
    ds = make_ds(images={"a": 1}, labels={"a": lines}, size=size)
    return [(i.code, i.line, i.severity) for i in box_aspect.run(ds, cfg)]


def test_normal_boxes_are_silent(make_ds, cfg):
    # person đứng cao-hẹp (64x288 px, h/w 4.5) và car dẹt ngang (320x96 px, w/h 3.3): đều bình thường
    assert run(make_ds, cfg, ["1 0.5 0.5 0.1 0.6", "0 0.5 0.5 0.5 0.2"]) == []


def test_tall_vehicle_is_flagged(make_ds, cfg):
    # car 32x192 px: h/w = 6 > 2.5 -> nghi là người gán nhầm thành xe
    assert run(make_ds, cfg, ["0 0.5 0.5 0.05 0.4"]) == [("BOX_ASPECT", 1, "warn")]


def test_flat_person_is_flagged(make_ds, cfg):
    # person 320x48 px: w/h = 6.7 > 2.5
    assert run(make_ds, cfg, ["1 0.5 0.5 0.5 0.1"]) == [("BOX_ASPECT", 1, "warn")]


def test_ratio_is_in_pixels_not_normalized(make_ds, cfg):
    # w=h=0.3 chuẩn hoá nhưng ảnh 1200x200 -> 360x60 px: person dẹt 6.0 -> báo; trong ảnh vuông thì không
    assert run(make_ds, cfg, ["1 0.5 0.5 0.3 0.3"], size=(1200, 200)) == [("BOX_ASPECT", 1, "warn")]
    assert run(make_ds, cfg, ["1 0.5 0.5 0.3 0.3"], size=(400, 400)) == []


def test_threshold_from_config(make_ds, cfg):
    cfg["box_aspect"] = {"max_ratio": 10}
    assert run(make_ds, cfg, ["0 0.5 0.5 0.05 0.4"]) == []


def test_bad_lines_are_skipped_and_line_numbers_kept(make_ds, cfg):
    ds = make_ds(images={"a": 1})
    (ds.labels_dir / "a.txt").write_text("garbage\n\n93 0.5 0.5 0.05 0.4\n0 0.5 0.5 0 0.4\n2 0.5 0.5 0.05 0.4\n")
    assert [(i.code, i.line) for i in box_aspect.run(ds, cfg)] == [("BOX_ASPECT", 5)]


def test_corrupt_image_is_skipped(make_ds, cfg):
    ds = make_ds(images={"a": b"not an image"}, labels={"a": ["0 0.5 0.5 0.05 0.4"]})
    assert box_aspect.run(ds, cfg) == []
