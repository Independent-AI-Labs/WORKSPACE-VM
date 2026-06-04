"""Unit tests for workspace.utils.banner module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from workspace.utils.banner import (
    _find_pyproject,
    generate_banner_lines,
    generate_banner_text,
    get_project_version,
)


class TestFindPyproject:
    def test_finds_pyproject_in_current_dir(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        assert _find_pyproject(tmp_path) == pyproject

    def test_finds_pyproject_in_parent(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        subdir = tmp_path / "sub" / "deep"
        subdir.mkdir(parents=True)
        assert _find_pyproject(subdir) == pyproject

    def test_find_pyproject_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match=r"pyproject\.toml not found"):
            _find_pyproject(tmp_path)


class TestGetProjectVersion:
    def test_reads_version_from_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "1.2.3"\n')
        version = get_project_version(project_root=tmp_path)
        assert version == "1.2.3"

    def test_uses_file_location_when_no_root(self) -> None:
        version = get_project_version(project_root=None)
        assert isinstance(version, str)
        assert len(version) > 0


class TestGenerateBannerText:
    def test_generates_ascii_art(self) -> None:
        with (
            patch("workspace.utils.banner.get_project_version", return_value="0.1.0"),
            patch("workspace.utils.banner.text2art", return_value="ART"),
        ):
            result = generate_banner_text()
            assert "ART" in result

    def test_trims_empty_lines(self) -> None:
        with (
            patch("workspace.utils.banner.get_project_version", return_value="0.1.0"),
            patch("workspace.utils.banner.text2art", return_value="line1\nline2\n\n\n"),
        ):
            result = generate_banner_text()
            assert result == "line1\nline2"

    def test_custom_font(self) -> None:
        with (
            patch("workspace.utils.banner.get_project_version", return_value="0.1.0"),
            patch("workspace.utils.banner.text2art") as mock_art,
        ):
            mock_art.return_value = "x"
            generate_banner_text(font="big")
            mock_art.assert_called_once()
            assert mock_art.call_args[1]["font"] == "big"


class TestGenerateBannerLines:
    def test_returns_list_of_lines(self) -> None:
        with patch(
            "workspace.utils.banner.generate_banner_text", return_value="A\nB\nC"
        ):
            lines = generate_banner_lines()
            assert lines == ["A", "B", "C"]

    def test_empty_banner(self) -> None:
        with patch("workspace.utils.banner.generate_banner_text", return_value=""):
            lines = generate_banner_lines()
            assert lines == []


class TestMainBlock:
    pass
