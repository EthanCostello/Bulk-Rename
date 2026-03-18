"""Unit tests for batch_rename_tv pure helper functions."""
import json
import sys
import os
from unittest.mock import MagicMock, patch

# Mock all GUI modules before importing so tests run headlessly
for _mod in [
    'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
    'customtkinter',
]:
    sys.modules.setdefault(_mod, MagicMock())

# Allow importing from parent directory without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from batch_rename_tv import (
    load_history,
    save_history,
    validate_inputs,
    build_rename_plan,
    MEDIA_EXTS,
    MAX_HISTORY,
)


# ---------------------------------------------------------------------------
# load_history / save_history
# ---------------------------------------------------------------------------

class TestLoadHistory:
    def test_returns_defaults_when_file_missing(self, tmp_path):
        with patch('batch_rename_tv.HISTORY_FILE', tmp_path / 'no_such_file.json'):
            hist = load_history()
        assert hist == {"title": [], "year": [], "season": [], "episode": []}

    def test_returns_defaults_on_invalid_json(self, tmp_path):
        bad_file = tmp_path / 'history.json'
        bad_file.write_text("not valid json", encoding='utf-8')
        with patch('batch_rename_tv.HISTORY_FILE', bad_file):
            hist = load_history()
        assert hist == {"title": [], "year": [], "season": [], "episode": []}

    def test_returns_defaults_when_json_is_not_a_dict(self, tmp_path):
        bad_file = tmp_path / 'history.json'
        bad_file.write_text(json.dumps([1, 2, 3]), encoding='utf-8')
        with patch('batch_rename_tv.HISTORY_FILE', bad_file):
            hist = load_history()
        assert hist == {"title": [], "year": [], "season": [], "episode": []}

    def test_roundtrip(self, tmp_path):
        hist_file = tmp_path / 'history.json'
        data = {"title": ["Breaking Bad"], "year": ["2008"], "season": ["1"], "episode": ["1"]}
        with patch('batch_rename_tv.HISTORY_FILE', hist_file):
            save_history(data)
            loaded = load_history()
        assert loaded == data


# ---------------------------------------------------------------------------
# validate_inputs
# ---------------------------------------------------------------------------

class TestValidateInputs:
    def test_valid_inputs(self):
        assert validate_inputs("Breaking Bad", "2008", "1", "1") is None

    def test_empty_title(self):
        err = validate_inputs("", "2008", "1", "1")
        assert err is not None
        assert "title" in err.lower()

    def test_year_not_digits(self):
        err = validate_inputs("Show", "abcd", "1", "1")
        assert err is not None
        assert "year" in err.lower()

    def test_year_wrong_length(self):
        assert validate_inputs("Show", "208", "1", "1") is not None
        assert validate_inputs("Show", "20080", "1", "1") is not None

    def test_year_valid_boundary(self):
        assert validate_inputs("Show", "2024", "1", "1") is None

    def test_season_zero(self):
        assert validate_inputs("Show", "2008", "0", "1") is not None

    def test_season_negative(self):
        assert validate_inputs("Show", "2008", "-1", "1") is not None

    def test_season_not_integer(self):
        assert validate_inputs("Show", "2008", "abc", "1") is not None

    def test_episode_zero(self):
        assert validate_inputs("Show", "2008", "1", "0") is not None

    def test_episode_negative(self):
        assert validate_inputs("Show", "2008", "1", "-5") is not None

    def test_episode_not_integer(self):
        assert validate_inputs("Show", "2008", "1", "abc") is not None

    def test_large_valid_season_and_episode(self):
        assert validate_inputs("Show", "2008", "99", "99") is None


# ---------------------------------------------------------------------------
# build_rename_plan
# ---------------------------------------------------------------------------

class TestBuildRenamePlan:
    def test_single_file(self):
        plan = build_rename_plan(["episode.mp4"], "Breaking Bad", "2008", 1, 1)
        assert plan == [("episode.mp4", "Breaking Bad (2008) - S01E01.mp4")]

    def test_multiple_files_sequential_episodes(self):
        files = ["a.mkv", "b.mkv", "c.mkv"]
        plan = build_rename_plan(files, "Show", "2020", 2, 5)
        assert plan == [
            ("a.mkv", "Show (2020) - S02E05.mkv"),
            ("b.mkv", "Show (2020) - S02E06.mkv"),
            ("c.mkv", "Show (2020) - S02E07.mkv"),
        ]

    def test_preserves_original_extension(self):
        plan = build_rename_plan(["ep.avi"], "Show", "2020", 1, 1)
        assert plan[0][1].endswith(".avi")

    def test_season_and_episode_zero_padded(self):
        plan = build_rename_plan(["ep.mp4"], "Show", "2020", 3, 7)
        assert "S03E07" in plan[0][1]

    def test_season_and_episode_double_digit(self):
        plan = build_rename_plan(["ep.mp4"], "Show", "2020", 12, 10)
        assert "S12E10" in plan[0][1]

    def test_empty_file_list(self):
        plan = build_rename_plan([], "Show", "2020", 1, 1)
        assert plan == []

    def test_raises_on_duplicate_targets_via_patched_suffix(self):
        import batch_rename_tv as m

        class _FakePath:
            def __init__(self, name):
                self._name = name
            @property
            def suffix(self):
                return ''

        original_path = m.Path
        m.Path = _FakePath
        try:
            with pytest.raises(ValueError, match="Duplicate"):
                targets: set = set()
                for _ in range(2):
                    new = "Show (2020) - S01E01"
                    if new in targets:
                        raise ValueError(f"Duplicate target filename: {new}")
                    targets.add(new)
        finally:
            m.Path = original_path

    def test_no_collision_in_normal_usage(self):
        files = [f"ep{i}.mp4" for i in range(10)]
        plan = build_rename_plan(files, "Show", "2020", 1, 1)
        targets = [new for _, new in plan]
        assert len(targets) == len(set(targets))


# ---------------------------------------------------------------------------
# MEDIA_EXTS constant
# ---------------------------------------------------------------------------

class TestMediaExts:
    def test_contains_expected_formats(self):
        for ext in ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v'):
            assert ext in MEDIA_EXTS

    def test_all_lowercase(self):
        for ext in MEDIA_EXTS:
            assert ext == ext.lower()

    def test_all_start_with_dot(self):
        for ext in MEDIA_EXTS:
            assert ext.startswith('.')


# ---------------------------------------------------------------------------
# MAX_HISTORY constant
# ---------------------------------------------------------------------------

class TestMaxHistory:
    def test_history_capped_at_max(self):
        lst = []
        for i in range(MAX_HISTORY + 5):
            v = str(i)
            if v not in lst:
                lst.append(v)
                if len(lst) > MAX_HISTORY:
                    lst.pop(0)
        assert len(lst) == MAX_HISTORY
