"""Tests for src.utils.display_utils — DEVMODE struct and enum_raw_modes."""
import ctypes
from unittest.mock import patch

from src.utils.display_utils import DEVMODE, ENUM_CURRENT_SETTINGS, ENUM_REGISTRY_SETTINGS, enum_raw_modes


class TestDevmodeStruct:
    def test_instantiates_without_error(self):
        """DEVMODE can be constructed and dmSize assigned."""
        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        assert dm.dmSize > 0

    def test_has_expected_fields(self):
        """Spot-check critical fields exist on the struct."""
        dm = DEVMODE()
        assert hasattr(dm, "dmPelsWidth")
        assert hasattr(dm, "dmPelsHeight")
        assert hasattr(dm, "dmDisplayFrequency")
        assert hasattr(dm, "dmBitsPerPel")

    def test_constants(self):
        """ENUM_CURRENT_SETTINGS and ENUM_REGISTRY_SETTINGS have expected values."""
        assert ENUM_CURRENT_SETTINGS == -1
        assert ENUM_REGISTRY_SETTINGS == -2


class TestEnumRawModes:
    def test_returns_list_of_devmode_objects(self):
        """enum_raw_modes returns a list of DEVMODE instances, one per mode."""
        call_count = 0

        def fake_enum(device_name, i, ctypes_byref):
            nonlocal call_count
            call_count += 1
            return call_count == 1  # True once → one mode appended, then False → loop ends

        with patch("ctypes.windll") as mock_windll:
            mock_windll.user32.EnumDisplaySettingsW.side_effect = fake_enum
            result = enum_raw_modes(None)

        assert len(result) == 1
        assert isinstance(result[0], DEVMODE)

    def test_single_canonical_definition(self):
        """DEVMODE is only defined in display_utils — not in monitor_dumper or display_setter."""
        import inspect
        from src.collectors.sub import monitor_dumper
        from src.agent_tools import display_setter

        monitor_members = dict(inspect.getmembers(monitor_dumper))
        setter_members = dict(inspect.getmembers(display_setter))

        from src.utils.display_utils import DEVMODE as canonical_DEVMODE

        # Both modules should expose DEVMODE but it must be the same object (imported, not re-defined)
        assert monitor_members.get("DEVMODE") is canonical_DEVMODE, (
            "monitor_dumper.DEVMODE is not the canonical class from display_utils"
        )
        assert setter_members.get("DEVMODE") is canonical_DEVMODE, (
            "display_setter.DEVMODE is not the canonical class from display_utils"
        )
