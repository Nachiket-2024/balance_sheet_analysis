# Thin, stable entry point - the real targets live in
# makefiles/mystic_auth/Makefile (upstream-owned) and makefiles/app/Makefile
# (yours, ships empty), the same app/mystic_auth split as everything else in
# this repo. This file itself should rarely if ever need to change, so a
# sync almost never touches it. `make` has no built-in Windows version
# outside WSL/Git Bash, so native Windows PowerShell users should run the
# same targets via `.\make.ps1 <target>` instead (root make.ps1, ships with
# every Windows install, no extra tool needed). See
# docs/mystic_auth/template-usage/ownership-split.md.
include makefiles/mystic_auth/Makefile
-include makefiles/app/Makefile
