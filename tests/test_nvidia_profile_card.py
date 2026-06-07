"""Tests for the reusable NvidiaProfileCard dashboard widget.

Offscreen Qt (conftest.py) + qtbot. Asserts the Apply button emits the fix
check name and that set_gpu composes the GPU name with the status text.
"""
from __future__ import annotations

from src.gui.widgets.nvidia_profile_card import NvidiaProfileCard


def test_apply_button_emits_check_name(qtbot):
    card = NvidiaProfileCard("nvidia_dlss_preset", "DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_gpu("NVIDIA GeForce RTX 5090", "Recommended: DLSS Preset L", "tip")
    with qtbot.waitSignal(card.apply_requested, timeout=1000) as blocker:
        card._apply_btn.click()
    assert blocker.args == ["nvidia_dlss_preset"]


def test_set_gpu_combines_name_and_status(qtbot):
    card = NvidiaProfileCard("nvidia_profile", "NVIDIA Driver Profile", "Optimize")
    qtbot.addWidget(card)
    card.set_gpu("RTX 5090", "Optimize: G-Sync etc.")
    text = card._status_lbl.text()
    assert "RTX 5090" in text
    assert "Optimize" in text


def test_priority_toggle_emits(qtbot):
    card = NvidiaProfileCard("nvidia_dlss_preset", "DLSS Preset", "Apply Preset",
                             with_priority_toggle=True)
    qtbot.addWidget(card)
    with qtbot.waitSignal(card.priority_changed, timeout=1000) as blocker:
        card._fps_btn.click()
    assert blocker.args == ["fps"]


def test_no_priority_toggle_by_default(qtbot):
    card = NvidiaProfileCard("nvidia_profile", "NVIDIA Driver Profile", "Optimize")
    qtbot.addWidget(card)
    assert card._quality_btn is None
    assert card._fps_btn is None


def test_set_priority_reflects_state(qtbot):
    card = NvidiaProfileCard("nvidia_dlss_preset", "DLSS Preset", "Apply Preset",
                             with_priority_toggle=True)
    qtbot.addWidget(card)
    card.set_priority("fps")
    assert card._fps_btn.isChecked() is True
    assert card._quality_btn.isChecked() is False
