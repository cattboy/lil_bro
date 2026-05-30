"""Tests for src/utils/dump_parser.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.dump_parser import extract_hardware_summary, load_and_parse


class TestLoadAndParse:
    def test_load_and_parse_valid_json(self, tmp_path):
        """Valid JSON file → returns hardware summary dict."""
        specs_dict = {
            "WMI": {
                "CPU": [{"Name": "Intel Core i9", "Cores": 8, "Speed_MHz": 3600}],
                "RAM": [{"Capacity_GB": 32, "Configured_MHz": 3200, "Speed_MHz": 3200}],
                "OS": [{"Name": "Windows 11"}],
                "VideoController": [{"Name": "Integrated Graphics"}],
                "Motherboard": [{"Make": "ASUS", "Model": "ROG"}],
            },
            "NVIDIA": [],
        }
        specs_file = tmp_path / "full_specs.json"
        specs_file.write_text(json.dumps(specs_dict), encoding="utf-8")

        result = load_and_parse(specs_file)
        assert isinstance(result, dict)
        assert result["cpu"] == "Intel Core i9 (8 cores, 3600 MHz)"
        assert result["ram_gb"] == 32.0

    def test_load_and_parse_file_not_found(self):
        """Non-existent file → returns empty dict."""
        result = load_and_parse(Path("/nonexistent/path/specs.json"))
        assert result == {}

    def test_load_and_parse_malformed_json(self, tmp_path):
        """Malformed JSON → returns empty dict."""
        specs_file = tmp_path / "broken.json"
        specs_file.write_text("{invalid json", encoding="utf-8")

        result = load_and_parse(specs_file)
        assert result == {}


class TestExtractHardwareSummary:
    def test_extract_hardware_summary_nvidia_path(self):
        """nvidia-smi GPU data → gpu_name and vram_gb fields populated."""
        specs = {
            "WMI": {
                "CPU": [{"Name": "AMD Ryzen 9", "Cores": 16, "Speed_MHz": 3700}],
                "RAM": [{"Capacity_GB": 64, "Configured_MHz": 3600, "Speed_MHz": 3600}],
                "OS": [{"Name": "Windows 11"}],
                "Motherboard": [{"Make": "MSI", "Model": "B550"}],
            },
            "NVIDIA": [
                {
                    "GPU": "NVIDIA RTX 4090",
                    "Driver": "552.12",
                }
            ],
        }
        result = extract_hardware_summary(specs)
        assert result["gpu"] == "NVIDIA RTX 4090"
        assert result["gpu_driver"] == "552.12"
        assert result["cpu"] == "AMD Ryzen 9 (16 cores, 3700 MHz)"

    def test_extract_hardware_summary_unknown_fallback(self):
        """Empty or missing GPU data → returns 'Unknown' gracefully."""
        specs = {
            "WMI": {
                "RAM": [{"Capacity_GB": 16}],
                "OS": [{"Name": "Windows 10"}],
            },
            "NVIDIA": [],
        }
        result = extract_hardware_summary(specs)
        assert result["gpu"] == "Unknown"
        assert result["cpu"] == "Unknown"
        assert result["gpu_driver"] == "Unknown"
        assert result["ram_gb"] == 16.0

    def test_extract_hardware_summary_wmi_gpu_fallback(self):
        """No NVIDIA data, but WMI VideoController present → uses VideoController."""
        specs = {
            "WMI": {
                "CPU": [{"Name": "Intel Core i7", "Cores": 8, "Speed_MHz": 3200}],
                "RAM": [{"Capacity_GB": 16}],
                "OS": [{"Name": "Windows 11"}],
                "VideoController": [{"Name": "Intel Iris Xe Graphics"}],
                "Motherboard": [{"Make": "Dell", "Model": "XPS"}],
            },
            "NVIDIA": [],
        }
        result = extract_hardware_summary(specs)
        assert result["gpu"] == "Intel Iris Xe Graphics"
        assert result["cpu"] == "Intel Core i7 (8 cores, 3200 MHz)"

    def test_extract_hardware_summary_ram_multiple_sticks(self):
        """Multiple RAM sticks → capacities summed, first stick's speed used."""
        specs = {
            "WMI": {
                "CPU": [{"Name": "Intel i5", "Cores": 4, "Speed_MHz": 2800}],
                "RAM": [
                    {"Capacity_GB": 8, "Configured_MHz": 2666, "Speed_MHz": 2666},
                    {"Capacity_GB": 8, "Configured_MHz": 2666, "Speed_MHz": 2666},
                ],
                "OS": [{"Name": "Windows 11"}],
            },
            "NVIDIA": [],
        }
        result = extract_hardware_summary(specs)
        assert result["ram_gb"] == 16.0
        assert result["ram_mhz"] == 2666
