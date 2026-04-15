## FIXME
- icon disappears sometimes (after reload? when moving window across monitors?)

## TODO
- add NOT filter option (match all tags NOT having tag)
- add dialog for managing exclusions (separate dialog or main list with hidden items shown?)
- UX: what buttons do we need in the main list?
- add indexing of items to enable full text search
- add browser history
- add chrome favorites

## DONE (not yet tested)
- make source plugins configurable via config.toml with per-source options
- add max_age_days option for recent file plugins (Windows, Linux/GNOME, Office)
- fix GUI freeze when opening file-type filter dialog (pre-compute link types in background)
- resolve links on OneDrive to sharepoint URLs (automatic resolution using Microsoft Graph API with Azure CLI auth)

## NOT PLANNED
- add auto-update mechanism ← this needs public distribution of a binary which introduces licensing issues