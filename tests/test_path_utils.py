"""Unit tests for path utilities."""
from pathlib import PureWindowsPath, PurePosixPath

import pytest
from unittest.mock import patch

from link4000.utils.path_utils import (
    is_url,
    is_file_path,
    get_link_type,
    get_file_extension,
    to_office_uri,
    resolve_unc_path,
    resolve_lnk,
    matches_exclusion_pattern,
)


class TestIsUrl:
    """Tests for is_url function."""

    def test_http_url(self):
        """Tests that http and https URLs are recognized as URLs."""
        assert is_url("http://example.com") is True
        assert is_url("https://example.com") is True

    def test_ftp_url(self):
        """Tests that ftp URLs are recognized as URLs."""
        assert is_url("ftp://ftp.example.com") is True

    def test_file_path(self):
        """Tests that Unix and Windows file paths are not recognized as URLs."""
        assert is_url("/home/user/file.txt") is False
        assert is_url("C:\\Users\\file.txt") is False

    def test_relative_path(self):
        """Tests that relative paths are not recognized as URLs."""
        assert is_url("some/path/file.txt") is False


class TestIsFilePath:
    """Tests for is_file_path function."""

    def test_unix_absolute_path(self):
        """Tests that Unix absolute paths are recognized as file paths."""
        assert is_file_path("/home/user/file.txt") is True
        assert is_file_path("/home/user/") is True

    def test_windows_drive_letter(self):
        """Tests that Windows drive letter paths are recognized as file paths."""
        assert is_file_path("C:\\Users\\file.txt") is True
        assert is_file_path("C:/Users/file.txt") is True
        assert is_file_path("D:\\") is True

    def test_unc_path(self):
        """Tests that UNC paths are recognized as file paths."""
        assert is_file_path("\\\\server\\share\\file.txt") is True
        assert is_file_path("//server/share/file.txt") is True

    def test_url(self):
        """Tests that URLs are not recognized as file paths."""
        assert is_file_path("https://example.com") is False
        assert is_file_path("http://example.com") is False

    def test_relative_path(self):
        """Tests that relative paths are not recognized as file paths."""
        assert is_file_path("relative/path") is False


class TestGetLinkType:
    """Tests for get_link_type function."""

    def test_web_url(self):
        """Tests that http, https, and ftp URLs are classified as 'web' links."""
        assert get_link_type("https://example.com") == "web"
        assert get_link_type("http://example.com") == "web"
        assert get_link_type("ftp://example.com") == "web"

    @patch("link4000.utils.path_utils.is_sharepoint_url", return_value=True)
    def test_sharepoint_url(self, mock_sp):
        """Tests that a SharePoint URL without a file extension is classified as 'sharepoint'."""
        # SharePoint URL without extension
        result = get_link_type("https://company.sharepoint.com/sites/test")
        assert result == "sharepoint"

    @patch("link4000.utils.path_utils.is_sharepoint_url", return_value=True)
    def test_sharepoint_file(self, mock_sp):
        """Tests that a SharePoint URL with a file extension is classified as 'file'."""
        # SharePoint URL with file extension
        result = get_link_type("https://company.sharepoint.com/sites/test/doc.docx")
        assert result == "file"

    @patch("os.path.isdir")
    @patch("os.path.isfile")
    def test_existing_folder(self, mock_isfile, mock_isdir):
        """Tests that an existing directory path is classified as 'folder'."""
        mock_isdir.return_value = True
        mock_isfile.return_value = False
        result = get_link_type("/home/user/folder")
        assert result == "folder"

    @patch("os.path.isdir")
    @patch("os.path.isfile")
    def test_existing_file(self, mock_isfile, mock_isdir):
        """Tests that an existing file path is classified as 'file'."""
        mock_isdir.return_value = False
        mock_isfile.return_value = True
        result = get_link_type("/home/user/file.txt")
        assert result == "file"

    def test_path_with_extension(self):
        """Tests that a path with a file extension is classified as 'file'."""
        result = get_link_type("/home/user/document.pdf")
        assert result == "file"

    def test_unknown_path(self):
        """Tests that a nonexistent path without extension is classified as 'unknown'."""
        result = get_link_type("/nonexistent/path")
        assert result == "unknown"


