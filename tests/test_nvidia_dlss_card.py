"""Tests for the NvidiaDlssCard dashboard widget.

Offscreen Qt (conftest.py) + qtbot. Covers: Apply emits the fixed check name,
set_gpu renders correctly, toggle emits priority_changed, set_priority reflects
state, and default toggle state is Quality.
"""
from __future__ import annotations

from src.gui.widgets.nvidia_dlss_card import NvidiaDlssCard


def test_apply_button_emits_dlss_check_name(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_gpu("NVIDIA GeForce RTX 5090", "Recommended: DLSS Preset L", "tip")
    with qtbot.waitSignal(card.apply_requested, timeout=1000) as blocker:
        card._apply_btn.click()
    assert blocker.args == ["nvidia_dlss_preset"]


def test_set_gpu_combines_name_and_status(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_gpu("RTX 5090", "Recommended: DLSS Preset L")
    text = card._status_lbl.text()
    assert "RTX 5090" in text
    assert "Recommended" in text


def test_fps_toggle_emits_priority_changed(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    with qtbot.waitSignal(card.priority_changed, timeout=1000) as blocker:
        card._fps_btn.click()
    assert blocker.args == ["fps"]


def test_quality_toggle_emits_priority_changed(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card._fps_btn.setChecked(True)
    with qtbot.waitSignal(card.priority_changed, timeout=1000) as blocker:
        card._quality_btn.click()
    assert blocker.args == ["quality"]


def test_default_toggle_state_is_quality(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    assert card._quality_btn.isChecked() is True
    assert card._fps_btn.isChecked() is False


def test_set_priority_reflects_fps(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_priority("fps")
    assert card._fps_btn.isChecked() is True
    assert card._quality_btn.isChecked() is False


def test_set_priority_reflects_quality(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_priority("fps")
    card.set_priority("quality")
    assert card._quality_btn.isChecked() is True
    assert card._fps_btn.isChecked() is False
