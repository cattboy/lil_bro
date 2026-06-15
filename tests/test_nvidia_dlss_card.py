"""Tests for the NvidiaDlssCard dashboard widget.

Offscreen Qt (conftest.py) + qtbot. Covers: Apply emits the fixed check name,
set_gpu renders correctly, the Quality/FPS switch and its flanking labels emit
priority_changed, set_priority reflects state without emitting, and the default
state is Quality.

The control is a custom ``ToggleSwitch`` (``card._toggle``): unchecked = Quality,
checked = FPS. ``clicked`` (user) drives priority_changed; programmatic
``setChecked`` (used by ``set_priority``) must stay silent.
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


def test_toggle_to_fps_emits_priority_changed(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    # Default is Quality (unchecked); a user click flips to FPS.
    with qtbot.waitSignal(card.priority_changed, timeout=1000) as blocker:
        card._toggle.click()
    assert blocker.args == ["fps"]
    assert card._toggle.isChecked() is True


def test_toggle_to_quality_emits_priority_changed(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card._toggle.setChecked(True)  # start on FPS (programmatic, no signal)
    with qtbot.waitSignal(card.priority_changed, timeout=1000) as blocker:
        card._toggle.click()
    assert blocker.args == ["quality"]
    assert card._toggle.isChecked() is False


def test_fps_label_click_emits_priority_changed(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    with qtbot.waitSignal(card.priority_changed, timeout=1000) as blocker:
        card._fps_lbl.clicked.emit()
    assert blocker.args == ["fps"]
    assert card._toggle.isChecked() is True


def test_quality_label_click_emits_priority_changed(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_priority("fps")
    with qtbot.waitSignal(card.priority_changed, timeout=1000) as blocker:
        card._quality_lbl.clicked.emit()
    assert blocker.args == ["quality"]
    assert card._toggle.isChecked() is False


def test_clicking_active_label_is_noop(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    # Default is Quality; clicking the already-active Quality label emits nothing.
    with qtbot.assertNotEmitted(card.priority_changed):
        card._quality_lbl.clicked.emit()
    assert card._toggle.isChecked() is False


def test_default_state_is_quality(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    assert card._toggle.isChecked() is False


def test_set_priority_reflects_fps(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_priority("fps")
    assert card._toggle.isChecked() is True


def test_set_priority_reflects_quality(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_priority("fps")
    card.set_priority("quality")
    assert card._toggle.isChecked() is False


def test_set_priority_does_not_emit(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    with qtbot.assertNotEmitted(card.priority_changed):
        card.set_priority("fps")
        card.set_priority("quality")