class TestGetFileExtension:
    """Tests for get_file_extension function."""

    def test_file_path_with_extension(self):
        """Tests that file extensions are extracted and lowercased from file paths."""
        assert get_file_extension("/home/user/file.txt") == ".txt"
        assert get_file_extension("/home/user/file.PDF") == ".pdf"

    def test_file_path_no_extension(self):
        """Tests that paths without an extension return an empty string."""
        assert get_file_extension("/home/user/folder") == ""

    def test_url_no_extension(self):
        """Tests that URLs without a file extension return an empty string."""
        assert get_file_extension("https://example.com") == ""

    @patch("link4000.utils.path_utils.is_sharepoint_url", return_value=True)
    @patch(
        "link4000.utils.path_utils.get_sharepoint_file_extension", return_value=".docx"
    )
    def test_sharepoint_file_extension(self, mock_sp_ext, mock_sp):
        """Tests that SharePoint file extensions are extracted via the dedicated helper."""
        result = get_file_extension("https://company.sharepoint.com/file.docx")
        assert result == ".docx"


class TestToOfficeUri:
    """Tests for to_office_uri function."""

    @pytest.mark.skipif(
        not __import__("sys").platform.startswith("win"), reason="Windows only"
    )
    @patch("link4000.utils.path_utils.is_sharepoint_url", return_value=True)
    def test_office_file_windows(self, mock_sp):
        """Tests that a SharePoint Office file returns a ms-office URI on Windows."""
        url = "https://company.sharepoint.com/sites/doc.docx"
        result = to_office_uri(url)
        assert result is not None
        assert url in result

    def test_non_windows_platform(self):
        """Tests that to_office_uri returns None on non-Windows platforms."""
        with patch("sys.platform", "linux"):
            result = to_office_uri("https://example.com/doc.docx")
            assert result is None

    def test_non_sharepoint_url(self):
        """Tests that to_office_uri returns None for non-SharePoint URLs."""
        result = to_office_uri("https://example.com/doc.docx")
        assert result is None


class TestResolveUncPath:
    """Tests for resolve_unc_path function."""

    def test_non_windows_returns_unchanged(self):
        """Tests that resolve_unc_path returns the path unchanged on non-Windows."""
        with patch("sys.platform", "linux"):
            result = resolve_unc_path(PurePosixPath("/home/user/file.txt"))
            assert result == PurePosixPath("/home/user/file.txt")

    @patch("sys.platform", "win32")
    @patch("link4000.utils.path_utils._get_unc_for_drive")
    def test_mapped_drive_to_unc(self, mock_get_unc):
        """Tests that a mapped drive letter is resolved to its UNC equivalent."""
        mock_get_unc.return_value = "\\\\fileserver\\share"
        result = resolve_unc_path(PureWindowsPath("Z:\\Docs\\file.txt"))
        assert result == PureWindowsPath("\\\\fileserver\\share\\Docs\\file.txt")

    @patch("sys.platform", "win32")
    @patch("link4000.utils.path_utils._get_unc_for_drive")
    def test_unc_path_unchanged(self, mock_get_unc):
        """Tests that an existing UNC path is returned unchanged on Windows."""
        result = resolve_unc_path(PureWindowsPath("\\\\server\\share\\file.txt"))
        assert result == PureWindowsPath("\\\\server\\share\\file.txt")

    @patch("sys.platform", "win32")
    @patch("link4000.utils.path_utils._get_unc_for_drive")
    def test_local_drive_returns_unchanged(self, mock_get_unc):
        """Tests that a local (non-mapped) drive returns the path unchanged on Windows."""
        mock_get_unc.return_value = None  # Local drive, not mapped
        result = resolve_unc_path(PureWindowsPath("C:\\Users\\file.txt"))
        assert result == PureWindowsPath("C:\\Users\\file.txt")


