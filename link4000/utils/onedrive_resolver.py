"""OneDrive/SharePoint path resolution utilities.

This module provides functionality to resolve local file paths within
OneDrive for Business folders (that are synced from SharePoint) to their
corresponding SharePoint URLs.

Uses Microsoft Graph API via office365-rest-python-client with
Azure CLI authentication (no app registration required).
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from office365.graph_client import GraphClient

from link4000.utils.config import get_azure_cli_path

_graph_client: Optional["GraphClient"] = None


def _get_access_token() -> Optional[str]:
    """Get an access token using Azure CLI with configurable executable path.

    Returns:
        Access token string, or None if authentication fails.
    """
    azure_cli_path = get_azure_cli_path()

    az_executable = azure_cli_path
    if os.path.isdir(azure_cli_path):
        az_path = shutil.which("az", path=azure_cli_path)
        az_executable = az_path if az_path else "az"
    elif os.path.isfile(azure_cli_path):
        az_executable = azure_cli_path

    scopes = "https://graph.microsoft.com/Files.Read.All https://graph.microsoft.com/Sites.Read.All"

    if sys.platform.startswith("win"):
        cmd = ["cmd", "/c", f'"{az_executable}" account get-access-token --output json --resource {scopes}']
    else:
        cmd = ["/bin/sh", "-c", f'"{az_executable}" account get-access-token --output json --resource {scopes}']

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=dict(os.environ, AZURE_CORE_NO_COLOR="true"),
        )
        if result.returncode != 0:
            return None
        token_data = json.loads(result.stdout)
        return token_data.get("accessToken")
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError):
        return None


def _get_graph_client() -> Optional["GraphClient"]:
    """Get or create the Microsoft Graph client using Azure CLI authentication.

    Uses Azure CLI (configurable path) to get access token from 'az login'.
    No app registration required.

    Returns:
        Authenticated GraphClient instance, or None if authentication fails.
    """
    global _graph_client
    if _graph_client is not None:
        return _graph_client

    try:
        from office365.graph_client import GraphClient
    except ImportError:
        return None

    try:
        token = _get_access_token()
        if not token:
            return None

        def acquire_token():
            return {"access_token": token}

        _graph_client = GraphClient(
            tenant="common",
            acquire_token=acquire_token,
        )
        return _graph_client
    except Exception:
        return None


def _get_onedrive_roots() -> dict[str, str]:
    """Get known OneDrive root paths from the system.

    On Windows, OneDrive creates specific folder structures.
    This function attempts to detect common OneDrive paths.

    Returns:
        Dictionary mapping OneDrive root path to drive name.
    """
    roots: dict[str, str] = {}

    if sys.platform != "win32":
        return roots

    user_home = Path.home()
    onedrive_paths = [
        user_home / "OneDrive",
        user_home / "OneDrive - Personal",
        user_home / "OneDrive - Company",
    ]

    for onedrive_path in onedrive_paths:
        if onedrive_path.exists() and onedrive_path.is_dir():
            roots[str(onedrive_path)] = onedrive_path.name

    return roots


def _find_matching_drive(
    client: "GraphClient", relative_path: str
) -> Optional[dict]:
    """Find the drive that contains the given relative path.

    Args:
        client: Authenticated GraphClient instance.
        relative_path: The relative path within OneDrive (e.g., '/Documents/folder/file.docx').

    Returns:
        Dictionary with drive info and item details, or None if not found.
    """
    try:

        drives = client.drives.get().execute_query()
        relative_path = relative_path.replace("\\", "/").lstrip("/")

        for drive in drives:
            try:
                drive_root = drive.root
                if not drive_root:
                    continue

                item_path = f"{drive_root.path}:/{relative_path}"
                item = client.drive.get_by_path(item_path).get().execute_query()

                if item:
                    return {
                        "drive_id": drive.id,
                        "item_id": item.id,
                        "web_url": item.web_url,
                        "name": item.name,
                    }
            except Exception:
                continue

    except Exception:
        pass

    return None


def resolve_to_sharepoint_url(local_path: str) -> Optional[str]:
    """Resolve a local file path to its SharePoint URL if it's in a synced OneDrive folder.

    This function checks if the given path is within a OneDrive for Business
    folder that is synced from SharePoint. If so, it uses the Microsoft Graph API
    to find the corresponding SharePoint URL.

    Args:
        local_path: The local file path (e.g., 'C:\\Users\\...\\OneDrive - Company\\Documents\\file.docx').

    Returns:
        The SharePoint URL if resolution successful, None otherwise.
        On failure, returns None (caller should fall back to local path).
    """
    if sys.platform != "win32":
        return None

    if not local_path or not os.path.isfile(local_path):
        return None

    local_path = local_path.strip('"')
    path_obj = Path(local_path)
    path_str = str(path_obj)

    onedrive_roots = _get_onedrive_roots()
    if not onedrive_roots:
        return None

    matched_root = None
    relative_path = None

    for root_path, root_name in onedrive_roots.items():
        if path_str.startswith(root_path):
            matched_root = root_path
            relative_path = path_str[len(root_path):].lstrip("\\/")
            break

    if not matched_root or not relative_path:
        return None

    client = _get_graph_client()
    if client is None:
        return None

    result = _find_matching_drive(client, relative_path)
    if result and result.get("web_url"):
        return result["web_url"]

    return None


def is_onedrive_path(path: str) -> bool:
    """Check if the given path is within a known OneDrive folder.

    Args:
        path: The file path to check.

    Returns:
        True if the path is within a OneDrive folder, False otherwise.
    """
    if sys.platform != "win32":
        return False

    if not path:
        return False

    path_normalized = path.replace("\\", "/")

    onedrive_roots = _get_onedrive_roots()
    for root_path in onedrive_roots.keys():
        root_normalized = root_path.replace("\\", "/")
        if path_normalized.startswith(root_normalized):
            return True

    return False
