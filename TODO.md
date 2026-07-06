## FIXME
- icon disappears sometimes (after reload? when moving window across monitors?)

## TODO
- resolve links on OneDrive to sharepoint URLs
- add dialog for managing exclusions (separate dialog or main list with hidden items shown?)
- UX: what buttons do we need in the main list?

## DONE
- Multi-store support: named JSON stores shown as filterable "sources" in the UI.
- Shared stores: automatic 3-way merge sync (Option C) over a network share using
  portalocker locking + atomic writes, with tombstones, last-synced baseline, and
  a conflict-resolution dialog (keep local / remote / both).
- Sync triggers: startup, debounced on local change, periodic timer, and on exit.

## NOT PLANNED
- add auto-update mechanism ← this needs public distribution of a binary which introduces licensing issues
- add indexing of items to enable full text search ← out of scope, link4000 is a link manager, not a document management system