class TestResolveLnk:
    """Tests for resolve_lnk function."""

    def test_resolves_shortcut_target_and_description(self):
        """Tests that resolve_lnk extracts TargetPath and Description from a .lnk file."""
        import sys
        from pathlib import PureWindowsPath
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_shortcut = MagicMock()
        mock_shortcut.TargetPath = "C:\\Users\\docs\\report.pdf"
        mock_shortcut.Description = "Q4 Report"
        mock_shell = MagicMock()
        mock_shell.CreateShortCut.return_value = mock_shortcut
        mock_client.Dispatch.return_value = mock_shell

        mock_win32com = MagicMock()
        mock_win32com.client = mock_client

        with patch.dict(
            sys.modules,
            {"win32com": mock_win32com, "win32com.client": mock_client},
        ):
            target, title = resolve_lnk(PureWindowsPath("C:\\Users\\Recent\\report.lnk"))
            assert target == "C:\\Users\\docs\\report.pdf"
            assert title == "Q4 Report"
            mock_shell.CreateShortCut.assert_called_once_with(
                "C:\\Users\\Recent\\report.lnk"
            )

    def test_falls_back_to_stem_when_no_description(self):
        """Tests that resolve_lnk uses the filename stem when Description is empty."""
        import sys
        from pathlib import PureWindowsPath
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_shortcut = MagicMock()
        mock_shortcut.TargetPath = "D:\\data.xlsx"
        mock_shortcut.Description = ""
        mock_shell = MagicMock()
        mock_shell.CreateShortCut.return_value = mock_shortcut
        mock_client.Dispatch.return_value = mock_shell

        mock_win32com = MagicMock()
        mock_win32com.client = mock_client

        with patch.dict(
            sys.modules,
            {"win32com": mock_win32com, "win32com.client": mock_client},
        ):
            target, title = resolve_lnk(PureWindowsPath("D:\\Recent\\data.lnk"))
            assert target == "D:\\data.xlsx"
            assert title == "data"

    def test_returns_empty_on_import_error(self):
        """Tests that resolve_lnk returns empty strings when pywin32 is unavailable."""
        import sys
        from pathlib import PureWindowsPath

        with patch.dict(sys.modules, {"win32com": None, "win32com.client": None}):
            target, title = resolve_lnk(PureWindowsPath("C:\\test.lnk"))
            assert target == ""
            assert title == ""

    def test_returns_empty_on_com_error(self):
        """Tests that resolve_lnk returns empty strings on COM errors."""
        import sys
        from pathlib import PureWindowsPath
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.Dispatch.side_effect = Exception("COM error")

        mock_win32com = MagicMock()
        mock_win32com.client = mock_client

        with patch.dict(
            sys.modules,
            {"win32com": mock_win32com, "win32com.client": mock_client},
        ):
            target, title = resolve_lnk(PureWindowsPath("C:\\broken.lnk"))
            assert target == ""
            assert title == ""


class TestMatchesExclusionPattern:
    """Tests for matches_exclusion_pattern function."""

    @patch("link4000.utils.path_utils.get_exclusion_patterns")
    def test_matches_pattern(self, mock_get_patterns):
        """Test that URL matching pattern returns True."""
        mock_get_patterns.return_value = ["**/*.internal.company.com/*"]
        assert (
            matches_exclusion_pattern("https://server.internal.company.com/file")
            is True
        )

    @patch("link4000.utils.path_utils.get_exclusion_patterns")
    def test_no_match(self, mock_get_patterns):
        """Test that non-matching URL returns False."""
        mock_get_patterns.return_value = ["*internal.company.com/*"]
        assert matches_exclusion_pattern("https://example.com/file") is False

    @patch("link4000.utils.path_utils.get_exclusion_patterns")
    def test_multiple_patterns(self, mock_get_patterns):
        """Test multiple patterns - first match wins."""
        mock_get_patterns.return_value = ["**/temp/**", "**/private/*"]
        assert matches_exclusion_pattern("C:/temp/file.txt") is True

    @patch("link4000.utils.path_utils.get_exclusion_patterns")
    def test_empty_patterns(self, mock_get_patterns):
        """Test that empty patterns list returns False."""
        mock_get_patterns.return_value = []
        assert matches_exclusion_pattern("https://example.com") is False

    @patch("link4000.utils.path_utils.get_exclusion_patterns")
    def test_empty_input(self, mock_get_patterns):
        """Test that empty input returns False."""
        mock_get_patterns.return_value = ["*"]
        assert matches_exclusion_pattern("") is False
