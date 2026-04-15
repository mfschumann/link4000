"""Unit tests for path utilities."""

import pytest
from unittest.mock import patch

from link4000.utils.path_utils import (
    is_url,
    is_file_path,
    get_link_type,
    get_file_extension,
    to_office_uri,
    resolve_path,
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


class TestResolvePath:
    """Tests for resolve_path function."""

    def test_empty_path_returns_empty(self):
        """Tests that an empty path returns empty strings."""
        result = resolve_path("")
        assert result == ("", "")

    def test_url_unchanged(self):
        """Tests that URLs are returned unchanged."""
        result = resolve_path("https://example.com/file.pdf")
        assert result == ("https://example.com/file.pdf", "")

    def test_non_file_path_unchanged(self):
        """Tests that non-file paths are returned unchanged."""
        result = resolve_path("relative/path/file.txt")
        assert result == ("relative/path/file.txt", "")

    @patch("link4000.utils.path_utils._resolve_lnk")
    @patch("link4000.utils.path_utils.Path.is_symlink", return_value=False)
    def test_lnk_resolution_on_windows(self, mock_symlink, mock_lnk):
        """Tests that .lnk files are resolved on Windows."""
        import sys

        with patch.object(sys, "platform", "win32"):
            mock_lnk.return_value = ("C:\\Target\\file.pdf", "My PDF")
            result = resolve_path("C:\\Shortcuts\\file.lnk")
            assert result == ("C:\\Target\\file.pdf", "My PDF")
            mock_lnk.assert_called_once()

    @patch("link4000.utils.path_utils._resolve_lnk")
    @patch("link4000.utils.path_utils.Path.is_symlink", return_value=False)
    def test_lnk_not_resolved_on_linux(self, mock_symlink, mock_lnk):
        """Tests that .lnk files are not resolved on Linux."""
        import sys

        with patch.object(sys, "platform", "linux"):
            result = resolve_path("/home/user/shortcut.lnk")
            assert result == ("/home/user/shortcut.lnk", "")
            mock_lnk.assert_not_called()

    @patch("link4000.utils.path_utils._resolve_unc_path")
    @patch("link4000.utils.path_utils.Path.is_symlink", return_value=False)
    def test_unc_resolution_on_windows(self, mock_symlink, mock_unc):
        """Tests that UNC path resolution is called on Windows."""
        import sys

        with patch.object(sys, "platform", "win32"):
            mock_unc.return_value = "\\\\server\\share\\file.txt"
            result = resolve_path("Z:\\file.txt")
            assert result == ("\\\\server\\share\\file.txt", "")
            mock_unc.assert_called_once_with("Z:\\file.txt")

    @patch("link4000.utils.path_utils._resolve_unc_path")
    @patch("link4000.utils.path_utils.Path.is_symlink", return_value=False)
    def test_unc_not_resolved_on_linux(self, mock_symlink, mock_unc):
        """Tests that UNC path resolution is not called on Linux."""
        import sys

        with patch.object(sys, "platform", "linux"):
            result = resolve_path("/mnt/share/file.txt")
            assert result == ("/mnt/share/file.txt", "")
            mock_unc.assert_not_called()

    @patch("link4000.utils.path_utils._resolve_lnk")
    @patch("link4000.utils.path_utils.Path.is_symlink", return_value=True)
    @patch("pathlib.Path.readlink")
    def test_symlink_resolution(self, mock_readlink, mock_is_link, mock_lnk):
        """Tests that symlinks are resolved."""
        import sys
        from pathlib import Path

        mock_readlink.return_value = Path("/actual/target/file.txt")

        with patch.object(sys, "platform", "linux"):
            result = resolve_path("/home/user/link")
            assert result[0] == "/actual/target/file.txt"

    @patch("link4000.utils.path_utils._resolve_lnk", return_value=("", ""))
    @patch("pathlib.Path.is_symlink", return_value=False)
    @patch("link4000.utils.path_utils._resolve_unc_path")
    def test_lnk_followed_by_unc(self, mock_unc, mock_is_link, mock_lnk):
        """Tests that .lnk resolution is followed by UNC resolution."""
        import sys

        mock_lnk.return_value = ("Z:\\target\\file.pdf", "Report")
        mock_unc.return_value = "\\\\server\\share\\file.pdf"

        with patch.object(sys, "platform", "win32"):
            result = resolve_path("C:\\shortcut.lnk")
            assert result == ("\\\\server\\share\\file.pdf", "Report")
