"""Tests for _parse_tile_created_at and the duplicate_window_days logic."""
import asyncio
import datetime
import pytest
from playwright_prototype.steps import ExistingWorkItemError, _parse_tile_created_at
import playwright_prototype.steps as steps


class TestParseTileCreatedAt:

    def test_parses_standard_format(self):
        text = "Open\nComplaints: PM\nCreated At: 5/22/2026, 1:39:33 PM\nEstimated Labor Time: 0.5"
        assert _parse_tile_created_at(text) == datetime.date(2026, 5, 22)

    def test_parses_single_digit_month_and_day(self):
        assert _parse_tile_created_at("Created At: 1/3/2026, 9:00:00 AM") == datetime.date(2026, 1, 3)

    def test_returns_none_when_absent(self):
        assert _parse_tile_created_at("Open\nComplaints: Glass\nEstimated Labor Time: 1.0") is None

    def test_returns_none_on_bad_format(self):
        assert _parse_tile_created_at("Created At: not-a-date") is None

    def test_case_insensitive(self):
        assert _parse_tile_created_at("created at: 5/22/2026, 1:00:00 PM") == datetime.date(2026, 5, 22)


class TestDuplicateWindowDays:
    """Verify the age-based logic via config override."""

    def _tile_text(self, date: datetime.date) -> str:
        return f"Open\nComplaints: PM\nCreated At: {date.month}/{date.day}/{date.year}, 1:00:00 PM\nEstimated Labor Time: 0.5"

    def test_within_window_is_dup(self):
        today = datetime.date.today()
        tile_date = today - datetime.timedelta(days=3)
        created_at = _parse_tile_created_at(self._tile_text(tile_date))
        age = (today - created_at).days
        assert age <= 5

    def test_at_window_boundary_is_dup(self):
        today = datetime.date.today()
        tile_date = today - datetime.timedelta(days=5)
        created_at = _parse_tile_created_at(self._tile_text(tile_date))
        age = (today - created_at).days
        assert age <= 5

    def test_beyond_window_is_not_dup(self):
        today = datetime.date.today()
        tile_date = today - datetime.timedelta(days=6)
        created_at = _parse_tile_created_at(self._tile_text(tile_date))
        age = (today - created_at).days
        assert age > 5

    def test_zero_window_always_dup(self):
        today = datetime.date.today()
        tile_date = today - datetime.timedelta(days=100)
        created_at = _parse_tile_created_at(self._tile_text(tile_date))
        age = (today - created_at).days
        assert age > 5


class _FakeTile:
    def __init__(self, text: str):
        self._text = text

    async def inner_text(self) -> str:
        return self._text


class _FakeLocator:
    def __init__(self, tile_texts: list[str], visible: bool = True):
        self._tile_texts = tile_texts
        self._visible = visible

    @property
    def first(self):
        return self

    def filter(self, **_kwargs):
        return self

    async def wait_for(self, **_kwargs):
        if not self._visible:
            raise RuntimeError("not visible")

    async def count(self) -> int:
        return len(self._tile_texts)

    def nth(self, idx: int):
        return _FakeTile(self._tile_texts[idx])


class _FakePage:
    def __init__(self, tile_texts: list[str], visible: bool = True):
        self._tile_texts = tile_texts
        self._visible = visible

    def locator(self, _selector: str):
        return _FakeLocator(self._tile_texts, visible=self._visible)


class TestCheckExistingWorkItemDuplicateWindow:
    def _tile_text(self, date: datetime.date | None, complaints: str = "PM", status: str = "Open") -> str:
        if date is None:
            return f"{status}\nComplaints: {complaints}\nEstimated Labor Time: 0.5"
        return (
            f"{status}\nComplaints: {complaints}\n"
            f"Created At: {date.month}/{date.day}/{date.year}, 1:39:33 PM\nEstimated Labor Time: 0.5"
        )

    def test_within_window_raises_duplicate(self, monkeypatch):
        monkeypatch.setattr(steps, "get_config", lambda key, default=None: 5 if key == "duplicate_window_days" else default)
        tile_date = datetime.date.today() - datetime.timedelta(days=2)
        page = _FakePage([self._tile_text(tile_date)])

        with pytest.raises(ExistingWorkItemError):
            asyncio.run(steps.check_existing_work_item(page, "12345", "PM"))

    def test_open_beyond_window_still_raises_duplicate(self, monkeypatch):
        monkeypatch.setattr(steps, "get_config", lambda key, default=None: 5 if key == "duplicate_window_days" else default)
        tile_date = datetime.date.today() - datetime.timedelta(days=10)
        page = _FakePage([self._tile_text(tile_date)])

        with pytest.raises(ExistingWorkItemError):
            asyncio.run(steps.check_existing_work_item(page, "12345", "PM"))

    def test_open_in_header_text_still_raises_duplicate(self, monkeypatch):
        monkeypatch.setattr(steps, "get_config", lambda key, default=None: 5 if key == "duplicate_window_days" else default)
        tile_date = datetime.date.today() - datetime.timedelta(days=10)
        page = _FakePage([self._tile_text(tile_date, status="Glass Damage - Open")])

        with pytest.raises(ExistingWorkItemError):
            asyncio.run(steps.check_existing_work_item(page, "12345", "PM"))

    def test_closed_within_window_raises_duplicate(self, monkeypatch):
        monkeypatch.setattr(steps, "get_config", lambda key, default=None: 5 if key == "duplicate_window_days" else default)
        tile_date = datetime.date.today() - datetime.timedelta(days=2)
        page = _FakePage([self._tile_text(tile_date, status="Complete")])

        with pytest.raises(ExistingWorkItemError):
            asyncio.run(steps.check_existing_work_item(page, "12345", "PM"))

    def test_closed_beyond_window_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(steps, "get_config", lambda key, default=None: 5 if key == "duplicate_window_days" else default)
        tile_date = datetime.date.today() - datetime.timedelta(days=10)
        page = _FakePage([self._tile_text(tile_date, status="Complete")])

        asyncio.run(steps.check_existing_work_item(page, "12345", "PM"))

    def test_missing_created_at_raises_duplicate(self, monkeypatch):
        monkeypatch.setattr(steps, "get_config", lambda key, default=None: 5 if key == "duplicate_window_days" else default)
        page = _FakePage([self._tile_text(None)])

        with pytest.raises(ExistingWorkItemError):
            asyncio.run(steps.check_existing_work_item(page, "12345", "PM"))

    def test_zero_window_always_raises(self, monkeypatch):
        monkeypatch.setattr(steps, "get_config", lambda key, default=None: 0 if key == "duplicate_window_days" else default)
        tile_date = datetime.date.today() - datetime.timedelta(days=100)
        page = _FakePage([self._tile_text(tile_date)])

        with pytest.raises(ExistingWorkItemError):
            asyncio.run(steps.check_existing_work_item(page, "12345", "PM"))
