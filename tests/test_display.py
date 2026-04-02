from src.agent_tools.display import analyze_display


def test_analyze_display_ok():
    specs = {"DisplayCapabilities": [
        {"current_refresh_hz": 144, "max_refresh_hz": 144, "edid_declared_max_hz": None}
    ]}
    result = analyze_display(specs)
    assert result["status"] == "OK"
    assert result["current"] == 144


def test_analyze_display_warning_mismatch():
    specs = {"DisplayCapabilities": [
        {"current_refresh_hz": 60, "max_refresh_hz": 144, "edid_declared_max_hz": None}
    ]}
    result = analyze_display(specs)
    assert result["status"] == "WARNING"
    assert result["can_auto_fix"] is True
    assert result["expected"] == 144


def test_analyze_display_missing_capabilities():
    specs = {"DisplayCapabilities": []}
    result = analyze_display(specs)
    assert result["check"] == "display"
    assert result["status"] == "ERROR"


def test_analyze_display_multi_monitor():
    # Only the primary (first) display is evaluated
    specs = {"DisplayCapabilities": [
        {"current_refresh_hz": 60, "max_refresh_hz": 144, "edid_declared_max_hz": None},  # primary: WARNING
        {"current_refresh_hz": 144, "max_refresh_hz": 144, "edid_declared_max_hz": None},  # secondary: OK
    ]}
    result = analyze_display(specs)
    assert result["check"] == "display"
    assert result["status"] == "WARNING"
    assert result["expected"] == 144
