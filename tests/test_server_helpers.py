"""Pure-function unit tests for hypermesh_mcp_server helpers (no HyperMesh dependency)."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hypermesh_mcp_server import (  # noqa: E402
    _balanced_seed_density,
    _generated_by,
    _tcl_escape_name,
    _estimate_tetra_timeout_seconds,
    _probe_int_list_value,
    _probe_float_list_value,
    _unit_vector,
    _perpendicular_unit_vector,
    _probe_lines_iter,
    _recommended_timeout_from_script,
    _wrap_generated_tcl,
    _unwrap_generated_tcl,
    _script_diag_summary,
    MCP_SCRIPT_BEGIN,
    MCP_SCRIPT_END,
)


class TestBalancedSeedDensity:
    def test_all_equal_counts_no_target(self):
        counts, source = _balanced_seed_density(
            element_size=1.0,
            target_density=None,
            preview_edge_seed_counts=[10, 10, 10],
            source_edge_lengths=None,
            ratio_threshold=3.0,
        )
        assert counts == 10
        assert "average" in source

    def test_high_ratio_balanced(self):
        counts, source = _balanced_seed_density(
            element_size=1.0,
            target_density=None,
            preview_edge_seed_counts=[2, 60],
            source_edge_lengths=None,
            ratio_threshold=3.0,
        )
        assert counts == round((2 * 60) ** 0.5)
        assert "balanced" in source

    def test_explicit_target_used(self):
        counts, source = _balanced_seed_density(
            element_size=1.0,
            target_density=42,
            preview_edge_seed_counts=[10, 10],
            source_edge_lengths=None,
            ratio_threshold=3.0,
        )
        assert counts == 42
        assert source == "explicit"

    def test_no_counts_no_target_bbox_estimate(self):
        counts, source = _balanced_seed_density(
            element_size=1.0,
            target_density=None,
            preview_edge_seed_counts=None,
            source_edge_lengths=None,
            ratio_threshold=3.0,
        )
        assert counts is None
        assert source == "bbox_estimate"

    def test_no_counts_with_target(self):
        counts, source = _balanced_seed_density(
            element_size=1.0,
            target_density=30,
            preview_edge_seed_counts=None,
            source_edge_lengths=None,
            ratio_threshold=3.0,
        )
        assert counts == 30
        assert source == "explicit"

    def test_source_edge_lengths_used(self):
        counts, source = _balanced_seed_density(
            element_size=10.0,
            target_density=None,
            preview_edge_seed_counts=None,
            source_edge_lengths=[100.0, 100.0],
            ratio_threshold=3.0,
        )
        assert counts == 10
        assert "average" in source

    def test_clamped_min(self):
        counts, _ = _balanced_seed_density(
            element_size=1.0,
            target_density=None,
            preview_edge_seed_counts=[1, 1],
            source_edge_lengths=None,
            ratio_threshold=3.0,
        )
        assert counts >= 4

    def test_clamped_max(self):
        counts, _ = _balanced_seed_density(
            element_size=1.0,
            target_density=None,
            preview_edge_seed_counts=[500, 500],
            source_edge_lengths=None,
            ratio_threshold=3.0,
        )
        assert counts <= 120

    def test_low_ratio_uses_average_not_balanced(self):
        counts, source = _balanced_seed_density(
            element_size=1.0,
            target_density=None,
            preview_edge_seed_counts=[10, 12, 11],
            source_edge_lengths=None,
            ratio_threshold=3.0,
        )
        assert "balanced" not in source


class TestGeneratedBy:
    def test_valid_generator(self):
        script = "# mcp_generated_by=generate_guarded_drag_hex_tcl\nsome tcl"
        assert _generated_by(script) == "generate_guarded_drag_hex_tcl"

    def test_lower_case_prefix(self):
        script = "# MCP_GENERATED_BY=generate_plain_tetra_tcl\nsome tcl"
        # the check is .lower() so upper-case prefix also works
        result = _generated_by(script)
        assert result == "generate_plain_tetra_tcl"

    def test_no_generator_returns_none(self):
        assert _generated_by("some tcl without markers") is None

    def test_extra_whitespace(self):
        script = "  # mcp_generated_by=  foo_bar  \n"
        assert _generated_by(script) == "foo_bar"


class TestTclEscapeName:
    def test_plain_name(self):
        assert _tcl_escape_name("my_component") == "my_component"

    def test_backslash(self):
        assert _tcl_escape_name("C:\\path") == "C:\\\\path"

    def test_braces(self):
        assert _tcl_escape_name("my{comp}") == "my\\{comp\\}"

    def test_brackets(self):
        assert _tcl_escape_name("my[comp]") == "my\\[comp\\]"

    def test_dollar_sign(self):
        assert _tcl_escape_name("$VAR") == "\\$VAR"

    def test_double_quote(self):
        assert _tcl_escape_name('my"comp') == 'my\\"comp'

    def test_all_special_chars(self):
        result = _tcl_escape_name('a{b}[c]$d\\e"f')
        assert "\\" in result


class TestEstimateTetraTimeoutSeconds:
    def test_default_bounds(self):
        result = _estimate_tetra_timeout_seconds(
            surf_count=10, min_element_size=0.6, diagonal=50.0, batch_size=1
        )
        assert 300 <= result <= 7200

    def test_min_element_size_clamped(self):
        # min_element_size below 0.2 is clamped to 0.2
        result = _estimate_tetra_timeout_seconds(
            surf_count=1, min_element_size=0.01, diagonal=10.0, batch_size=1
        )
        assert 300 <= result <= 7200

    def test_large_batch_increases_timeout(self):
        t1 = _estimate_tetra_timeout_seconds(
            surf_count=10, min_element_size=0.6, diagonal=50.0, batch_size=1
        )
        t2 = _estimate_tetra_timeout_seconds(
            surf_count=10, min_element_size=0.6, diagonal=50.0, batch_size=5
        )
        assert t2 > t1

    def test_minimum_returned_for_simple_case(self):
        result = _estimate_tetra_timeout_seconds(
            surf_count=1, min_element_size=1.0, diagonal=10.0, batch_size=1
        )
        assert result >= 300


class TestRecommendedTimeoutFromScript:
    def test_valid_timeout(self):
        script = "# MCP_RECOMMENDED_TIMEOUT_SECONDS=300\nsome tcl"
        assert _recommended_timeout_from_script(script) == 300

    def test_invalid_timeout(self):
        script = "# MCP_RECOMMENDED_TIMEOUT_SECONDS=abc\nsome tcl"
        assert _recommended_timeout_from_script(script) is None

    def test_no_timeout_line(self):
        assert _recommended_timeout_from_script("no timeout line here") is None

    def test_only_checks_first_20_lines(self):
        lines = ["# comment\n"] * 21
        lines.append("# MCP_RECOMMENDED_TIMEOUT_SECONDS=600")
        script = "\n".join(lines)
        assert _recommended_timeout_from_script(script) is None


class TestProbeIntListValue:
    def test_none(self):
        assert _probe_int_list_value(None) == []

    def test_empty_list(self):
        assert _probe_int_list_value([]) == []

    def test_int_list(self):
        assert _probe_int_list_value([1, 2, 3]) == [1, 2, 3]

    def test_string_list(self):
        assert _probe_int_list_value("1 2 3") == [1, 2, 3]

    def test_string_with_braces(self):
        assert _probe_int_list_value("{1 2 3}") == [1, 2, 3]

    def test_skip_non_int(self):
        assert _probe_int_list_value("1 abc 3") == [1, 3]

    def test_null_string(self):
        assert _probe_int_list_value("null") == []

    def test_dash_string(self):
        assert _probe_int_list_value("-") == []

    def test_mixed_list(self):
        assert _probe_int_list_value([1, "abc", 3]) == [1, 3]


class TestProbeFloatListValue:
    def test_none(self):
        assert _probe_float_list_value(None) == []

    def test_empty_list(self):
        assert _probe_float_list_value([]) == []

    def test_float_list(self):
        assert _probe_float_list_value([1.0, 2.0, 3.0]) == [1.0, 2.0, 3.0]

    def test_int_list_coerced(self):
        result = _probe_float_list_value([1, 2, 3])
        assert result == [1.0, 2.0, 3.0]

    def test_text_parser(self):
        result = _probe_float_list_value("1.5 2.5 3.5")
        assert result == [1.5, 2.5, 3.5]

    def test_empty_text(self):
        assert _probe_float_list_value("") == []

    def test_null_text(self):
        assert _probe_float_list_value("none") == []


class TestUnitVector:
    def test_basic_z(self):
        assert _unit_vector([0, 0, 1]) == [0, 0, 1]

    def test_basic_x(self):
        assert _unit_vector([1, 0, 0]) == [1, 0, 0]

    def test_basic_y(self):
        assert _unit_vector([0, 1, 0]) == [0, 1, 0]

    def test_non_normalized_input(self):
        result = _unit_vector([3, 4, 0])
        total = sum(v * v for v in result)
        assert abs(total - 1.0) < 1e-6

    def test_zero_vector_returns_empty(self):
        result = _unit_vector([0, 0, 0])
        assert result == []


class TestPerpendicularUnitVector:
    def test_z_axis_perpendicular(self):
        result = _perpendicular_unit_vector([0, 0, 1])
        assert len(result) == 3
        dot = result[0] * 0 + result[1] * 0 + result[2] * 1
        assert abs(dot) < 1e-6
        total = sum(v * v for v in result)
        assert abs(total - 1.0) < 1e-6

    def test_returns_zero_for_zero_input(self):
        result = _perpendicular_unit_vector([0, 0, 0])
        assert result == []


class TestWrapGeneratedTcl:
    def test_wraps_body(self):
        script = _wrap_generated_tcl("generate_test_tcl", "puts hello")
        assert MCP_SCRIPT_BEGIN in script
        assert MCP_SCRIPT_END in script
        assert "puts hello" in script

    def test_includes_generator_name(self):
        script = _wrap_generated_tcl("generate_test_tcl", "puts hello")
        assert "generate_test_tcl" in script


class TestUnwrapGeneratedTcl:
    def test_removes_markers(self):
        body = "puts hello"
        script = _wrap_generated_tcl("generate_test_tcl", body)
        unwrapped = _unwrap_generated_tcl(script)
        assert MCP_SCRIPT_BEGIN not in unwrapped
        assert MCP_SCRIPT_END not in unwrapped
        assert body in unwrapped

    def test_preserves_content(self):
        body = "puts hello\nputs world"
        script = _wrap_generated_tcl("generate_test_tcl", body)
        unwrapped = _unwrap_generated_tcl(script)
        assert "puts hello" in unwrapped
        assert "puts world" in unwrapped


class TestScriptDiagSummary:
    def test_has_script_chars_and_lines(self):
        script = "# mcp_generated_by=generate_plain_tetra_tcl\nputs hello"
        summary = _script_diag_summary(script)
        assert isinstance(summary, dict)
        assert summary["script_chars"] == 54
        assert summary["script_lines"] == 2

    def test_empty_script(self):
        summary = _script_diag_summary("")
        assert isinstance(summary, dict)
        assert summary["script_chars"] == 0
        assert summary["script_lines"] == 0

    def test_markers_detected(self):
        script = "# MCP_SCRIPT_BEGIN\nputs hello\n# MCP_SCRIPT_END"
        summary = _script_diag_summary(script)
        assert any("MCP_SCRIPT_BEGIN" in m for m in summary["first_markers"])
        assert any("MCP_SCRIPT_END" in m for m in summary["last_markers"])

    def test_truncated_markers(self):
        long_script = "\n".join([f"puts command_{i}" for i in range(20)]) + "\nMCP_END"
        summary = _script_diag_summary(long_script)
        assert len(summary["first_markers"]) <= 8
        assert len(summary["last_markers"]) <= 8


class TestProbeLinesIter:
    def test_none_returns_empty(self):
        assert _probe_lines_iter(None) == []

    def test_empty_string(self):
        assert _probe_lines_iter("") == []

    def test_single_line_string(self):
        assert _probe_lines_iter("hello") == ["hello"]

    def test_multi_line_string(self):
        result = _probe_lines_iter("line1\nline2\nline3")
        assert result == ["line1", "line2", "line3"]

    def test_list_of_strings(self):
        result = _probe_lines_iter(["a", "b", "c"])
        assert result == ["a", "b", "c"]

    def test_tuple_of_strings(self):
        result = _probe_lines_iter(("x", "y"))
        assert result == ["x", "y"]

    def test_list_of_ints_converted(self):
        result = _probe_lines_iter([1, 2, 3])
        assert result == ["1", "2", "3"]

    def test_mixed_list(self):
        result = _probe_lines_iter([1, "abc", None])
        assert result == ["1", "abc", "None"]

    def test_empty_list(self):
        assert _probe_lines_iter([]) == []

    def test_empty_tuple(self):
        assert _probe_lines_iter(()) == []

    def test_trailing_newline(self):
        assert _probe_lines_iter("a\nb\n") == ["a", "b"]

    def test_carriage_return_newline(self):
        result = _probe_lines_iter("a\r\nb")
        assert result == ["a", "b"]
