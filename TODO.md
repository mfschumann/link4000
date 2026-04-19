## FIXME
- icon disappears sometimes (after reload? when moving window across monitors?)

## TODO
- resolve links on OneDrive to sharepoint URLs
- add NOT filter option (match all tags NOT having tag)
- add dialog for managing exclusions (separate dialog or main list with hidden items shown?)
- UX: what buttons do we need in the main list?
- add "resolve" checkbox in add/edit dialog
- add indexing of items to enable full text search
- add browser history
- add chrome favorites

## DONE (not yet tested)
- moved source plugins into source_plugins package (2025-04-19)
  - JsonStoreSource moved from link_store.py to json_store.py
  - recent_docs.py split into Windows (recent_docs_windows.py) and LinuxGnome (recent_docs_linux_gnome.py) plugins
  - edge_favorites.py and office_recent_docs.py moved to source_plugins/
  - source_registry now auto-imports from source_plugins package

## NOT PLANNED
- add auto-update mechanism ← this needs public distribution of a binary which introduces licensing issues
