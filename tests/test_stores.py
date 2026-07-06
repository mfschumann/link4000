"""Unit tests for the multi-store registry."""

import pytest

from link4000.data.store_registry import StoreRegistry
from link4000.models.link import Link


@pytest.fixture
def registry(tmp_path):
    """Create a StoreRegistry backed by temporary store files."""
    import link4000.utils.config as cfg

    cfg_dir = tmp_path / ".link4000"
    cfg_dir.mkdir()
    cfg._CONFIG_PATH = str(cfg_dir / "config.toml")
    cfg._config = None
    (cfg_dir / "config.toml").write_text(
        f"""
[[stores]]
name = "Local"
path = "{tmp_path / 'local.json'}"
shared = false

[[stores]]
name = "Team"
path = "{tmp_path / 'team.json'}"
shared = true
"""
    )
    cfg._config = None
    reg = StoreRegistry()
    yield reg
    cfg._config = None


def test_store_names(registry):
    """Registry exposes the configured store names."""
    assert set(registry.get_store_names()) == {"Local", "Team"}


def test_default_store_name(registry):
    """The default store is 'Local'."""
    assert registry.get_default_store_name() == "Local"


def test_add_link_routes_to_store(registry):
    """add_link routes a link to the named store and tags it."""
    link = Link(title="A", url="https://a.example.com")
    registry.add_link(link, "Team")
    assert link.store == "Team"

    team = registry.get_store("Team")
    assert team is not None
    assert len(team.get_all()) == 1
    assert team.get_all()[0].url == "https://a.example.com"

    local = registry.get_store("Local")
    assert local is not None
    assert local.get_all() == []


def test_get_all_links_tags_store(registry):
    """get_all_links aggregates across stores and tags each link."""
    registry.add_link(Link(title="A", url="https://a.example.com"), "Local")
    registry.add_link(Link(title="B", url="https://b.example.com"), "Team")
    all_links = registry.get_all_links()
    assert len(all_links) == 2
    by_url = {link.url: link.store for link in all_links}
    assert by_url["https://a.example.com"] == "Local"
    assert by_url["https://b.example.com"] == "Team"


def test_find_link_and_store(registry):
    """find_link returns the link and its owning store."""
    link = Link(title="A", url="https://a.example.com")
    registry.add_link(link, "Team")
    found, store = registry.find_link(link.id)
    assert found is not None
    assert store == "Team"
    assert found.store == "Team"
    assert registry.find_store_of_link(link.id) == "Team"


def test_update_and_delete_link(registry):
    """update_link and delete_link target the correct store."""
    link = Link(title="A", url="https://a.example.com")
    registry.add_link(link, "Team")
    link.title = "A2"
    registry.update_link(link)
    assert registry.get_store("Team").get_all()[0].title == "A2"

    registry.delete_link(link.id, "Team")
    assert registry.get_store("Team").get_all() == []
    assert registry.find_link(link.id) == (None, None)


def test_bulk_delete(registry):
    """bulk_delete removes the given ids from the store."""
    l1 = Link(title="A", url="https://a.example.com")
    l2 = Link(title="B", url="https://b.example.com")
    registry.add_link(l1, "Team")
    registry.add_link(l2, "Team")
    registry.bulk_delete([l1.id, l2.id], "Team")
    assert registry.get_store("Team").get_all() == []


def test_search_aggregates(registry):
    """search spans all stores and tags results."""
    registry.add_link(Link(title="Alpha", url="https://a.example.com"), "Local")
    registry.add_link(Link(title="Beta", url="https://b.example.com"), "Team")
    results = registry.search("beta")
    assert len(results) == 1
    assert results[0].store == "Team"


def test_excluded_recent_urls_local_only(registry):
    """Excluded recent URLs live on the local store."""
    registry.add_excluded_recent_url("https://x.example.com")
    assert "https://x.example.com" in registry.get_excluded_recent_urls()


def test_shared_stores(registry):
    """shared_stores returns only the shared store."""
    shared = registry.shared_stores()
    assert len(shared) == 1
    assert shared[0].shared is True
