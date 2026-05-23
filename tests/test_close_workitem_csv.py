"""Tests for _load_csv comment-line skipping in WorkItems/close_workitem.py."""
from pathlib import Path
import pytest


def _write_csv(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "test.csv"
    p.write_text(content, encoding="utf-8")
    return p


class TestLoadCsvCommentSkipping:

    def test_comment_lines_skipped(self, tmp_path):
        from WorkItems.close_workitem import _load_csv
        csv_path = _write_csv(
            tmp_path,
            "# header comment\nmva,Type\n# row comment\n11111,Glass\n",
        )
        rows = _load_csv(str(csv_path))
        assert len(rows) == 1
        assert rows[0]["mva"] == "11111"

    def test_blank_mva_skipped(self, tmp_path):
        from WorkItems.close_workitem import _load_csv
        csv_path = _write_csv(tmp_path, "mva,Type\n,Glass\n22222,PM\n")
        rows = _load_csv(str(csv_path))
        assert len(rows) == 1
        assert rows[0]["mva"] == "22222"

    def test_complaint_type_patterns_imported_from_steps(self):
        from WorkItems.close_workitem import COMPLAINT_TYPE_PATTERNS
        from playwright_prototype.steps import COMPLAINT_TYPE_PATTERNS as steps_patterns
        assert COMPLAINT_TYPE_PATTERNS is steps_patterns
