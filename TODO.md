## FIXME
- icon disappears sometimes (after reload? when moving window across monitors?)
- intermittent Windows crash on link click: added structured logging + fixed missing try/except in `_open_parent_folder`; look at `~/.link4000/link4000.log` after next occurrence

## TODO
- resolve links on OneDrive to sharepoint URLs
- add dialog for managing exclusions (separate dialog or main list with hidden items shown?)
- UX: what buttons do we need in the main list?

## DONE
- convert `file://` URLs entered in the Add/Edit dialog to plain, percent-decoded file paths on save (Posix, Windows drive, and UNC variants; `file://localhost/...` is intentionally left unconverted)
- select the search field text (not only set focus) when the main window gains focus, so search terms can be overridden right away
- add `show_tags_column` config option ([global]); when disabled, tags are shown in the title tooltip instead
- add configurable `[[extension_groups]]` (shared name/color/color_dark/extension list) with color resolution (explicit `[extensions]`/`[extensions_dark]` entries win) and group filters in the Types section of the Filter dialog
- infer Office file type from SharePoint share tokens (`/:x:/`, `/:w:/`, `/:p:/`) for native open, link type, and colors
- fix SharePoint Doc.aspx title pre-fill to use `file=` filename instead of `Doc.aspx`
- add structured logging (file + stderr + sys.excepthook) and wrap all link-opening paths in try/except with traceback logging
- persist search term, active filters (tags/types/match mode), and full sort state (sorting_active, sort_column, sort_order) across app restarts via `ui_state.json` next to `links.json`; saved on true quit only, restored at startup after links are loaded

## NOT PLANNED
- add auto-update mechanism ← this needs public distribution of a binary which introduces licensing issues
- add indexing of items to enable full text search ← out of scope, link4000 is a link manager, not a document management system
