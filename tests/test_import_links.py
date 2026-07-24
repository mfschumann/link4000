"""Unit tests for the import_links utility module."""

import json
import pytest

from link4000.utils.import_links import do_import, _detect_schema


class TestDetectSchema:
    """Test schema detection for JSON import files."""

    def test_detect_legacy_schema_list(self):
        """A list of links with 'keywords' field is detected as legacy."""
        data = [{"name": "Test", "path": "https://example.com", "keywords": ["test"]}]
        assert _detect_schema(data) == "legacy"

    def test_detect_current_schema_dict(self):
        """A dict with 'links' containing 'tags' field is detected as current."""
        data = {
            "links": [
                {
                    "id": "test-id",
                    "title": "Test",
                    "url": "https://example.com",
                    "tags": ["test"],
                }
            ]
        }
        assert _detect_schema(data) == "current"

    def test_detect_current_schema_empty(self):
        """An empty links list is detected as current schema."""
        data = {"links": []}
        assert _detect_schema(data) == "current"

    def test_detect_legacy_schema_with_keywords(self):
        """A dict with 'links' containing 'keywords' field is detected as legacy."""
        data = {
            "links": [
                {"name": "Test", "path": "https://example.com", "keywords": ["test"]}
            ]
        }
        assert _detect_schema(data) == "legacy"


class TestDoImport:
    """Test the do_import function."""

    @pytest.fixture
    def config_setup(self, tmp_path, monkeypatch):
        """Set up a temporary config and links file for testing."""
        from link4000.utils import config

        config_file = tmp_path / "config.toml"
        config_file.write_text(f'[global]\nlinks_file = "{tmp_path / "links.json"}"\n')
        monkeypatch.setattr(config, "_CONFIG_PATH", str(config_file))
        monkeypatch.setattr(config, "_config", None)

        return tmp_path

    def test_import_file_not_found(self, config_setup):
        """do_import returns error when file doesn't exist."""
        added, skipped, updated, error = do_import("/nonexistent/file.json")
        assert error is not None
        assert "File not found" in error
        assert added == 0
        assert skipped == 0
        assert updated == 0

    def test_import_invalid_json(self, config_setup):
        """do_import returns error for invalid JSON."""
        bad_file = config_setup / "bad.json"
        bad_file.write_text("{ invalid json }")

        added, skipped, updated, error = do_import(str(bad_file))
        assert error is not None
        assert "Invalid JSON" in error
        assert added == 0

    def test_import_empty_file(self, config_setup):
        """do_import returns success with zero counts for empty links."""
        empty_file = config_setup / "empty.json"
        empty_file.write_text('{"links": []}')

        added, skipped, updated, error = do_import(str(empty_file))
        assert error is None
        assert added == 0
        assert skipped == 0
        assert updated == 0

    def test_import_current_schema(self, config_setup):
        """do_import successfully imports links in current schema."""
        import_file = config_setup / "import.json"
        import_file.write_text(
            json.dumps(
                {
                    "links": [
                        {
                            "id": "test-1",
                            "title": "Test Link",
                            "url": "https://example.com",
                            "tags": ["test"],
                        }
                    ]
                }
            )
        )

        added, skipped, updated, error = do_import(str(import_file))
        assert error is None
        assert added == 1
        assert skipped == 0
        assert updated == 0

    def test_import_legacy_schema(self, config_setup):
        """do_import successfully imports links in legacy schema."""
        import_file = config_setup / "legacy.json"
        import_file.write_text(
            json.dumps(
                [
                    {
                        "name": "Legacy Link",
                        "path": "https://legacy.com",
                        "keywords": ["legacy"],
                    }
                ]
            )
        )

        added, skipped, updated, error = do_import(str(import_file))
        assert error is None
        assert added == 1
        assert skipped == 0
        assert updated == 0

    def test_import_with_duplicates_skip(self, config_setup):
        """do_import skips duplicates when override=False."""
        import_file = config_setup / "import.json"
        import_file.write_text(
            json.dumps(
                {
                    "links": [
                        {
                            "id": "test-1",
                            "title": "Test Link",
                            "url": "https://example.com",
                            "tags": ["test"],
                        }
                    ]
                }
            )
        )

        # Import once
        added1, _, _, _ = do_import(str(import_file))
        assert added1 == 1

        # Import again with override=False
        added2, skipped2, updated2, error2 = do_import(
            str(import_file), override=False
        )
        assert error2 is None
        assert added2 == 0
        assert skipped2 == 1
        assert updated2 == 0

    def test_import_with_duplicates_override(self, config_setup):
        """do_import overwrites duplicates when override=True."""
        import_file = config_setup / "import.json"
        import_file.write_text(
            json.dumps(
                {
                    "links": [
                        {
                            "id": "test-1",
                            "title": "Test Link",
                            "url": "https://example.com",
                            "tags": ["test"],
                        }
                    ]
                }
            )
        )

        # Import once
        added1, _, _, _ = do_import(str(import_file))
        assert added1 == 1

        # Import again with override=True
        added2, skipped2, updated2, error2 = do_import(str(import_file), override=True)
        assert error2 is None
        assert added2 == 0
        assert skipped2 == 0
        assert updated2 == 1
