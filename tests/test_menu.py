"""Tests for src/pipeline/menu.py -- setup_ai_model early-return logic."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
from src.pipeline.menu import setup_ai_model


class TestSetupAiModel:

    def test_setup_ai_model_llama_not_installed_returns_early(self):
        """When llama not installed, returns without calling load_model."""
        status = {
            "llama_installed": False,
            "model_downloaded": False,
            "model_path": "/path/to/model",
        }

        with patch("src.pipeline.menu.get_model_status", return_value=status), \
             patch("src.pipeline.menu.print_header"), \
             patch("src.pipeline.menu.print_warning"), \
             patch("src.pipeline.menu.print_info"), \
             patch("src.pipeline.menu.load_model") as mock_load:
            setup_ai_model()

        # load_model should not be called when llama not installed
        mock_load.assert_not_called()

    def test_setup_ai_model_already_loaded_returns_early(self):
        """When get_llm returns non-None, returns without calling load_model."""
        status = {
            "llama_installed": True,
            "model_downloaded": True,
            "model_path": "/path/to/model",
        }

        mock_llm = MagicMock()

        with patch("src.pipeline.menu.get_model_status", return_value=status), \
             patch("src.pipeline.menu.print_header"), \
             patch("src.pipeline.menu.print_success"), \
             patch("src.pipeline.menu.print_info"), \
             patch("src.pipeline.menu.get_llm", return_value=mock_llm), \
             patch("src.pipeline.menu.load_model") as mock_load:
            setup_ai_model()

        # load_model should not be called when model already loaded
        mock_load.assert_not_called()

    def test_setup_ai_model_model_not_downloaded_prints_info(self):
        """When model not downloaded, prints info and returns."""
        status = {
            "llama_installed": True,
            "model_downloaded": False,
            "model_path": "/path/to/model",
        }

        with patch("src.pipeline.menu.get_model_status", return_value=status), \
             patch("src.pipeline.menu.print_header"), \
             patch("src.pipeline.menu.print_success"), \
             patch("src.pipeline.menu.print_info") as mock_info, \
             patch("src.pipeline.menu.get_llm", return_value=None), \
             patch("src.pipeline.menu.load_model") as mock_load:
            setup_ai_model()

        # print_info should be called for model download message
        assert mock_info.call_count > 0
        # load_model called since no model loaded yet
        mock_load.assert_called_once()

    def test_setup_ai_model_loads_model_when_ready(self):
        """When all conditions met, calls load_model and set_llm."""
        status = {
            "llama_installed": True,
            "model_downloaded": True,
            "model_path": "/path/to/model",
        }

        mock_loaded_llm = MagicMock()

        with patch("src.pipeline.menu.get_model_status", return_value=status), \
             patch("src.pipeline.menu.print_header"), \
             patch("src.pipeline.menu.print_success"), \
             patch("src.pipeline.menu.print_info"), \
             patch("src.pipeline.menu.get_llm", side_effect=[None, mock_loaded_llm]), \
             patch("src.pipeline.menu.load_model", return_value=mock_loaded_llm) as mock_load, \
             patch("src.pipeline.menu.set_llm") as mock_set:
            setup_ai_model()

        # load_model and set_llm both called
        mock_load.assert_called_once()
        mock_set.assert_called_once_with(mock_loaded_llm)
