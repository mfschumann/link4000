r"""Link source plugin for Microsoft Office recent documents.

This module provides the OfficeRecentSource class that fetches recently-opened
files from Microsoft Office applications via Windows registry.

Works on Windows by reading the Office File MRU registry keys.
"""

from __future__ import annotations

import sys
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from link4000.data.loader_types import SourceEntry
from link4000.data.link_source import LinkSource
from link4000.data.source_registry import SourceRegistry
from link4000.utils.path_utils import resolve_unc_path


@SourceRegistry.register
class OfficeRecentSource(LinkSource):
    """Link source for MS Office recent files."""

    name = "office_recent"
    source_tag = "office_recent"
    config_schema = [
        ("max_age_days", int, 0, "Maximum age in days for recent items (0 = no limit)"),
    ]

    @property
    def is_available(self) -> bool:
        """Check if Office recent files are available."""
        return sys.platform == "win32"

    def fetch(self) -> list[SourceEntry]:
        """Return recently-opened Office documents from registry, newest first."""
        entries: list[SourceEntry] = []

        entries.extend(self._fetch_office_mru_entries())
        entries.extend(self._fetch_office_user_mru_entries())

        entries.sort(key=lambda e: e.last_accessed, reverse=True)

        max_age_days = self.get_config().get("max_age_days", 0)
        return self._filter_by_age(entries, max_age_days)

    def _fetch_office_mru_entries(self) -> list[SourceEntry]:
        r"""Read from HKEY_CURRENT_USER\Software\Microsoft\Office\<version>\<App>\File MRU"""
        import winreg

        entries: list[SourceEntry] = []
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
                        entries.extend(self._read_mru_keys(mru_path))

                finally:
                    winreg.CloseKey(app_key)

        finally:
            winreg.CloseKey(office_key)

        return entries

    def _fetch_office_user_mru_entries(self) -> list[SourceEntry]:
        r"""Read from HKEY_CURRENT_USER\Software\Microsoft\Office\<version>\<App>\User MRU\<user>\File MRU"""
        import winreg

        entries: list[SourceEntry] = []
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
                        entries.extend(self._read_user_mru_entries(user_mru_path))

                finally:
                    winreg.CloseKey(app_key)

        finally:
            winreg.CloseKey(office_key)

        return entries

    def _read_user_mru_entries(self, user_mru_path: str) -> list[SourceEntry]:
        r"""Read from User MRU\<user>\File MRU for all users."""
        import winreg

        entries: list[SourceEntry] = []

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
                entries.extend(self._read_mru_keys(file_mru_path))

        finally:
            winreg.CloseKey(user_mru_key)

        return entries

    def _read_mru_keys(self, mru_path: str) -> list[SourceEntry]:
        """Read Item 1, Item 2, etc. from a File MRU registry key."""
        import winreg

        entries: list[SourceEntry] = []

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

                entry = self._parse_mru_value(value)
                if entry:
                    entries.append(entry)

        finally:
            winreg.CloseKey(mru_key)

        return entries

    def _parse_mru_value(self, value: str) -> Optional[SourceEntry]:
        r"""Parse Office MRU value like [F00000000][T01CDC2FCC3BD6990][O00000000]*C:\path\file.docx"""
        if not value or "*" not in value:
            return None

        path = value.split("*", 1)[1].strip()
        if not path:
            return None

        path = resolve_unc_path(path)

        timestamp = self._parse_mru_timestamp(value)

        title = Path(path).name

        return SourceEntry(
            url=path,
            title=title,
            created_at=timestamp,
            updated_at=timestamp,
            last_accessed=timestamp,
            source_tag=self.source_tag,
        )

    def _parse_mru_timestamp(self, value: str) -> datetime:
        r"""Extract and convert FILETIME from MRU value like [T01CDC2FCC3BD6990]"""
        match = re.search(r"\[T([0-9A-Fa-f]+)\]", value)
        if not match:
            return datetime.now()

        hex_value = match.group(1)

        filetime = int(hex_value, 16)

        windows_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        filetime_microseconds = filetime / 10
        dt = windows_epoch + timedelta(microseconds=filetime_microseconds)

        return dt.replace(tzinfo=None)