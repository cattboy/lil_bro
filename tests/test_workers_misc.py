"""Tests for RevertWorker, _MonitorRefreshWorker, and _MousePollWorker.

All three workers are QObjects whose run() methods are called synchronously
in tests (no QThread). Signals are captured by connecting to a list before
calling run().
"""
from __future__ import annotations

from unittest.mock import patch

from src.gui.worker import RevertOneWorker, RevertWorker, _MonitorRefreshWorker, _MousePollWorker


class TestRevertWorker:
    def test_emits_started_and_finished_on_success(self):
        """Happy path: revert_started then revert_finished; no failed."""
        worker = RevertWorker()
        order: list[str] = []
        worker.revert_started.connect(lambda: order.append("started"))
        worker.revert_finished.connect(lambda: order.append("finished"))
        worker.revert_failed.connect(lambda *a: order.append("failed"))

        with patch("src.pipeline.phase_revert.run_revert_phase"):
            worker.run()

        assert order == ["started", "finished"], f"unexpected order: {order}"

    def test_emits_failed_on_exception(self):
        """Exception from run_revert_phase must emit revert_failed and not finished."""
        worker = RevertWorker()
        finished: list[str] = []
        failed_args: list[tuple] = []
        worker.revert_finished.connect(lambda: finished.append("finished"))
        worker.revert_failed.connect(lambda *a: failed_args.append(a))

        with patch(
            "src.pipeline.phase_revert.run_revert_phase",
            side_effect=RuntimeError("revert boom"),
        ):
            worker.run()

        assert not finished
        assert len(failed_args) == 1
        exc_type, message, _tb = failed_args[0]
        assert exc_type == "RuntimeError"
        assert "revert boom" in message


class TestRevertOneWorker:
    """Single-entry revert worker (GUI per-item revert)."""

    def test_success_clean_prunes_and_finishes(self):
        worker = RevertOneWorker({"fix": "display", "applied_at": "t1"})
        finished: list[tuple] = []
        failed: list[str] = []
        worker.revert_finished.connect(lambda f, w: finished.append((f, w)))
        worker.revert_failed.connect(lambda m: failed.append(m))
        with patch("src.utils.revert.revert_fix", return_value=(True, "")) as rf, \
             patch("src.utils.revert.remove_fix_from_manifest") as rm:
            worker.run()
        rf.assert_called_once()
        rm.assert_called_once()
        assert finished == [("display", "")]
        assert failed == []

    def test_success_warning_passed_through(self):
        """A display revert returns (True, '<reboot warning>'); carry it through."""
        worker = RevertOneWorker({"fix": "display", "applied_at": "t1"})
        finished: list[tuple] = []
        warn = "reboot required to apply display change"
        worker.revert_finished.connect(lambda f, w: finished.append((f, w)))
        with patch("src.utils.revert.revert_fix", return_value=(True, warn)), \
             patch("src.utils.revert.remove_fix_from_manifest"):
            worker.run()
        assert finished == [("display", warn)]

    def test_failure_does_not_prune_and_emits_failed(self):
        worker = RevertOneWorker({"fix": "power_plan", "applied_at": "t1"})
        finished: list = []
        failed: list[str] = []
        worker.revert_finished.connect(lambda f, w: finished.append((f, w)))
        worker.revert_failed.connect(lambda m: failed.append(m))
        with patch("src.utils.revert.revert_fix",
                   return_value=(False, "power_plan revert: missing before.guid")), \
             patch("src.utils.revert.remove_fix_from_manifest") as rm:
            worker.run()
        rm.assert_not_called()
        assert not finished
        assert failed == ["power_plan revert: missing before.guid"]

    def test_exception_emits_failed_with_type(self):
        worker = RevertOneWorker({"fix": "display", "applied_at": "t1"})
        finished: list = []
        failed: list[str] = []
        worker.revert_finished.connect(lambda f, w: finished.append((f, w)))
        worker.revert_failed.connect(lambda m: failed.append(m))
        with patch("src.utils.revert.revert_fix", side_effect=RuntimeError("boom")):
            worker.run()
        assert not finished
        assert len(failed) == 1
        assert "RuntimeError" in failed[0] and "boom" in failed[0]


class TestMonitorRefreshWorker:
    def test_emits_finished_with_displays_on_success(self):
        """Successful probe must emit finished with the returned display list."""
        worker = _MonitorRefreshWorker()
        results: list[list] = []
        worker.finished.connect(lambda d: results.append(d))
        worker.failed.connect(lambda msg: results.append({"error": msg}))

        displays = [{"device": r"\\.\DISPLAY1", "current_hz": 144}]
        with patch(
            "src.collectors.sub.monitor_dumper.get_monitor_refresh_capabilities",
            return_value=displays,
        ):
            worker.run()

        assert results == [displays]

    def test_emits_failed_on_exception(self):
        """Exception from get_monitor_refresh_capabilities must emit failed, not finished."""
        worker = _MonitorRefreshWorker()
        finished: list = []
        errors: list[str] = []
        worker.finished.connect(lambda d: finished.append(d))
        worker.failed.connect(lambda msg: errors.append(msg))

        with patch(
            "src.collectors.sub.monitor_dumper.get_monitor_refresh_capabilities",
            side_effect=OSError("probe failed"),
        ):
            worker.run()

        assert not finished
        assert len(errors) == 1
        assert "probe failed" in errors[0]


class TestMousePollWorker:
    def test_emits_result_on_success(self):
        """Successful poll must emit finished with the result dict."""
        worker = _MousePollWorker()
        results: list[dict] = []
        worker.finished.connect(lambda r: results.append(r))

        poll_result = {"current_hz": 1000, "status": "OK", "message": ""}
        with patch(
            "src.agent_tools.mouse.check_polling_rate",
            return_value=poll_result,
        ):
            worker.run()

        assert results == [poll_result]

    def test_emits_error_dict_on_exception(self):
        """Exception from check_polling_rate must emit finished with status=ERROR."""
        worker = _MousePollWorker()
        results: list[dict] = []
        worker.finished.connect(lambda r: results.append(r))

        with patch(
            "src.agent_tools.mouse.check_polling_rate",
            side_effect=RuntimeError("mouse gone"),
        ):
            worker.run()

        assert len(results) == 1
        assert results[0]["status"] == "ERROR"
        assert results[0]["current_hz"] == 0
        assert "mouse gone" in results[0]["message"]
