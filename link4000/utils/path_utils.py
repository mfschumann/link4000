"""Utilities for URL/file-path detection and Windows network drive resolution."""

import os
import re
import sys
import urllib.parse
from pathlib import Path, PurePath
from typing import Optional

from link4000.utils.config import get_exclusion_patterns, get_sharepoint_patterns

# Module-level cache: drive letter (uppercase) -> UNC root, or None if local/unknown
_drive_unc_cache: dict[str, Optional[str]] = {}

# Office URI scheme mapping: extension -> scheme prefix
_OFFICE_SCHEMES = {
    ".doc": "ms-word:ofv|u|",
    ".docx": "ms-word:ofv|u|",
    ".xls": "ms-excel:ofv|u|",
    ".xlsx": "ms-excel:ofv|u|",
    ".ppt": "ms-powerpoint:ofv|u|",
    ".pptx": "ms-powerpoint:ofv|u|",
    ".vsdx": "ms-visio:ofv|u|",
    ".accdb": "ms-access:ofv|u|",
    ".mpp": "ms-project:ofv|u|",
    ".pub": "ms-publisher:ofv|u|",
}


def is_url(text: str) -> bool:
    """Return True if *text* looks like a URL (has a scheme like http://, ftp://, …)."""
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", text))


def is_file_path(text: str) -> bool:
    """
    Return True if *text* looks like a local or network file-system path.

    Recognises:
    - Unix absolute paths:      ``/…``
    - UNC paths:                ``\\\\server\\share`` or ``//server/share``
    - Windows absolute paths:   ``C:\\…`` or ``C:/…``
    """
    if not text:
        return False
    # Unix absolute path
    if text.startswith("/"):
        return True
    # UNC path (forward- or back-slash variants)
    if text.startswith("\\\\") or text.startswith("//"):
        return True
    # Windows drive-letter path
    if re.match(r"^[A-Za-z]:[/\\]", text):
        return True
    return False


def is_sharepoint_url(url: str) -> bool:
    """
    Return True if the URL matches any of the configured SharePoint patterns.
    """
    if not is_url(url):
        return False

    patterns = get_sharepoint_patterns()
    for pattern in patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def matches_exclusion_pattern(url_or_path: str) -> bool:
    """
    Return True if the URL or path matches any of the configured exclusion patterns.

    Uses pathlib.PurePath.full_match with glob patterns. Patterns should use
    glob syntax (e.g., "*.txt", "**/temp/**") rather than regex syntax.
    No path normalization is performed - patterns must match the exact path format.
    """
    if not url_or_path:
        return False

    patterns = get_exclusion_patterns()
    if not patterns:
        return False

    path = PurePath(url_or_path)
    for pattern in patterns:
        if path.full_match(pattern):
            return True
    return False


def get_sharepoint_file_extension(url: str) -> str:
    """
    Extract the file extension from a SharePoint URL's path.
    Returns the extension (lowercase, with leading dot) or empty string if none.
    """
    if not is_sharepoint_url(url):
        return ""

    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)

    ext = Path(path).suffix
    return ext.lower()


def get_office_scheme(extension: str) -> str | None:
    """
    Return the Office URI scheme prefix for the given file extension,
    or None if the extension is not a known Office type.
    """
    return _OFFICE_SCHEMES.get(extension.lower())


def to_office_uri(url: str) -> str | None:
    """
    Convert a SharePoint file URL to an Office URI scheme on Windows.
    Returns None if not on Windows, not a SharePoint URL, or not an Office file.
    """
    if sys.platform != "win32":
        return None

    if not is_sharepoint_url(url):
        return None

    ext = get_sharepoint_file_extension(url)
    if not ext:
        return None

    scheme = get_office_scheme(ext)
    if not scheme:
        return None

    return f"{scheme}{url}"


def _resolve_unc_path(path: str) -> str:
    """
    On Windows, if *path* starts with a mapped drive letter, replace the drive
    letter with its UNC equivalent and return the resolved path.

    The drive→UNC mapping is cached at module level so each drive is only
    queried once per process.  On non-Windows platforms, or for paths that are
    already UNC / local drives, the path is returned unchanged.

    Example::

        _resolve_unc_path(r"Z:\\Reports\\Q1.xlsx")
        # → r"\\\\fileserver\\Finance\\Reports\\Q1.xlsx"
    """
    if sys.platform != "win32":
        return path

    match = re.match(r"^([A-Za-z]):(.*)", path)
    if not match:
        # Already UNC or not a drive-letter path
        return path

    drive_letter = match.group(1).upper()
    rest = match.group(2)  # e.g. \Reports\Q1.xlsx

    if drive_letter not in _drive_unc_cache:
        _drive_unc_cache[drive_letter] = _get_unc_for_drive(drive_letter)

    unc_root = _drive_unc_cache[drive_letter]
    if unc_root:
        # Use string concatenation to preserve Windows path separators
        return unc_root + rest
    return path


