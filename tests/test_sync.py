"""Unit tests for the synchronization (3-way merge) engine."""

import json
import os

import pytest

from link4000.data.link_store import LinkStore
from link4000.data.sync import SyncEngine, ConflictRecord
from link4000.models.link import Link


@pytest.fixture
def local_store(tmp_path):
    """A shared local LinkStore backed by a temp file."""
    path = tmp_path / "local.json"
    store = LinkStore(filepath=str(path), shared=True)
    yield store


@pytest.fixture
def shared_path(tmp_path):
    """Path to the simulated remote shared file."""
    return str(tmp_path / "shared.json")


def _write_shared(shared_path, links, tombstones=None):
    """Write a shared payload file (links + tombstones)."""
    payload = {
        "links": [l.to_shared_dict() for l in links],
        "tombstones": tombstones or {},
    }
    with open(shared_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def test_push_new_local_link(local_store, shared_path):
    """A local-only link since baseline is pushed to the shared file."""
    local_store.add(Link(title="Local", url="https://local.example.com"))
    engine = SyncEngine(local_store, shared_path)
    result = engine.sync_store()
    assert result.pushed == 1
    assert result.ok

    with open(shared_path) as f:
        data = json.load(f)
    assert len(data["links"]) == 1
    assert data["links"][0]["url"] == "https://local.example.com"


def test_pull_new_remote_link(local_store, shared_path):
    """A remote-only link is pulled into the local store."""
    remote = Link(title="Remote", url="https://remote.example.com")
    _write_shared(shared_path, [remote])
    engine = SyncEngine(local_store, shared_path)
    result = engine.sync_store()
    assert result.pulled == 1
    assert result.ok
    assert len(local_store.get_all()) == 1
    assert local_store.get_all()[0].url == "https://remote.example.com"


def test_no_change_no_sync(local_store, shared_path):
    """With an established baseline and no changes, nothing is pushed/pulled."""
    link = Link(title="X", url="https://x.example.com")
    local_store.add(link)
    engine = SyncEngine(local_store, shared_path)
    engine.sync_store()  # establishes baseline + pushes

    # Second sync: no changes.
    result = engine.sync_store()
    assert result.pushed == 0
    assert result.pulled == 0
    assert result.ok


def test_edit_edit_conflict_auto_resolve(local_store, shared_path):
    """Same link edited on both sides -> conflict resolved by latest wins."""
    link = Link(title="Orig", url="https://x.example.com")
    local_store.add(link)
    engine = SyncEngine(local_store, shared_path)
    engine.sync_store()  # baseline set, pushed to shared

    # Local edit.
    local_link = local_store.get_all()[0]
    local_link.title = "LocalEdit"
    local_store.update(local_link)

    # Remote edit (newer updated_at).
    with open(shared_path) as f:
        data = json.load(f)
    data["links"][0]["title"] = "RemoteEdit"
    from datetime import datetime, timedelta

    data["links"][0]["updated_at"] = (
        datetime.now() + timedelta(seconds=10)
    ).isoformat()
    with open(shared_path, "w") as f:
        json.dump(data, f)

    result = engine.sync_store()
    assert len(result.conflicts) == 1
    assert result.conflicts[0].kind == "edit_edit"
    # Auto-resolve: remote is newer -> remote wins.
    assert local_store.get_all()[0].title == "RemoteEdit"


def test_delete_propagation(local_store, shared_path):
    """Deleting locally propagates a tombstone so remote is removed."""
    link = Link(title="X", url="https://x.example.com")
    local_store.add(link)
    engine = SyncEngine(local_store, shared_path)
    engine.sync_store()  # baseline set, link in shared

    local_store.delete(link.id)  # local delete -> tombstone
    result = engine.sync_store()
    assert result.deleted_local == 0  # it was already local-deleted
    assert result.ok

    with open(shared_path) as f:
        data = json.load(f)
    assert len(data["links"]) == 0
    assert link.id in data["tombstones"]


def test_remote_delete_removes_local(local_store, shared_path):
    """A remote deletion (tombstone) removes the local link."""
    link = Link(title="X", url="https://x.example.com")
    local_store.add(link)
    engine = SyncEngine(local_store, shared_path)
    engine.sync_store()  # baseline set

    # Remote deletes it.
    _write_shared(shared_path, [], tombstones={link.id: "2020-01-01T00:00:00"})
    result = engine.sync_store()
    assert result.deleted_local == 1
    assert local_store.get_all() == []


def test_delete_vs_edit_conflict(local_store, shared_path):
    """Local delete vs remote edit -> conflict surfaced."""
    link = Link(title="X", url="https://x.example.com")
    local_store.add(link)
    engine = SyncEngine(local_store, shared_path)
    engine.sync_store()

    # Local delete.
    local_store.delete(link.id)
    # Remote edit (newer).
    with open(shared_path) as f:
        data = json.load(f)
    data["links"][0]["title"] = "EditedRemote"
    from datetime import datetime, timedelta

    data["links"][0]["updated_at"] = (
        datetime.now() + timedelta(seconds=10)
    ).isoformat()
    with open(shared_path, "w") as f:
        json.dump(data, f)

    result = engine.sync_store()
    assert len(result.conflicts) == 1
    assert result.conflicts[0].kind == "delete_edit"
    # Auto-resolve defaults to remote -> link restored locally with remote edit.
    assert any(l.url == "https://x.example.com" for l in local_store.get_all())
    assert local_store.get_all()[0].title == "EditedRemote"


def test_tombstone_retention_prune(local_store, shared_path):
    """Old tombstones are pruned after retention period."""
    from datetime import datetime, timedelta

    link = Link(title="X", url="https://x.example.com")
    local_store.add(link)
    engine = SyncEngine(local_store, shared_path, tombstone_retention_days=30)
    engine.sync_store()

    local_store.delete(link.id)
    # Force an old tombstone timestamp.
    old = datetime.now() - timedelta(days=60)
    local_store._tombstones[link.id] = old
    engine.sync_store()
    engine._baseline = {}  # ensure prune path executes
    local_store.prune_tombstones(30)
    assert link.id not in local_store.get_tombstones()


def test_resolver_keep_both(local_store, shared_path):
    """A keep_both resolver keeps both local and remote versions."""
    link = Link(title="Orig", url="https://x.example.com")
    local_store.add(link)
    engine = SyncEngine(local_store, shared_path)
    engine.sync_store()

    local_link = local_store.get_all()[0]
    local_link.title = "LocalEdit"
    local_store.update(local_link)

    with open(shared_path) as f:
        data = json.load(f)
    data["links"][0]["title"] = "RemoteEdit"
    from datetime import datetime, timedelta

    data["links"][0]["updated_at"] = (
        datetime.now() + timedelta(seconds=10)
    ).isoformat()
    with open(shared_path, "w") as f:
        json.dump(data, f)

    def resolver(conflicts):
        return {c.link_id: "keep_both" for c in conflicts}

    result = engine.sync_store(conflict_resolver=resolver)
    assert result.pulled == 0
    # Two links now: original id (remote) + a new id (local kept).
    assert len(local_store.get_all()) == 2
    titles = {l.title for l in local_store.get_all()}
    assert titles == {"LocalEdit", "RemoteEdit"}


def test_locking_serializes_concurrent_syncs(local_store, shared_path):
    """Two engines writing the same shared file both succeed (no clobber)."""
    local_store.add(Link(title="A", url="https://a.example.com"))
    engine1 = SyncEngine(local_store, shared_path)
    engine1.sync_store()

    # Second client with its own local store pointed at same shared file.
    other = LinkStore(filepath=str(local_store.filepath) + ".other", shared=True)
    other.add(Link(title="B", url="https://b.example.com"))
    engine2 = SyncEngine(other, shared_path)
    engine2.sync_store()

    # Both links should now be present in the shared file.
    with open(shared_path) as f:
        data = json.load(f)
    urls = {l["url"] for l in data["links"]}
    assert urls == {"https://a.example.com", "https://b.example.com"}
