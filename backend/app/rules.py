"""Shared simulation reference values. These are not equipment specifications."""
RULE_VERSION = "demo-risk-v2"
TEMPERATURE_THRESHOLD = 60
SOURCE_LABEL = "演示规则参考，不是设备规范或安全认证标准"


def reference(kind):
    definitions = {
        "temperature": (f"低于 {TEMPERATURE_THRESHOLD}℃未命中本演示规则；≥{TEMPERATURE_THRESHOLD}℃触发演示异常", "°C", ("lt", TEMPERATURE_THRESHOLD), ("gte", TEMPERATURE_THRESHOLD)),
        "smoke_alarm": ("0 表示模拟未触发，1 表示模拟告警；未触发不能排除现场风险", "", ("eq", 0), ("eq", 1)),
        "connectivity": ("1 表示模拟在线，0 表示模拟离线；在线不证明现场安全", "", ("eq", 1), ("eq", 0)),
        "camera_event": ("0 表示无模拟异常记录，1 表示有模拟异常记录；未进行视频识别", "", ("eq", 0), ("eq", 1)),
        "water_pressure": ("未配置参考范围，需核实设备规范与实际工况", "MPa", None, None),
        "battery": ("仅展示模拟电量，未配置执行安全阈值", "%", None, None),
    }
    label, unit, normal, warning = definitions.get(kind, ("未配置参考规则", "", None, None))
    return {"kind": kind, "rule_id": f"demo-{kind}", "rule_version": RULE_VERSION,
            "reference_label": label, "normal_condition": {"operator": normal[0], "value": normal[1]} if normal else None,
            "warning_condition": {"operator": warning[0], "value": warning[1]} if warning else None,
            "unit": unit, "source_kind": "demo_rule", "source_label": SOURCE_LABEL, "is_simulated": True}


def references_for(device_type):
    kinds = {"temperature": ["temperature"], "smoke": ["smoke_alarm"], "camera": ["connectivity", "camera_event"],
             "water_pressure": ["water_pressure"], "fire": ["water_pressure"],
             "drone": ["connectivity", "battery"], "robot": ["connectivity", "battery"]}.get(device_type, [])
    return [reference(kind) for kind in kinds]


def all_references():
    return [reference(kind) for kind in ["temperature", "smoke_alarm", "connectivity", "camera_event", "water_pressure", "battery"]]
