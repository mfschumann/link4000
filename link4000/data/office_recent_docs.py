r"""Read recently-opened files from Microsoft Office applications via registry.

Works on Windows by reading the Office File MRU registry keys.
"""

from __future__ import annotations

import sys
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from link4000.utils.path_utils import resolve_path

RecentEntry = namedtuple(
    "RecentEntry", ["url", "title", "created_at", "updated_at", "last_accessed"]
)


def fetch_office_recent_entries() -> list[RecentEntry]:
    """Return recently-opened Office documents from registry, newest first."""
    if sys.platform != "win32":
        return []

    entries: list[RecentEntry] = []

    entries.extend(_fetch_office_mru_entries())
    entries.extend(_fetch_office_user_mru_entries())

    entries.sort(key=lambda e: e.last_accessed, reverse=True)
    return entries


def _fetch_office_mru_entries() -> list[RecentEntry]:
    r"""Read from HKEY_CURRENT_USER\Software\Microsoft\Office\<version>\<App>\File MRU"""
    import winreg

    entries: list[RecentEntry] = []
    base_path = r"Software\Microsoft\Office"

    try:
        office_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_path)
    except WindowsError:
        return entries

    try:
        i = 0
        while True:
            try:
                version = winreg.EnumKey(office_key, i)
            except WindowsError:
                break
            i += 1

            app_path = f"{base_path}\\{version}"
            try:
                app_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, app_path)
            except WindowsError:
                continue

            try:
                j = 0
                while True:
                    try:
                        app_name = winreg.EnumKey(app_key, j)
                    except WindowsError:
                        break
                    j += 1

                    mru_path = f"{app_path}\\{app_name}\\File MRU"
                    entries.extend(_read_mru_keys(mru_path))

            finally:
                winreg.CloseKey(app_key)

    finally:
        winreg.CloseKey(office_key)

    return entries


def _fetch_office_user_mru_entries() -> list[RecentEntry]:
    r"""Read from HKEY_CURRENT_USER\Software\Microsoft\Office\<version>\<App>\User MRU\<user>\File MRU"""
    import winreg

    entries: list[RecentEntry] = []
    base_path = r"Software\Microsoft\Office"

    try:
        office_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_path)
    except WindowsError:
        return entries

    try:
        i = 0
        while True:
            try:
                version = winreg.EnumKey(office_key, i)
            except WindowsError:
                break
            i += 1

            app_path = f"{base_path}\\{version}"
            try:
                app_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, app_path)
            except WindowsError:
                continue

            try:
                j = 0
                while True:
                    try:
                        app_name = winreg.EnumKey(app_key, j)
                    except WindowsError:
                        break
                    j += 1

                    user_mru_path = f"{app_path}\\{app_name}\\User MRU"
                    entries.extend(_read_user_mru_entries(user_mru_path))

            finally:
                winreg.CloseKey(app_key)

    finally:
        winreg.CloseKey(office_key)

    return entries


def _read_user_mru_entries(user_mru_path: str) -> list[RecentEntry]:
    r"""Read from User MRU\<user>\File MRU for all users."""
    import winreg

    entries: list[RecentEntry] = []

    try:
        user_mru_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, user_mru_path)
    except WindowsError:
        return entries

    try:
        i = 0
        while True:
            try:
                user = winreg.EnumKey(user_mru_key, i)
            except WindowsError:
                break
            i += 1

            file_mru_path = f"{user_mru_path}\\{user}\\File MRU"
            entries.extend(_read_mru_keys(file_mru_path))

    finally:
        winreg.CloseKey(user_mru_key)

    return entries


def _read_mru_keys(mru_path: str) -> list[RecentEntry]:
    """Read Item 1, Item 2, etc. from a File MRU registry key."""
    import winreg

    entries: list[RecentEntry] = []

    try:
        mru_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, mru_path)
    except WindowsError:
        return entries

    try:
        i = 1
        while True:
            try:
                value, _ = winreg.QueryValueEx(mru_key, f"Item {i}")
            except WindowsError:
                break
            i += 1

            entry = _parse_mru_value(value)
            if entry:
                entries.append(entry)

    finally:
        winreg.CloseKey(mru_key)

    return entries


def _parse_mru_value(value: str) -> Optional[RecentEntry]:
    r"""Parse Office MRU value like [F00000000][T01CDC2FCC3BD6990][O00000000]*C:\path\file.docx"""
    if not value or "*" not in value:
        return None

    path = value.split("*", 1)[1].strip()
    if not path:
        return None

    # Resolve path (handles UNC conversion, symlinks, etc. on Windows)
    path, _ = resolve_path(path)

    timestamp = _parse_mru_timestamp(value)

    title = Path(path).name

    return RecentEntry(
        url=path,
        title=title,
        created_at=timestamp,
        updated_at=timestamp,
        last_accessed=timestamp,
    )


def _parse_mru_timestamp(value: str) -> datetime:
    r"""Extract and convert FILETIME from MRU value like [T01CDC2FCC3BD6990]"""
    import re

    match = re.search(r"\[T([0-9A-Fa-f]+)\]", value)
    if not match:
        return datetime.now()

    hex_value = match.group(1)

    filetime = int(hex_value, 16)

    windows_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    filetime_microseconds = filetime / 10
    dt = windows_epoch + timedelta(microseconds=filetime_microseconds)

    return dt.replace(tzinfo=None)