def _resolve_lnk(lnk_path: Path) -> tuple[str, str]:
    """Resolve a Windows .lnk shortcut file to its target path and description.

    Uses ``win32com.client`` (pywin32) to read the shortcut's target and
    description.  Returns empty strings on non-Windows platforms or when
    resolution fails (e.g. missing pywin32, corrupt shortcut).

    Args:
        lnk_path: Path to the ``.lnk`` file.

    Returns:
        A ``(target_path, description)`` tuple.  Both are empty strings on
        failure.
    """
    try:
        import win32com.client
    except Exception as e:
        print(f"_resolve_lnk import error: {e}", file=sys.stderr)
        return "", ""

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(lnk_path))
        target = shortcut.TargetPath
        # Normalize backslashes so Path.stem works on non-Windows platforms
        # (lnk_path.stem treats backslash as filename char on Linux).
        title = shortcut.Description or Path(lnk_path.name.replace("\\", "/")).stem

        return target, title
    except Exception as e:
        print(f"_resolve_lnk({lnk_path.name}) exception: {e}", file=sys.stderr)
        return "", ""


def get_link_type(url: str) -> str:
    """
    Return the type of the link: "web", "folder", "file", "sharepoint", or "unknown".

    A "web" link has a URL scheme (http://, https://, etc.) that is not SharePoint.
    A "folder" link is a file path that exists and is a directory.
    A "file" link is a file path that exists and is a regular file,
    OR a file path with an extension (even if it doesn't exist yet),
    OR a SharePoint URL with a file extension.
    A "sharepoint" link is a SharePoint URL without a file extension.
    An "unknown" link is a bare path without extension that doesn't exist.
    """
    if is_url(url):
        if is_sharepoint_url(url):
            ext = get_sharepoint_file_extension(url)
            if ext:
                return "file"
            return "sharepoint"
        return "web"

    if is_file_path(url):
        resolved = _resolve_unc_path(url) if sys.platform == "win32" else url
        if os.path.isdir(resolved):
            return "folder"
        if os.path.isfile(resolved):
            return "file"
        ext = get_file_extension(url)
        if ext:
            return "file"
        return "unknown"

    return "unknown"


def get_file_extension(url: str) -> str:
    """
    Return the file extension (including the leading dot) for a file path,
    or an empty string if the URL has no extension or is a non-SharePoint web URL.
    """
    if is_sharepoint_url(url):
        return get_sharepoint_file_extension(url)

    if is_url(url):
        return ""

    ext = Path(url).suffix
    return ext.lower()


def is_folder(url: str) -> bool:
    """Return True if the URL is a file path pointing to an existing directory."""
    if is_file_path(url):
        resolved = _resolve_unc_path(url) if sys.platform == "win32" else url
        if os.path.isdir(resolved):
            return True
    return False


def _get_unc_for_drive(drive_letter: str) -> Optional[str]:
    """
    Call ``WNetGetConnectionW`` via *ctypes* to retrieve the UNC share name
    for a mapped drive letter (e.g. ``Z:`` → ``\\\\fileserver\\Finance``).

    Returns the UNC root string on success, or ``None`` if the drive is not a
    mapped network drive or the query fails.
    """
    try:
        import ctypes

        drive = f"{drive_letter}:"
        buf_size = ctypes.c_ulong(1024)
        buf = ctypes.create_unicode_buffer(1024)

        # ERROR_CONNECTION_UNAVAIL (0x48F) and ERROR_NOT_CONNECTED (0x8CA) are
        # returned for local/unknown drives; NO_ERROR (0) means success.
        result = ctypes.windll.mpr.WNetGetConnectionW(
            drive,
            buf,
            ctypes.byref(buf_size),
        )

        if result == 0:  # NO_ERROR
            unc = buf.value
            return unc if unc else None
    except Exception:
        pass
    return None


def resolve_path(path: str) -> tuple[str, str]:
    """
    Resolve a path through all platform-specific transformations.

    Handles:
    - Windows .lnk shortcut resolution
    - Linux/Unix symlink resolution
    - Windows mapped drive to UNC path conversion

    Args:
        path: The input path string (URL or file path).

    Returns:
        A (resolved_path, title) tuple. Title is derived from .lnk description
        or symlink target name; empty string if not applicable.
    """
    if not path:
        return "", ""

    # Use pathlib for path handling based on platform
    if sys.platform == "win32":
        path_obj = Path(path)
    else:
        path_obj = Path(path)

    title = ""

    # Step 1: Resolve Windows .lnk shortcuts
    if sys.platform == "win32" and path.lower().endswith(".lnk"):
        target, lnk_title = _resolve_lnk(path_obj)
        if target:
            path = target
            title = lnk_title or ""
            # Update path_obj for further resolution
            path_obj = Path(path)

    # Step 2: Resolve symlinks (works on both Windows and Linux)
    try:
        if path_obj.is_symlink():
            target = path_obj.readlink()
            # Convert to string, preserving absolute vs relative
            if target.is_absolute():
                path = str(target)
            else:
                path = str(path_obj.parent / target)
            path_obj = Path(path)
    except (OSError, ValueError):
        pass  # Not a symlink or cannot read

    # Step 3: Resolve mapped drive to UNC on Windows
    if sys.platform == "win32" and is_file_path(path):
        path = _resolve_unc_path(path)

    return path, title
