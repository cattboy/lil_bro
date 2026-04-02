from src.agent_tools.xmp_check import analyze_xmp


def test_analyze_xmp_enabled_diff():
    """XMP detected: configured speed > base speed."""
    specs = {"WMI": {"RAM": [{"Configured_MHz": 3600, "Speed_MHz": 2133}]}}
    result = analyze_xmp(specs)
    assert result["status"] == "OK"
    assert result["current"] == 3600
    assert "XMP/EXPO" in result["message"]


def test_analyze_xmp_enabled_ddr4_heuristic():
    """XMP detected: active speed in DDR4 XMP territory (2667-3999 MHz)."""
    specs = {"WMI": {"RAM": [{"Configured_MHz": 3200, "Speed_MHz": 3200}]}}
    result = analyze_xmp(specs)
    assert result["status"] == "OK"
    assert result["current"] == 3200


def test_analyze_xmp_enabled_ddr5_heuristic():
    """XMP detected: active speed >= 5200 (DDR5 EXPO/XMP territory)."""
    specs = {"WMI": {"RAM": [{"Configured_MHz": 6000, "Speed_MHz": 6000}]}}
    result = analyze_xmp(specs)
    assert result["status"] == "OK"
    assert result["current"] == 6000


def test_analyze_xmp_disabled_jedec():
    """XMP not detected: running at base JEDEC speed."""
    specs = {"WMI": {"RAM": [{"Configured_MHz": 2133, "Speed_MHz": 2133}]}}
    result = analyze_xmp(specs)
    assert result["status"] == "WARNING"
    assert result["current"] == 2133
    assert "JEDEC" in result["message"]


def test_analyze_xmp_no_ram_data():
    """No RAM data in specs at all."""
    result = analyze_xmp({})
    assert result["status"] == "ERROR"
    assert result["current"] == 0
