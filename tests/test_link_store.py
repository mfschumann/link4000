"""Unit tests for the LinkStore."""

import pytest
import tempfile
import os

from link4000.data.link_store import LinkStore
from link4000.models.link import Link


class TestLinkStore:
    """Tests for the LinkStore class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def store(self, temp_dir):
        """Create a LinkStore with a temporary file."""
        filepath = os.path.join(temp_dir, "links.json")
        return LinkStore(filepath=filepath)

    def test_create_empty_store(self, store):
        """Test creating a new empty store."""
        links = store.get_all()
        assert links == []
        excluded = store.get_excluded_recent_urls()
        assert excluded == set()

    def test_add_link(self, store):
        """Test adding a link to the store."""
        link = Link(title="Test", url="https://example.com", tags=["test"])
        store.add(link)
        
        links = store.get_all()
        assert len(links) == 1
        assert links[0].title == "Test"
        assert links[0].url == "https://example.com"

    def test_add_link_generates_id(self, store):
        """Test that adding a link without ID generates one."""
        link = Link(title="Test", url="https://example.com", id="")
        store.add(link)
        
        links = store.get_all()
        assert links[0].id != ""

    def test_update_link(self, store):
        """Test updating an existing link."""
        link = Link(title="Test", url="https://example.com", tags=["test"])
        store.add(link)
        
        original_id = link.id
        link.title = "Updated Title"
        store.update(link)
        
        links = store.get_all()
        assert len(links) == 1
        assert links[0].title == "Updated Title"
        assert links[0].id == original_id

    def test_delete_link(self, store):
        """Test deleting a link."""
        link = Link(title="Test", url="https://example.com")
        store.add(link)
        link_id = link.id
        
        store.delete(link_id)
        
        links = store.get_all()
        assert len(links) == 0

    def test_find_by_url(self, store):
        """Test finding a link by URL."""
        link = Link(title="Test", url="https://example.com")
        store.add(link)
        
        found = store.find_by_url("https://example.com")
        assert found is not None
        assert found.title == "Test"

    def test_find_by_url_case_insensitive(self, store):
        """Test URL search is case-insensitive."""
        link = Link(title="Test", url="https://Example.COM")
        store.add(link)
        
        found = store.find_by_url("https://example.com")
        assert found is not None

    def test_search(self, store):
        """Test searching links."""
        store.add(Link(title="Google", url="https://google.com", tags=["search"]))
        store.add(Link(title="GitHub", url="https://github.com", tags=["code"]))
        
        results = store.search("google")
        assert len(results) == 1
        assert results[0].title == "Google"

    def test_search_by_tag(self, store):
        """Test searching by tag."""
        store.add(Link(title="Link1", url="https://example1.com", tags=["work"]))
        store.add(Link(title="Link2", url="https://example2.com", tags=["personal"]))
        
        results = store.search("work")
        assert len(results) == 1
        assert results[0].title == "Link1"

    def test_import_links_no_override(self, store):
        """Test importing links without overriding existing."""
        existing = Link(title="Existing", url="https://example.com")
        store.add(existing)
        
        new_links = [
            Link(title="New", url="https://example.com"),
            Link(title="Another", url="https://another.com"),
        ]
        
        added, skipped, updated = store.import_links(new_links, override=False)
        
        assert added == 1  # Only the new URL
        assert skipped == 1  # Duplicate URL
        assert updated == 0
        
        links = store.get_all()
        assert len(links) == 2
        # Existing should keep its title
        assert links[0].title == "Existing"

    def test_import_links_with_override(self, store):
        """Test importing links with override."""
        existing = Link(title="Existing", url="https://example.com")
        store.add(existing)
        
        new_links = [
            Link(title="New", url="https://example.com"),
        ]
        
        added, skipped, updated = store.import_links(new_links, override=True)
        
        assert added == 0
        assert skipped == 0
        assert updated == 1
        
        links = store.get_all()
        assert len(links) == 1
        assert links[0].title == "New"

    def test_bulk_update_tags(self, store):
        """Test bulk tag updates."""
        link1 = Link(title="Link1", url="https://example1.com", tags=["old"])
        link2 = Link(title="Link2", url="https://example2.com", tags=["old"])
        store.add(link1)
        store.add(link2)
        
        link_ids = [link1.id, link2.id]
        store.bulk_update_tags(link_ids, tags_to_add=["new"], tags_to_remove=["old"])
        
        links = store.get_all()
        for link in links:
            assert "new" in link.tags
            assert "old" not in link.tags

    def test_bulk_delete(self, store):
        """Test bulk delete."""
        link1 = Link(title="Link1", url="https://example1.com")
        link2 = Link(title="Link2", url="https://example2.com")
        store.add(link1)
        store.add(link2)
        
        store.bulk_delete([link1.id])
        
        links = store.get_all()
        assert len(links) == 1
        assert links[0].title == "Link2"

    def test_excluded_recent_urls(self, store):
        """Test managing excluded recent URLs."""
        store.add_excluded_recent_url("https://example.com")
        
        excluded = store.get_excluded_recent_urls()
        assert "https://example.com" in excluded

    def test_persistence(self, temp_dir):
        """Test that data persists across store instances."""
        filepath = os.path.join(temp_dir, "links.json")
        
        store1 = LinkStore(filepath=filepath)
        store1.add(Link(title="Test", url="https://example.com"))
        
        # Create new store instance with same file
        store2 = LinkStore(filepath=filepath)
        links = store2.get_all()
        
        assert len(links) == 1
        assert links[0].title == "Test"

    def test_update_last_accessed(self, store):
        """Test updating last accessed timestamp."""
        link = Link(title="Test", url="https://example.com")
        store.add(link)
        
        store.update_last_accessed(link.id)
        
        links = store.get_all()
        assert links[0].last_accessed is not None
