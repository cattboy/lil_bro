from src.agent_tools.rebar import analyze_rebar


def test_analyze_rebar_nvidia_enabled():
    specs = {"NVIDIA": [{"ReBAR": True, "BAR1 Used (MiB)": 8192, "GPU": "RTX 4090"}]}
    result = analyze_rebar(specs)
    assert result["status"] == "OK"
    assert result["current"] is True
    assert "ENABLED" in result["message"]
    assert "RTX 4090" in result["message"]


def test_analyze_rebar_nvidia_disabled():
    specs = {"NVIDIA": [{"ReBAR": False, "BAR1 Used (MiB)": 256, "GPU": "RTX 3080"}]}
    result = analyze_rebar(specs)
    assert result["status"] == "WARNING"
    assert result["current"] is False
    assert "DISABLED" in result["message"]
    assert "Above 4G Decoding" in result["message"]


def test_analyze_rebar_wmi_fallback_enabled():
    specs = {"WMI": {"ReBAR": {"enabled": True, "max_range_mb": 8192.0}}}
    result = analyze_rebar(specs)
    assert result["status"] == "OK"
    assert result["current"] is True
    assert "ENABLED" in result["message"]


def test_analyze_rebar_wmi_fallback_disabled():
    specs = {"WMI": {"ReBAR": {"enabled": False, "max_range_mb": 0.0}}}
    result = analyze_rebar(specs)
    assert result["status"] == "WARNING"
    assert result["current"] is False
    assert "Above 4G Decoding" in result["message"]


def test_analyze_rebar_unknown():
    result = analyze_rebar({})
    assert result["status"] == "UNKNOWN"
    assert result["current"] is None


def test_analyze_rebar_nvidia_takes_precedence():
    specs = {
        "NVIDIA": [{"ReBAR": False, "BAR1 Used (MiB)": 256, "GPU": "RTX 3080"}],
        "WMI": {"ReBAR": {"enabled": True, "max_range_mb": 8192.0}},
    }
    result = analyze_rebar(specs)
    assert result["status"] == "WARNING"
    assert "RTX 3080" in result["message"]
