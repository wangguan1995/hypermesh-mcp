"""convert_stp_to_hm.py 纯函数单元测试（无 HyperMesh 依赖）。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from convert_stp_to_hm import (  # noqa: E402
    _has_non_ascii,
    _stem_to_safe_ascii,
    locate_hmbatch,
    locate_runhwx,
)


@pytest.fixture
def no_exe_on_disk(monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda self: False)


class TestHasNonAscii:
    def test_ascii_path(self):
        assert _has_non_ascii(r"C:\Program Files\Altair\part.stp") is False

    def test_ascii_name(self):
        assert _has_non_ascii("part.stp") is False

    def test_chinese_name(self):
        assert _has_non_ascii("零件.stp") is True

    def test_chinese_path(self):
        assert _has_non_ascii(r"C:\Users\零件\part.stp") is True


class TestStemToSafeAscii:
    def test_ascii_passthrough(self):
        assert _stem_to_safe_ascii("part") == "part"

    def test_chinese_exact_match(self):
        assert _stem_to_safe_ascii("齿轮") == "gear"

    def test_chinese_substring_match(self):
        assert _stem_to_safe_ascii("齿轮轴") == "gear_shaft"

    def test_unknown_chinese_fallback_uid(self):
        result = _stem_to_safe_ascii("未知中文名称")
        assert result.startswith("part_")
        assert len(result) == len("part_") + 8


class TestLocateHmbatch:
    def test_missing_raises(self, no_exe_on_disk):
        with pytest.raises(FileNotFoundError):
            locate_hmbatch()

    def test_runhwx_returns_none_when_missing(self, no_exe_on_disk):
        assert locate_runhwx() is None