"""Unit tests for pipeline/approval.py — display_proposals, run_approval_flow, execute_approved_fixes."""

from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# display_proposals
# ---------------------------------------------------------------------------

class TestDisplayProposals:

    def test_empty_list_returns_empty(self):
        from src.pipeline.approval import display_proposals
        with patch("src.pipeline.approval.print_proposal"):
            result = display_proposals([])
        assert result == []

    def test_returns_only_auto_fixable(self):
        from src.pipeline.approval import display_proposals
        proposals = [
            {"finding": "a", "can_auto_fix": True},
            {"finding": "b", "can_auto_fix": False},
            {"finding": "c", "can_auto_fix": True},
        ]
        with patch("src.pipeline.approval.print_proposal"):
            result = display_proposals(proposals)
        assert len(result) == 2
        assert result[0] == (1, proposals[0])
        assert result[1] == (3, proposals[2])

    def test_none_fixable_returns_empty(self):
        from src.pipeline.approval import display_proposals
        proposals = [
            {"finding": "x", "can_auto_fix": False},
            {"finding": "y", "can_auto_fix": False},
        ]
        with patch("src.pipeline.approval.print_proposal"):
            result = display_proposals(proposals)
        assert result == []

    def test_print_proposal_called_for_each(self):
        from src.pipeline.approval import display_proposals
        proposals = [{"finding": "a", "can_auto_fix": True}, {"finding": "b", "can_auto_fix": False}]
        with patch("src.pipeline.approval.print_proposal") as mock_pp:
            display_proposals(proposals)
        assert mock_pp.call_count == 2


# ---------------------------------------------------------------------------
# run_approval_flow
# ---------------------------------------------------------------------------

class _FakeCtx:
    approved_proposals: list = []
    specs: dict = {}
    restore_point_created: bool = False
    fixes_applied: int = 0


class TestRunApprovalFlow:

    def test_returns_zero_when_no_proposals(self):
        from src.pipeline.approval import run_approval_flow
        ctx = _FakeCtx()
        with patch("src.pipeline.approval.print_success"):
            result = run_approval_flow([], ctx)
        assert result == 0

    def test_returns_zero_when_all_manual(self):
        from src.pipeline.approval import run_approval_flow
        ctx = _FakeCtx()
        proposals = [{"finding": "bios_xmp", "can_auto_fix": False}]
        with patch("src.pipeline.approval.display_proposals", return_value=[]), \
             patch("src.pipeline.approval.print_info"):
            result = run_approval_flow(proposals, ctx)
        assert result == 0

    def test_gui_handler_skip_returns_zero(self):
        from src.pipeline.approval import run_approval_flow
        ctx = _FakeCtx()
        proposals = [{"finding": "power_plan", "can_auto_fix": True}]
        auto_fixable = [(1, proposals[0])]

        with patch("src.pipeline.approval.display_proposals", return_value=auto_fixable), \
             patch("src.utils.formatting.get_batch_selection_handler", return_value=lambda *_: []), \
             patch("src.pipeline.approval.action_logger"), \
             patch("src.pipeline.approval.print_info"):
            result = run_approval_flow(proposals, ctx)
        assert result == 0

    def test_gui_handler_selects_all_populates_ctx(self):
        from src.pipeline.approval import run_approval_flow
        ctx = _FakeCtx()
        proposals = [
            {"finding": "power_plan", "can_auto_fix": True},
            {"finding": "game_mode", "can_auto_fix": True},
        ]
        auto_fixable = [(1, proposals[0]), (2, proposals[1])]

        with patch("src.pipeline.approval.display_proposals", return_value=auto_fixable), \
             patch("src.utils.formatting.get_batch_selection_handler",
                   return_value=lambda *_: [1, 2]), \
             patch("src.pipeline.approval.action_logger"):
            result = run_approval_flow(proposals, ctx)
        assert result == 2
        assert len(ctx.approved_proposals) == 2

    def test_gui_handler_partial_selection(self):
        from src.pipeline.approval import run_approval_flow
        ctx = _FakeCtx()
        proposals = [
            {"finding": "power_plan", "can_auto_fix": True},
            {"finding": "game_mode", "can_auto_fix": True},
        ]
        auto_fixable = [(1, proposals[0]), (2, proposals[1])]

        with patch("src.pipeline.approval.display_proposals", return_value=auto_fixable), \
             patch("src.utils.formatting.get_batch_selection_handler",
                   return_value=lambda *_: [1]), \
             patch("src.pipeline.approval.action_logger"):
            result = run_approval_flow(proposals, ctx)
        assert result == 1
        assert ctx.approved_proposals == [proposals[0]]


# ---------------------------------------------------------------------------
# execute_approved_fixes
# ---------------------------------------------------------------------------

class TestExecuteApprovedFixes:

    def _make_ctx(self, proposals):
        ctx = _FakeCtx()
        ctx.approved_proposals = list(proposals)
        ctx.restore_point_created = False
        ctx.specs = {}
        ctx.fixes_applied = 0
        return ctx

    def test_returns_zero_when_no_proposals(self):
        from src.pipeline.approval import execute_approved_fixes
        ctx = self._make_ctx([])
        assert execute_approved_fixes(ctx) == 0

    def test_all_fixes_succeed(self):
        from src.pipeline.approval import execute_approved_fixes
        proposals = [{"finding": "power_plan"}, {"finding": "game_mode"}]
        ctx = self._make_ctx(proposals)
        with patch("src.pipeline.approval.execute_fix", return_value=True), \
             patch("src.pipeline.approval.AnimatedProgressBar") as mock_bar, \
             patch("src.utils.revert.start_session_manifest"), \
             patch("src.pipeline.approval.print_info"):
            mock_bar.return_value = MagicMock()
            result = execute_approved_fixes(ctx)
        assert result == 2
        assert ctx.fixes_applied == 2

    def test_partial_failures_counted_correctly(self):
        from src.pipeline.approval import execute_approved_fixes
        proposals = [{"finding": "a"}, {"finding": "b"}, {"finding": "c"}]
        ctx = self._make_ctx(proposals)
        with patch("src.pipeline.approval.execute_fix", side_effect=[True, False, True]), \
             patch("src.pipeline.approval.AnimatedProgressBar") as mock_bar, \
             patch("src.utils.revert.start_session_manifest"), \
             patch("src.pipeline.approval.print_info"):
            mock_bar.return_value = MagicMock()
            result = execute_approved_fixes(ctx)
        assert result == 2
        assert ctx.fixes_applied == 2

    def test_manifest_init_called_with_restore_point_flag(self):
        from src.pipeline.approval import execute_approved_fixes
        proposals = [{"finding": "power_plan"}]
        ctx = self._make_ctx(proposals)
        ctx.restore_point_created = True
        with patch("src.pipeline.approval.execute_fix", return_value=True), \
             patch("src.pipeline.approval.AnimatedProgressBar") as mock_bar, \
             patch("src.utils.revert.start_session_manifest") as mock_manifest, \
             patch("src.pipeline.approval.print_info"):
            mock_bar.return_value = MagicMock()
            execute_approved_fixes(ctx)
        mock_manifest.assert_called_once_with(restore_point_created=True)
