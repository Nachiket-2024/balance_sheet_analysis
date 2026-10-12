# Third-party notices

This directory lists the application dependency licenses: one file per
package under `backend/` (Python, 66 packages) or `frontend/` (npm production
bundle, 131 packages). Each file has the package's name, version, license
identifier, copyright line, and full license text. Any package `NOTICE` file
is included with that package's license.

The backend runtime image copies its notices to
`/usr/share/licenses/mystic-auth/backend/`. The production frontend serves its
notices at `/third-party-notices/`. This keeps the notices available with the
application artifacts instead of leaving them only in the source checkout.

This inventory covers Python and npm application dependencies. The
`db_backup` image includes rclone's source and Go-module license files under
`/usr/share/licenses/mystic-auth/db-backup/rclone/`, generated from the exact
source used to build its binary. The Debian Trixie PostgreSQL runtime package
inventory is recorded in `debian/packages.tsv`, and the corresponding package
copyright/license files and common license texts are copied from
`/usr/share/doc/` into `/usr/share/licenses/mystic-auth/db-backup/debian/` in
the image. CI checks that the inventory and a substantial set of upstream
copyright files are present. The exact image SBOM remains the package-level
record; the notice bundle is a convenience copy of the distro's upstream
notices, not a legal determination of license obligations.

Split as one file per package (not one combined file) so a dependency
bump's diff touches only the packages that actually changed, not a single
multi-thousand-line file shifting around on every regeneration.

## Regenerating

Backend (run from an isolated venv built from `backend/requirements.txt`,
not the host environment - the installed set differs):

```bash
pip install pip-licenses
pip-licenses --format=json --with-license-file --no-license-path --with-urls
```

Frontend (production dependencies only):

```bash
cd frontend
npx license-checker-rseidelsohn --production --excludePackages "frontend@0.0.0" --json
```

Write one `backend/<name>-<version>.txt` or `frontend/<name>.txt` file per
entry. Include the package name, version, license identifier, source URL,
copyright line, full license text, and any package `NOTICE` file. The npm
inventory command reports metadata; copy the actual license and notice files
from each matching package in `frontend/node_modules/`, rather than treating
the license identifier as a substitute for its text. If an npm package omits
its license file, retrieve it from the matching source release and record the
source used. Review the changed inventory against the production dependency
list before distributing an image.
