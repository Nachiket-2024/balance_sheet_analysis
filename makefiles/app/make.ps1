# Your own make.ps1 targets. Ships empty - add whatever you want here as
# more $AppTargets hashtable entries (e.g. "deploy-staging" = { ... }).
# Merged into the root make.ps1 dispatch after makefiles/mystic_auth/make.ps1,
# so a target here with the same name overrides the upstream one. Upstream
# never edits this file again. See
# docs/mystic_auth/template-usage/ownership-split.md.

$AppTargets = @{}
