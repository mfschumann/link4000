"""Unit tests for path utilities."""

import pytest
from unittest.mock import patch

from link4000.utils.path_utils import (
    is_url,
    is_file_path,
    get_link_type,
    get_file_extension,
    get_parent_folder,
    to_office_uri,
    resolve_unc_path,
    resolve_lnk,
    onedrive_to_sharepoint_url,
    clear_onedrive_cache,
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


class TestGetParentFolder:
    """Tests for get_parent_folder function."""

    def test_unix_path(self):
        """Tests that parent folder is correctly extracted from Unix paths."""
        assert get_parent_folder("/home/user/file.txt") == "/home/user"
        assert get_parent_folder("/home/user/folder/file.txt") == "/home/user/folder"

    def test_windows_drive_letter(self):
        """Tests that parent folder is correctly extracted from Windows drive paths."""
        assert get_parent_folder("C:\\Users\\john\\file.txt") == "C:\\Users\\john"
        assert (
            get_parent_folder("C:\\Users\\john\\folder\\file.txt")
            == "C:\\Users\\john\\folder"
        )

    def test_unc_path(self):
        """Tests that parent folder is correctly extracted from UNC paths."""
        result = get_parent_folder("\\\\server\\share\\folder\\file.txt")
        assert result == "\\\\server\\share\\folder"

    def test_empty_path(self):
        """Tests that an empty path returns an empty string."""
        assert get_parent_folder("") == ""

    def test_root_path(self):
        """Tests that the root path '/' returns '/' as its parent."""
        assert get_parent_folder("/") == "/"


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
            result = resolve_unc_path("/home/user/file.txt")
            assert result == "/home/user/file.txt"

    @patch("sys.platform", "win32")
    @patch("link4000.utils.path_utils._get_unc_for_drive")
    def test_mapped_drive_to_unc(self, mock_get_unc):
        """Tests that a mapped drive letter is resolved to its UNC equivalent."""
        mock_get_unc.return_value = "\\\\fileserver\\share"
        result = resolve_unc_path("Z:\\Docs\\file.txt")
        assert result == "\\\\fileserver\\share\\Docs\\file.txt"

    @patch("sys.platform", "win32")
    @patch("link4000.utils.path_utils._get_unc_for_drive")
    def test_unc_path_unchanged(self, mock_get_unc):
        """Tests that an existing UNC path is returned unchanged on Windows."""
        result = resolve_unc_path("\\\\server\\share\\file.txt")
        assert result == "\\\\server\\share\\file.txt"

    @patch("sys.platform", "win32")
    @patch("link4000.utils.path_utils._get_unc_for_drive")
    def test_local_drive_returns_unchanged(self, mock_get_unc):
        """Tests that a local (non-mapped) drive returns the path unchanged on Windows."""
        mock_get_unc.return_value = None  # Local drive, not mapped
        result = resolve_unc_path("C:\\Users\\file.txt")
        assert result == "C:\\Users\\file.txt"


class TestResolveLnk:
    """Tests for resolve_lnk function."""

    def test_resolves_shortcut_target_and_description(self):
        """Tests that resolve_lnk extracts TargetPath and Description from a .lnk file."""
        import sys
        from pathlib import Path
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
            target, title = resolve_lnk(Path("C:\\Users\\Recent\\report.lnk"))
            assert target == "C:\\Users\\docs\\report.pdf"
            assert title == "Q4 Report"
            mock_shell.CreateShortCut.assert_called_once_with(
                "C:\\Users\\Recent\\report.lnk"
            )

    def test_falls_back_to_stem_when_no_description(self):
        """Tests that resolve_lnk uses the filename stem when Description is empty."""
        import sys
        from pathlib import Path
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
            target, title = resolve_lnk(Path("D:\\Recent\\data.lnk"))
            assert target == "D:\\data.xlsx"
            assert title == "data"

    def test_returns_empty_on_import_error(self):
        """Tests that resolve_lnk returns empty strings when pywin32 is unavailable."""
        import sys
        from pathlib import Path

        with patch.dict(sys.modules, {"win32com": None, "win32com.client": None}):
            target, title = resolve_lnk(Path("C:\\test.lnk"))
            assert target == ""
            assert title == ""

    def test_returns_empty_on_com_error(self):
        """Tests that resolve_lnk returns empty strings on COM errors."""
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.Dispatch.side_effect = Exception("COM error")

        mock_win32com = MagicMock()
        mock_win32com.client = mock_client

        with patch.dict(
            sys.modules,
            {"win32com": mock_win32com, "win32com.client": mock_client},
        ):
            target, title = resolve_lnk(Path("C:\\broken.lnk"))
            assert target == ""
            assert title == ""


# -----------------------------------------------------------------------
# onedrive_to_sharepoint_url
# -----------------------------------------------------------------------

# Shared mount-points fixture used across multiple test classes.
# All paths are stored in normalised form (forward-slash, no trailing /).
_SAMPLE_MOUNTS = [
    (
        "C:/Users/me/OneDrive - Contoso/Projects",
        "https://contoso.sharepoint.com/sites/engineering/Shared Documents/Projects",
    ),
    (
        "C:/Users/me/OneDrive - Contoso",
        "https://contoso-my.sharepoint.com/personal/me_contoso_com/Documents",
    ),
    (
        "D:/Sync/Finance Docs",
        "https://contoso.sharepoint.com/sites/finance/Shared Documents",
    ),
]


class TestOnedriveToSharepointUrl:
    """Tests for onedrive_to_sharepoint_url with explicit mount_points."""

    def test_exact_mount_point(self):
        """Tests that the exact mount-point root returns the URL namespace."""
        result = onedrive_to_sharepoint_url(
            r"C:\Users\me\OneDrive - Contoso\Projects",
            mount_points=_SAMPLE_MOUNTS,
        )
        assert result == (
            "https://contoso.sharepoint.com/sites/engineering"
            "/Shared Documents/Projects"
        )

    def test_file_inside_mount(self):
        """Tests that a file inside a synced library is resolved to a SharePoint URL."""
        result = onedrive_to_sharepoint_url(
            r"C:\Users\me\OneDrive - Contoso\Projects\plan.docx",
            mount_points=_SAMPLE_MOUNTS,
        )
        assert result == (
            "https://contoso.sharepoint.com/sites/engineering"
            "/Shared Documents/Projects/plan.docx"
        )

    def test_nested_folder(self):
        """Tests that nested subfolders are correctly appended."""
        result = onedrive_to_sharepoint_url(
            r"C:\Users\me\OneDrive - Contoso\Projects\sub\deep\file.txt",
            mount_points=_SAMPLE_MOUNTS,
        )
        assert result == (
            "https://contoso.sharepoint.com/sites/engineering"
            "/Shared Documents/Projects/sub/deep/file.txt"
        )

    def test_spaces_in_relative_path(self):
        """Tests that spaces in the relative path are URL-encoded."""
        result = onedrive_to_sharepoint_url(
            r"C:\Users\me\OneDrive - Contoso\Projects\My Report.docx",
            mount_points=_SAMPLE_MOUNTS,
        )
        assert result == (
            "https://contoso.sharepoint.com/sites/engineering"
            "/Shared Documents/Projects/My%20Report.docx"
        )

    def test_special_characters_encoded(self):
        """Tests that special characters in the path are percent-encoded."""
        result = onedrive_to_sharepoint_url(
            r"C:\Users\me\OneDrive - Contoso\Projects\R&D/budget#1.xlsx",
            mount_points=_SAMPLE_MOUNTS,
        )
        assert result == (
            "https://contoso.sharepoint.com/sites/engineering"
            "/Shared Documents/Projects/R%26D/budget%231.xlsx"
        )

    def test_longest_prefix_match(self):
        """Tests that the most specific (longest) mount point wins."""
        # "Projects" is a sub-mount that is longer than the root "OneDrive - Contoso"
        result = onedrive_to_sharepoint_url(
            r"C:\Users\me\OneDrive - Contoso\Projects\plan.docx",
            mount_points=_SAMPLE_MOUNTS,
        )
        # Should use the "Projects" mount, NOT the root mount.
        assert "engineering" in result
        assert "personal" not in result

    def test_no_match(self):
        """Tests that a path outside all mounts returns None."""
        result = onedrive_to_sharepoint_url(
            r"C:\Users\me\Documents\file.txt",
            mount_points=_SAMPLE_MOUNTS,
        )
        assert result is None

    def test_empty_path(self):
        """Tests that an empty path returns None."""
        assert onedrive_to_sharepoint_url("", mount_points=_SAMPLE_MOUNTS) is None

    def test_empty_mount_points(self):
        """Tests that an empty mount-points list returns None."""
        assert onedrive_to_sharepoint_url(r"C:\file.txt", mount_points=[]) is None

    def test_none_mount_points_no_cache(self):
        """Tests that passing None mount_points with no registry returns None."""
        # On Linux the registry reading returns an empty list anyway.
        clear_onedrive_cache()
        result = onedrive_to_sharepoint_url(r"C:\file.txt", mount_points=None)
        assert result is None

    def test_case_insensitive_on_win32(self):
        """Tests that path matching is case-insensitive on Windows."""
        with patch("sys.platform", "win32"):
            result = onedrive_to_sharepoint_url(
                r"c:\users\me\onedrive - contoso\projects\file.txt",
                mount_points=_SAMPLE_MOUNTS,
            )
        assert result is not None
        assert result.endswith("/file.txt")

    def test_case_sensitive_on_linux(self):
        """Tests that path matching is case-sensitive on Linux."""
        with patch("sys.platform", "linux"):
            result = onedrive_to_sharepoint_url(
                r"c:\users\me\onedrive - contoso\projects\file.txt",
                mount_points=_SAMPLE_MOUNTS,
            )
        # Lowercase c: won't match uppercase C: on Linux.
        assert result is None

    def test_unix_path_no_match(self):
        """Tests that Unix paths do not match Windows mount points."""
        result = onedrive_to_sharepoint_url(
            "/home/user/file.txt",
            mount_points=_SAMPLE_MOUNTS,
        )
        assert result is None

    def test_trailing_slash_in_input(self):
        """Tests that a trailing slash on the input path is handled."""
        result = onedrive_to_sharepoint_url(
            "C:\\Users\\me\\OneDrive - Contoso\\Projects\\",
            mount_points=_SAMPLE_MOUNTS,
        )
        # Exact mount point match (trailing slash stripped).
        assert result == (
            "https://contoso.sharepoint.com/sites/engineering"
            "/Shared Documents/Projects"
        )

    def test_url_encoding_of_percent(self):
        """Tests that literal percent signs in the path are double-encoded."""
        result = onedrive_to_sharepoint_url(
            r"C:\Users\me\OneDrive - Contoso\Projects\50%sale.txt",
            mount_points=_SAMPLE_MOUNTS,
        )
        assert result is not None
        assert "50%25sale.txt" in result


class TestClearOnedriveCache:
    """Tests for clear_onedrive_cache."""

    def test_clear_resets_cache(self):
        """Tests that clearing the cache causes it to be repopulated on next access."""
        from link4000.utils import path_utils as pu

        pu._onedrive_mount_cache = [("dummy", "https://example.com")]
        clear_onedrive_cache()
        assert pu._onedrive_mount_cache is None


class TestReadOnedriveMountPoints:
    """Tests for _read_onedrive_mount_points with mocked registry."""

    @patch("sys.platform", "win32")
    def test_reads_registry_entries(self):
        """Tests that registry entries are read and sorted by length descending."""
        import types

        from link4000.utils.path_utils import _read_onedrive_mount_points

        # Fake winreg module.
        fake_winreg = types.ModuleType("winreg")
        fake_winreg.HKEY_CURRENT_USER = 0x80000001

        subkey_names = ["abc123", "def456", "ghi789"]
        subkey_data = {
            "abc123": {
                "MountPoint": r"C:\Users\me\OneDrive - Contoso\Team",
                "UrlNamespace": "https://contoso.sharepoint.com/sites/team/Shared Documents",
            },
            "def456": {
                "MountPoint": r"C:\Users\me\OneDrive - Contoso",
                "UrlNamespace": "https://contoso-my.sharepoint.com/personal/me_contoso_com/Documents",
            },
            "ghi789": {
                "MountPoint": "",
                "UrlNamespace": "https://example.com/empty",
            },
        }

        def fake_enum_key(key, idx):
            if isinstance(key, str):
                names = subkey_names
            else:
                names = getattr(key, "_names", [])
            if idx >= len(names):
                raise OSError
            return names[idx]

        def fake_open_key(parent, name, reserved=0, access=0):
            if isinstance(name, str) and "SyncEngines" in name:
                # Base key.
                class BaseKey:
                    _names = subkey_names

                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        pass

                return BaseKey()
            # Sub-key.
            data = subkey_data.get(name, {})

            class SubKey:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    pass

            sk = SubKey()
            sk._data = data
            return sk

        def fake_query_value(key, name):
            return key._data.get(name, ""), 0

        fake_winreg.OpenKey = fake_open_key
        fake_winreg.EnumKey = fake_enum_key
        fake_winreg.QueryValueEx = fake_query_value

        import sys as _sys

        original_winreg = _sys.modules.get("winreg")
        _sys.modules["winreg"] = fake_winreg
        try:
            result = _read_onedrive_mount_points()
        finally:
            if original_winreg is not None:
                _sys.modules["winreg"] = original_winreg
            else:
                _sys.modules.pop("winreg", None)

        # Empty mount-point entry should be excluded.
        assert len(result) == 2
        # Longest mount-point first.
        assert len(result[0][0]) >= len(result[1][0])
        # Correct normalisation (backslash -> forward-slash).
        assert "\\" not in result[0][0]
        assert "\\" not in result[1][0]

    @patch("sys.platform", "linux")
    def test_returns_empty_on_non_windows(self):
        """Tests that _read_onedrive_mount_points returns [] on non-Windows."""
        from link4000.utils.path_utils import _read_onedrive_mount_points

        result = _read_onedrive_mount_points()
        assert result == []

    @patch("sys.platform", "win32")
    def test_handles_registry_error(self):
        """Tests that a registry error is handled gracefully."""
        import types

        from link4000.utils.path_utils import _read_onedrive_mount_points

        fake_winreg = types.ModuleType("winreg")
        fake_winreg.HKEY_CURRENT_USER = 0x80000001
        fake_winreg.OpenKey = None  # will raise when called

        import sys as _sys

        original_winreg = _sys.modules.get("winreg")
        _sys.modules["winreg"] = fake_winreg
        try:
            result = _read_onedrive_mount_points()
        finally:
            if original_winreg is not None:
                _sys.modules["winreg"] = original_winreg
            else:
                _sys.modules.pop("winreg", None)

        assert result == []
