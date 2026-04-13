"""Tests for src/utils/subprocess_utils.py."""
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from src.utils.subprocess_utils import run_subprocess


@patch("src.utils.subprocess_utils.subprocess.run")
def test_happy_path_returns_completed_process(mock_run):
    mock_result = MagicMock(spec=subprocess.CompletedProcess)
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    result = run_subprocess(["echo", "hi"])

    assert result is mock_result
    mock_run.assert_called_once_with(
        ["echo", "hi"],
        timeout=10,
        capture_output=True,
        text=True,
        check=False,
    )


@patch("src.utils.subprocess_utils.subprocess.run")
def test_nonzero_returncode_still_returns_result(mock_run):
    mock_result = MagicMock(spec=subprocess.CompletedProcess)
    mock_result.returncode = 1
    mock_run.return_value = mock_result

    result = run_subprocess(["false"])

    assert result is mock_result


@patch("src.utils.subprocess_utils.subprocess.run")
def test_timeout_raises_and_is_reraised(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["slow"], timeout=10)

    with pytest.raises(subprocess.TimeoutExpired):
        run_subprocess(["slow"], timeout=10)


@patch("src.utils.subprocess_utils.subprocess.run")
def test_file_not_found_is_reraised(mock_run):
    mock_run.side_effect = FileNotFoundError("not found")

    with pytest.raises(FileNotFoundError):
        run_subprocess(["missing-binary"])


@patch("src.utils.subprocess_utils.subprocess.run")
def test_called_process_error_reraised_when_check_true(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["cmd"])

    with pytest.raises(subprocess.CalledProcessError):
        run_subprocess(["cmd"], check=True)


@patch("src.utils.subprocess_utils.subprocess.run")
def test_custom_timeout_forwarded(mock_run):
    mock_result = MagicMock(spec=subprocess.CompletedProcess)
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    run_subprocess(["cmd"], timeout=30)

    _, kwargs = mock_run.call_args
    assert kwargs["timeout"] == 30
