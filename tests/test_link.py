"""Unit tests for the Link model."""

import uuid
from datetime import datetime

from link4000.models.link import Link


class TestLink:
    """Tests for the Link dataclass."""

    def test_create_link_with_defaults(self):
        """Test creating a link with default values."""
        link = Link(title="Test Link", url="https://example.com")
        
        assert link.title == "Test Link"
        assert link.url == "https://example.com"
        assert link.tags == []
        assert link.id is not None
        assert isinstance(uuid.UUID(link.id), uuid.UUID)  # Valid UUID
        assert link.created_at is not None
        assert link.updated_at is not None
        assert link.last_accessed is not None

    def test_create_link_with_tags(self):
        """Test creating a link with tags."""
        link = Link(
            title="Test Link",
            url="https://example.com",
            tags=["work", "important"]
        )
        
        assert link.tags == ["work", "important"]

    def test_create_link_with_custom_id(self):
        """Test creating a link with a custom ID."""
        custom_id = "custom-uuid-123"
        link = Link(title="Test", url="https://example.com", id=custom_id)
        
        assert link.id == custom_id

    def test_to_dict(self):
        """Test serialization to dictionary."""
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        updated_at = datetime(2024, 1, 2, 12, 0, 0)
        last_accessed = datetime(2024, 1, 3, 12, 0, 0)
        
        link = Link(
            title="Test",
            url="https://example.com",
            tags=["tag1"],
            id="test-id",
            created_at=created_at,
            updated_at=updated_at,
            last_accessed=last_accessed,
        )
        
        result = link.to_dict()
        
        assert result == {
            "id": "test-id",
            "title": "Test",
            "url": "https://example.com",
            "tags": ["tag1"],
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-02T12:00:00",
            "last_accessed": "2024-01-03T12:00:00",
        }

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "id": "test-id",
            "title": "Test Link",
            "url": "https://example.com",
            "tags": ["work", "important"],
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-02T12:00:00",
            "last_accessed": "2024-01-03T12:00:00",
        }
        
        link = Link.from_dict(data)
        
        assert link.id == "test-id"
        assert link.title == "Test Link"
        assert link.url == "https://example.com"
        assert link.tags == ["work", "important"]
        assert link.created_at == datetime(2024, 1, 1, 12, 0, 0)
        assert link.updated_at == datetime(2024, 1, 2, 12, 0, 0)
        assert link.last_accessed == datetime(2024, 1, 3, 12, 0, 0)

    def test_from_dict_with_defaults(self):
        """Test from_dict with missing optional fields."""
        data = {
            "title": "Test",
            "url": "https://example.com",
        }
        
        link = Link.from_dict(data)
        
        assert link.title == "Test"
        assert link.url == "https://example.com"
        assert link.id is not None
        assert isinstance(uuid.UUID(link.id), uuid.UUID)

    def test_from_legacy_dict(self):
        """Test conversion from legacy format."""
        data = {
            "name": "Legacy Link",
            "path": "https://example.com",
            "keywords": ["old", "tags"],
        }
        
        link = Link.from_legacy_dict(data)
        
        assert link.title == "Legacy Link"
        assert link.url == "https://example.com"
        assert link.tags == ["old", "tags"]

    def test_link_type_property(self):
        """Test link_type property caches result."""
        link = Link(title="Test", url="https://example.com")
        
        # First access computes the type
        type1 = link.link_type
        # Second access should return cached value
        type2 = link.link_type
        
        assert type1 == type2
        assert type1 in ["web", "folder", "file", "sharepoint", "unknown"]

    def test_repr_excludes_internal_fields(self):
        """Test that repr doesn't include private fields."""
        link = Link(title="Test", url="https://example.com")
        repr_str = repr(link)
        
        # _cached_link_type should be excluded per repr=False
        assert "_cached_link_type" not in repr_str
        # is_recent and is_favorite should be present (no repr=False)
        assert "is_recent" in repr_str
        assert "is_favorite" in repr_str
