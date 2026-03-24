"""Tests for src.pipeline.approval.parse_selection."""
import pytest
from src.pipeline.approval import parse_selection


class TestParseSelection:
    def test_empty_string_returns_empty_list(self):
        assert parse_selection("", 5) == []

    def test_skip_returns_empty_list(self):
        assert parse_selection("skip", 5) == []

    def test_s_returns_empty_list(self):
        assert parse_selection("s", 5) == []

    def test_all_returns_full_range(self):
        assert parse_selection("all", 3) == [1, 2, 3]

    def test_single_number(self):
        assert parse_selection("2", 5) == [2]

    def test_multiple_numbers(self):
        assert parse_selection("1 3", 5) == [1, 3]

    def test_out_of_range_returns_none(self):
        assert parse_selection("6", 5) is None

    def test_zero_returns_none(self):
        assert parse_selection("0", 5) is None

    def test_negative_returns_none(self):
        assert parse_selection("-1", 5) is None

    def test_non_numeric_returns_none(self):
        assert parse_selection("abc", 5) is None

    def test_whitespace_handling(self):
        assert parse_selection("  1  3  ", 5) == [1, 3]

    def test_case_insensitive_all(self):
        assert parse_selection("ALL", 3) == [1, 2, 3]
