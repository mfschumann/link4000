"""Synchronization engine for shared (group) link stores.

Implements a push/pull merge (Option C) for a local shared ``LinkStore``
against a shared JSON file on a common network share. Synchronization uses a
3-way merge keyed on link UUIDs:

* a **baseline** (last-synced ``updated_at`` per id, stored in a side-car
  ``.baseline.json`` next to the shared file) distinguishes "I changed it"
  from "they changed it";
* **tombstones** record deletions so a delete on one client is propagated
  instead of being silently resurrected by another client that still has the
  link;
* **conflicts** (the same link edited on both sides since the baseline, or a
  delete vs an edit) are collected and resolved via a pluggable resolver.

Concurrent writers are serialized with ``portalocker`` advisory file locks
and writes are made atomic with a temp-file + ``os.replace``.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional

import portalocker

from link4000.data.link_store import LinkStore
from link4000.models.link import Link


class ConflictRecord:
    """Describes a synchronization conflict between local and remote versions.

    Attributes:
        link_id: The UUID of the conflicting link.
        local: The local Link version (None for a pure delete-vs-edit).
        remote: The remote Link version (None for a pure edit-vs-delete).
        kind: One of "edit_edit", "delete_edit", "edit_delete".
    """

    def __init__(
        self,
        link_id: str,
        local: Optional[Link],
        remote: Optional[Link],
        kind: str,
    ) -> None:
        """Initialize a conflict record.

        Args:
            link_id: The UUID of the conflicting link.
            local: The local Link version, or None if locally deleted.
            remote: The remote Link version, or None if remotely deleted.
            kind: Conflict classification (see class docstring).
        """
        self.link_id = link_id
        self.local = local
        self.remote = remote
        self.kind = kind

    def describe(self) -> str:
        """Return a human-readable summary of the conflict.

        Returns:
            A short string describing the conflicting link and its kind.
        """
        subject = self.remote or self.local
        title = subject.title if subject else self.link_id
        return f"[{self.kind}] {title} ({self.link_id})"


class SyncResult:
    """Result of a single synchronization pass.

    Attributes:
        pushed: Number of local links written to the shared file.
        pulled: Number of remote links written into the local store.
        deleted_local: Number of local links removed due to remote deletion.
        conflicts: Conflict records that required resolution.
        errors: Non-fatal error messages encountered during the sync.
    """

    def __init__(self) -> None:
        """Initialize an empty sync result."""
        self.pushed: int = 0
        self.pulled: int = 0
        self.deleted_local: int = 0
        self.conflicts: List[ConflictRecord] = []
        self.errors: List[str] = []

    @property
    def ok(self) -> bool:
        """Return True if no errors were recorded."""
        return not self.errors


class SyncEngine:
    """Performs 3-way merge synchronization for a single shared store.

    Args:
        local_store: The local ``LinkStore`` (must have ``shared=True``).
        shared_file_path: Path to the shared JSON file on the network share.
        tombstone_retention_days: Tombstones older than this are pruned after
            a successful sync.
    """

    def __init__(
        self,
        local_store: LinkStore,
        shared_file_path: str,
        tombstone_retention_days: int = 30,
    ) -> None:
        """Initialize the engine and load the persisted baseline."""
        self._local = local_store
        self._shared_path = shared_file_path
        self._tombstone_retention_days = tombstone_retention_days
        self._baseline_path = shared_file_path + ".baseline.json"
        self._baseline: Dict[str, datetime] = self._load_baseline()

    # ------------------------------------------------------------------
    # Baseline persistence
    # ------------------------------------------------------------------
    def _load_baseline(self) -> Dict[str, datetime]:
        """Load the last-synced baseline from the side-car file.

        Returns:
            A mapping of link id -> last-synced ``updated_at`` timestamp.
        """
        if not os.path.exists(self._baseline_path):
            return {}
        try:
            with open(self._baseline_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {tid: datetime.fromisoformat(ts) for tid, ts in data.items()}
        except (json.JSONDecodeError, IOError, ValueError):
            return {}

    def _save_baseline(self) -> None:
        """Persist the current baseline to the side-car file."""
        data = {tid: ts.isoformat() for tid, ts in self._baseline.items()}
        tmp = self._baseline_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._baseline_path)

    # ------------------------------------------------------------------
    # Conflict resolution (pluggable)
    # ------------------------------------------------------------------
    def _auto_resolve(self, conflicts: List[ConflictRecord]) -> Dict[str, str]:
        """Default resolver: latest ``updated_at`` wins; remote on tie.

        Args:
            conflicts: The conflict records to resolve.

        Returns:
            A mapping of link id -> "local" | "remote" | "keep_both".
        """
        choices: Dict[str, str] = {}
        for c in conflicts:
            if c.local is None:
                choices[c.link_id] = "remote"
            elif c.remote is None:
                choices[c.link_id] = "local"
            else:
                choices[c.link_id] = (
                    "local"
                    if c.local.updated_at > c.remote.updated_at
                    else "remote"
                )
        return choices

    # ------------------------------------------------------------------
    # Core sync
    # ------------------------------------------------------------------
    def sync_store(
        self,
        conflict_resolver: Optional[
            Callable[[List[ConflictRecord]], Dict[str, str]]
        ] = None,
    ) -> SyncResult:
        """Synchronize the local shared store with the shared file.

        Performs a locked, atomic 3-way merge. Conflicts are resolved by
        *conflict_resolver* (or the built-in latest-wins resolver when None).

        Args:
            conflict_resolver: Optional callable taking the list of
                ``ConflictRecord`` and returning a dict mapping link id to
                "local" / "remote" / "keep_both".

        Returns:
            A :class:`SyncResult` describing what happened. Errors are recorded
            there rather than raised so callers can surface them gracefully.
        """
        result = SyncResult()
        shared_dir = os.path.dirname(os.path.abspath(self._shared_path))
        try:
            os.makedirs(shared_dir, exist_ok=True)
        except OSError as exc:
            result.errors.append(f"Cannot create shared directory: {exc}")
            return result

        try:
            lock = portalocker.Lock(
                self._shared_path, mode="a+", flags=portalocker.LOCK_EX
            )
            lock.acquire(timeout=10)
        except (portalocker.LockException, OSError) as exc:
            result.errors.append(f"Could not lock shared file: {exc}")
            return result

        try:
            return self._sync_locked(result, conflict_resolver)
        finally:
            try:
                lock.release()
            except Exception:
                pass

    def _sync_locked(
        self,
        result: SyncResult,
        conflict_resolver: Optional[
            Callable[[List[ConflictRecord]], Dict[str, str]]
        ],
    ) -> SyncResult:
        """Execute the merge while the shared-file lock is held.

        Args:
            result: The :class:`SyncResult` to populate.
            conflict_resolver: Optional conflict resolver (see ``sync_store``).

        Returns:
            The populated :class:`SyncResult`.
        """
        # 1. Read remote payload.
        remote_links: Dict[str, Link] = {}
        remote_tombstones: Dict[str, datetime] = {}
        if os.path.exists(self._shared_path):
            try:
                with open(self._shared_path, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                remote = json.loads(raw) if raw else {"links": [], "tombstones": {}}
                for d in remote.get("links", []):
                    link = Link.from_shared_dict(d)
                    remote_links[link.id] = link
                for tid, ts in remote.get("tombstones", {}).items():
                    try:
                        remote_tombstones[tid] = datetime.fromisoformat(ts)
                    except (ValueError, TypeError):
                        remote_tombstones[tid] = datetime.now()
            except (json.JSONDecodeError, IOError) as exc:
                result.errors.append(f"Corrupt shared file: {exc}")
                return result

        # 2. Local state.
        local_links: Dict[str, Link] = {
            link.id: link for link in self._local.get_all()
        }
        local_tombstones = self._local.get_tombstones()
        baseline = self._baseline

        def changed_locally(link_id: str) -> bool:
            """Return True if the local link changed since the baseline."""
            return link_id not in baseline or (
                link_id in local_links
                and local_links[link_id].updated_at > baseline[link_id]
            )

        def changed_remotely(link_id: str) -> bool:
            """Return True if the remote link changed since the baseline."""
            return link_id not in baseline or (
                link_id in remote_links
                and remote_links[link_id].updated_at > baseline[link_id]
            )

        # 3. Build new local + new remote sets.
        new_local: Dict[str, Link] = {}
        new_remote: Dict[str, Link] = dict(remote_links)
        new_remote_tombstones: Dict[str, datetime] = dict(remote_tombstones)
        new_local_tombstones: Dict[str, datetime] = dict(local_tombstones)

        all_ids = (
            set(local_links)
            | set(remote_links)
            | set(baseline)
            | set(local_tombstones)
            | set(remote_tombstones)
        )

        for lid in all_ids:
            in_local = lid in local_links
            in_remote = lid in remote_links
            in_local_tomb = lid in local_tombstones
            in_remote_tomb = lid in remote_tombstones
            in_baseline = lid in baseline

            # Deleted remotely since baseline -> delete locally.
            if in_remote_tomb and (in_baseline or in_local):
                if in_local and changed_locally(lid):
                    result.conflicts.append(
                        ConflictRecord(lid, local_links[lid], None, "delete_edit")
                    )
                else:
                    new_local.pop(lid, None)
                    new_local_tombstones.pop(lid, None)
                    result.deleted_local += 1
                new_remote.pop(lid, None)
                new_remote_tombstones[lid] = remote_tombstones[lid]
                continue

            # Deleted locally since baseline -> propagate tombstone to remote.
            if in_local_tomb and (in_baseline or in_remote):
                if in_remote and changed_remotely(lid):
                    result.conflicts.append(
                        ConflictRecord(lid, None, remote_links[lid], "edit_delete")
                    )
                else:
                    new_local.pop(lid, None)
                    new_local_tombstones.pop(lid, None)
                    new_remote.pop(lid, None)
                    new_remote_tombstones[lid] = local_tombstones[lid]
                continue

            # Both present and both changed -> conflict.
            if in_local and in_remote and changed_locally(lid) and changed_remotely(lid):
                result.conflicts.append(
                    ConflictRecord(lid, local_links[lid], remote_links[lid], "edit_edit")
                )
                continue

            # New remote link -> pull.
            if in_remote and not in_local and not in_baseline:
                new_local[lid] = remote_links[lid]
                result.pulled += 1
                continue

            # New local link -> push.
            if in_local and not in_remote and not in_baseline:
                new_local[lid] = local_links[lid]
                new_remote[lid] = local_links[lid]
                result.pushed += 1
                continue

            # Only local changed -> push.
            if in_local and changed_locally(lid) and not changed_remotely(lid):
                new_local[lid] = local_links[lid]
                new_remote[lid] = local_links[lid]
                result.pushed += 1
                continue

            # Only remote changed -> pull.
            if in_remote and changed_remotely(lid) and not changed_locally(lid):
                new_local[lid] = remote_links[lid]
                result.pulled += 1
                continue

            # Unchanged (or unchanged since baseline): keep whichever exists.
            if in_local:
                new_local.setdefault(lid, local_links[lid])
            if in_remote:
                new_remote.setdefault(lid, remote_links[lid])

        # 4. Resolve conflicts.
        if result.conflicts:
            resolver = conflict_resolver or self._auto_resolve
            choices = resolver(result.conflicts)
            for c in result.conflicts:
                choice = choices.get(c.link_id, "remote")
                if choice == "local":
                    if c.local is not None:
                        new_local[c.link_id] = c.local
                        new_remote[c.link_id] = c.local
                        result.pushed += 1
                elif choice == "remote":
                    if c.remote is not None:
                        new_local[c.link_id] = c.remote
                        new_remote[c.link_id] = c.remote
                    else:
                        new_local.pop(c.link_id, None)
                        new_local_tombstones.pop(c.link_id, None)
                        new_remote.pop(c.link_id, None)
                        new_remote_tombstones[c.link_id] = remote_tombstones.get(
                            c.link_id, datetime.now()
                        )
                        result.deleted_local += 1
                elif choice == "keep_both":
                    if c.remote is not None:
                        new_local[c.link_id] = c.remote
                        new_remote[c.link_id] = c.remote
                    new_id = str(uuid.uuid4())
                    if c.local is not None:
                        kept = Link.from_shared_dict(c.local.to_shared_dict())
                        kept.id = new_id
                        kept.updated_at = datetime.now()
                        new_local[new_id] = kept
                        new_remote[new_id] = kept
                        result.pushed += 1

        # 5. Write merged remote atomically.
        remote_payload = {
            "links": [link.to_shared_dict() for link in new_remote.values()],
            "tombstones": {
                tid: ts.isoformat() for tid, ts in new_remote_tombstones.items()
            },
        }
        tmp = self._shared_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(remote_payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self._shared_path)
        except OSError as exc:
            result.errors.append(f"Failed to write shared file: {exc}")
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return result

        # 6. Persist local merged state.
        local_payload = {
            "links": [link.to_shared_dict() for link in new_local.values()],
            "tombstones": {
                tid: ts.isoformat() for tid, ts in new_local_tombstones.items()
            },
        }
        self._local.load_shared_payload(local_payload)
        self._local.prune_tombstones(self._tombstone_retention_days)
        self._local.save()

        # 7. Advance baseline to the merged state.
        self._baseline = {}
        for lid, link in new_local.items():
            self._baseline[lid] = link.updated_at
        for lid in new_remote_tombstones:
            self._baseline.pop(lid, None)
        self._save_baseline()

        return result
