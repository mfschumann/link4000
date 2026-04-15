## FIXME
- icon disappears sometimes (after reload? when moving window across monitors?)
- fix onedrive to sharepoint resolution (generated path is wrong)
- exlude pattern does not work with Windows-paths
- when adding a new item using the selection dialog, paths are shown posix-style (G:/blub)
- UNC resolution translates the drive to windows-style paths (\\blub\drive), leading to mixed-style paths
- startup is slower after migration to resolve_path()
- strange lnk files from appdata\microsoft\windows\recent show as recent items (title = lnk file, target = lnk file). These did not show up before: e.g. msteamssystem-initiated (4).lnk, ms-settingstaskbar.lnk

## TODO
- resolve links on OneDrive to sharepoint URLs
- add NOT filter option (match all tags NOT having tag)
- add dialog for managing exclusions (sepsarate dialog or main list with hidden items shown?)
- UX: what buttons do we need in the main list?
- add "resolve" checkbox in add/edit dialog
- add indexing of items to enable full text search

## DONE (not yet tested)
- fix GUI freeze when opening file-type filter dialog (pre-compute link types in background)

## NOT PLANNED
- add clear button to reset search input ← double click on search input does this already
- add auto-update mechanism ← this needs public distribution of a binary which introduces licensing issues
