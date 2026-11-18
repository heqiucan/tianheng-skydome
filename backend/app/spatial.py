"""Normalized, illustrative geometry shared by the Day 2 and Day 4 demos."""
from math import hypot
from datetime import datetime, timezone


def offset_anchor(anchor, dx=0, dy=0, note="DEMO 布点，非学校真实部署"):
    if not anchor:
        return None
    return {"image_id": anchor["image_id"], "x": min(.98, max(.02, anchor["x"] + dx)),
            "y": min(.98, max(.02, anchor["y"] + dy)), "note": note}


def inspection_route(anchor, start=None, ground=False):
    start = start if start and start["image_id"] == anchor["image_id"] else offset_anchor(anchor, -.12, .12)
    offsets = [(-.075, .055), (.065, .075)] if ground else [(-.075, .055), (-.04, -.075), (.075, -.04), (.065, .075)]
    points = [start, *[offset_anchor(anchor, dx, dy) for dx, dy in offsets], anchor, start]
    return [{"x": point["x"], "y": point["y"]} for point in points]


def point_along_route(route, progress):
    if not route:
        return None
    if progress >= 100:
        return dict(route[-1])
    if progress <= 0:
        return dict(route[0])
    lengths = [hypot(b["x"] - a["x"], b["y"] - a["y"]) for a, b in zip(route, route[1:])]
    remaining = sum(lengths) * max(0, min(100, progress)) / 100
    for a, b, length in zip(route, route[1:], lengths):
        if remaining <= length and length:
            fraction = remaining / length
            return {"x": a["x"] + (b["x"] - a["x"]) * fraction,
                    "y": a["y"] + (b["y"] - a["y"]) * fraction}
        remaining -= length
    return dict(route[-1])


def advance_patrol(patrol, now=None):
    if patrol["status"] == "running":
        current = now or datetime.now(timezone.utc)
        started = datetime.fromisoformat(patrol["started_at"].replace("Z", "+00:00"))
        elapsed = (current - started).total_seconds()
        patrol["progress"] = round(min(100, max(0, elapsed / patrol["duration_seconds"] * 100)), 2)
        if patrol["progress"] >= 100:
            patrol["status"] = "completed"
            patrol["result"] = "DEMO 巡检完成：已沿确认路线完成动画并记录目标区域。未采集真实视频或遥测，不能据此判定风险已消除。"
    return patrol
