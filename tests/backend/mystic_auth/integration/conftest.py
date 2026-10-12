# tests/backend/mystic_auth/integration/conftest.py
#
# Forces app_settings.DEFAULT_APP_POLICIES = "" for this suite. Several
# integration tests assert an exact policy/permission set after
# create_verified_user(...), which goes through the real signup -> verify
# flow and really calls assign_app_default_policies. If a downstream app
# sets DEFAULT_APP_POLICIES in the .env this suite reads, those extra
# policies would get assigned on top of what these tests expect and break
# their exact-set assertions, for a reason unrelated to what each test is
# actually checking. Forcing it empty decouples this suite from whatever a
# downstream app configures.
from backend.app.core.settings import app_settings

app_settings.DEFAULT_APP_POLICIES = ""
