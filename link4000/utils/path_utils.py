"""Utilities for URL/file-path detection and Windows network drive resolution."""

import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Optional

from link4000.utils.config import get_sharepoint_patterns

# Module-level cache: drive letter (uppercase) -> UNC root, or None if local/unknown
_drive_unc_cache: dict[str, Optional[str]] = {}

# Module-level cache for OneDrive sync mount-point -> SharePoint URL mappings.
# Each entry is (normalized_mount_point, url_namespace).  Populated once per
# process from the Windows registry key
# HKCU\SOFTWARE\SyncEngines\Providers\OneDrive.
_onedrive_mount_cache: Optional[list[tuple[str, str]]] = None

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


def get_sharepoint_file_extension(url: str) -> str:
    """
    Extract the file extension from a SharePoint URL's path.
    Returns the extension (lowercase, with leading dot) or empty string if none.
    """
    if not is_sharepoint_url(url):
        return ""

    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)

    _, ext = os.path.splitext(path)
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


def resolve_unc_path(path: str) -> str:
    """
    On Windows, if *path* starts with a mapped drive letter, replace the drive
    letter with its UNC equivalent and return the resolved path.

    The drive→UNC mapping is cached at module level so each drive is only
    queried once per process.  On non-Windows platforms, or for paths that are
    already UNC / local drives, the path is returned unchanged.

    Example::

        resolve_unc_path(r"Z:\\Reports\\Q1.xlsx")
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
        return unc_root + rest
    return path


def resolve_lnk(lnk_path: Path) -> tuple[str, str]:
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
        print(f"resolve_lnk import error: {e}", file=sys.stderr)
        return "", ""

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(lnk_path))
        target = shortcut.TargetPath
        # Normalize backslashes so Path.stem works on non-Windows platforms
        # (lnk_path.stem treats backslash as filename char on Linux).
        title = shortcut.Description or Path(
            lnk_path.name.replace("\\", "/")
        ).stem

        return target, title
    except Exception as e:
        print(f"resolve_lnk({lnk_path.name}) exception: {e}", file=sys.stderr)
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
        resolved = resolve_unc_path(url) if sys.platform == "win32" else url
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

    _, ext = os.path.splitext(url)
    return ext.lower()


def is_folder(url: str) -> bool:
    """Return True if the URL is a file path pointing to an existing directory."""
    if is_file_path(url):
        resolved = resolve_unc_path(url) if sys.platform == "win32" else url
        if os.path.isdir(resolved):
            return True
    return False


def get_parent_folder(path: str) -> str:
    """
    Return the parent folder of the given path, handling:
    - Unix paths: /home/user/folder/file.txt → /home/user/folder
    - Windows drive letters: C:\\Users\\john\\file.txt → C:\\Users\\john
    - UNC paths: \\\\server\\share\\folder\\file.txt → \\\\server\\share\\folder
    """
    if not path:
        return ""

    # Normalize the path separators for consistent handling
    normalized = path.replace("/", "\\")

    # UNC path: \\server\share\folder\file.txt
    if normalized.startswith("\\\\"):
        parts = normalized.split("\\")
        if len(parts) >= 4:
            return "\\".join(parts[:-1])
        return normalized

    # Windows drive letter: C:\Users\john\file.txt
    if len(normalized) >= 3 and normalized[1] == ":" and normalized[2] == "\\":
        return "\\".join(normalized.split("\\")[:-1])

    # Unix path
    return os.path.dirname(path)


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


# ---------------------------------------------------------------------------
# OneDrive / SharePoint local-path -> URL conversion
# ---------------------------------------------------------------------------


def _read_onedrive_mount_points() -> list[tuple[str, str]]:
    """Read OneDrive sync mount-point to SharePoint URL mappings from the
    Windows registry.

    Scans ``HKCU\\SOFTWARE\\SyncEngines\\Providers\\OneDrive`` and each of its
    sub-keys.  Every sub-key that has both a non-empty *MountPoint* and a
    *UrlNamespace* value is included in the result.

    On non-Windows platforms the function returns an empty list.

    Returns:
        A list of ``(normalized_mount_point, url_namespace)`` tuples sorted
        by mount-point length descending so that the most specific match is
        tried first by :func:`onedrive_to_sharepoint_url`.
    """
    if sys.platform != "win32":
        return []

    try:
        import winreg

        base_key_path = r"SOFTWARE\SyncEngines\Providers\OneDrive"
        entries: list[tuple[str, str]] = []

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_key_path) as base_key:
            idx = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(base_key, idx)
                except OSError:
                    break
                idx += 1

                try:
                    with winreg.OpenKey(base_key, subkey_name) as subkey:
                        mount_point, _ = winreg.QueryValueEx(subkey, "MountPoint")
                        url_namespace, _ = winreg.QueryValueEx(
                            subkey, "UrlNamespace"
                        )
                except OSError:
                    continue

                if not mount_point or not url_namespace:
                    continue

                # Normalise backslashes and strip trailing separator.
                norm = mount_point.replace("\\", "/").rstrip("/")
                entries.append((norm, url_namespace.rstrip("/")))

        # Longest mount-point first → most specific match wins.
        entries.sort(key=lambda e: len(e[0]), reverse=True)
        return entries
    except Exception:
        return []


def _get_onedrive_mount_points() -> list[tuple[str, str]]:
    """Return cached OneDrive mount-point mappings, populating the cache on
    first access.

    Returns:
        A list of ``(normalized_mount_point, url_namespace)`` tuples.
    """
    global _onedrive_mount_cache
    if _onedrive_mount_cache is None:
        _onedrive_mount_cache = _read_onedrive_mount_points()
    return _onedrive_mount_cache


def onedrive_to_sharepoint_url(
    local_path: str,
    *,
    mount_points: Optional[list[tuple[str, str]]] = None,
) -> Optional[str]:
    """Convert a local OneDrive / SharePoint-synced file path to a SharePoint
    URL.

    The function looks up the Windows registry (or *mount_points* if given) for
    synced library mappings.  When *local_path* falls inside a known mount
    point the remaining relative path is URL-encoded and appended to the
    corresponding SharePoint URL namespace.

    Args:
        local_path: An absolute local file-system path
            (e.g. ``C:\\Users\\me\\OneDrive - Corp\\Docs\\file.docx``).
        mount_points: Optional explicit list of
            ``(normalized_mount_point, url_namespace)`` tuples for testing or
            when the registry should not be consulted.

    Returns:
        The SharePoint URL string, or *None* if *local_path* does not fall
        inside a synced library.

    Example::

        >>> onedrive_to_sharepoint_url(
        ...     r"C:\\Users\\me\\OneDrive - Corp\\Docs\\file.docx",
        ...     mount_points=[
        ...         ("C:/Users/me/OneDrive - Corp/Docs",
        ...          "https://contoso.sharepoint.com/sites/team/Shared Documents")
        ...     ],
        ... )
        'https://contoso.sharepoint.com/sites/team/Shared%20Documents/file.docx'
    """
    if not local_path:
        return None

    if mount_points is None:
        mount_points = _get_onedrive_mount_points()

    if not mount_points:
        return None

    # Normalise input path for comparison.
    norm_path = local_path.replace("\\", "/").rstrip("/")
    # On Windows the comparison must be case-insensitive.
    compare = norm_path.lower() if sys.platform == "win32" else norm_path

    for mount_norm, url_ns in mount_points:
        mount_compare = mount_norm.lower() if sys.platform == "win32" else mount_norm

        if compare == mount_compare:
            # Path IS the mount-point root itself.
            return url_ns

        if compare.startswith(mount_compare + "/"):
            relative = norm_path[len(mount_norm) + 1 :]
            encoded = "/".join(
                urllib.parse.quote(part, safe="") for part in relative.split("/")
            )
            return f"{url_ns}/{encoded}"

    return None


def clear_onedrive_cache() -> None:
    """Clear the OneDrive mount-point cache so it is re-read on next access.

    Useful after the user adds a new SharePoint sync during a running session.
    """
    global _onedrive_mount_cache
    _onedrive_mount_cache = None
