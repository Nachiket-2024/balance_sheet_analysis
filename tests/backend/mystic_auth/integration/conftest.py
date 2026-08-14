# tests/backend/mystic_auth/integration/conftest.py
#
# Forces settings.DEFAULT_APP_POLICIES = "" for this suite. Several
# integration tests assert an exact policy/permission set after
# create_verified_user(...), which goes through the real signup -> verify
# flow and therefore really calls assign_app_default_policies (unlike the
# unit tests in test_oauth2_service_unit.py, which mock that call out). If a
# downstream app sets DEFAULT_APP_POLICIES (e.g. to "app_self_service") in
# the .env this suite reads, those extra policies would get assigned on top
# of what these tests expect and break their exact-set assertions, for a
# reason entirely unrelated to what each test is actually checking. Forcing
# it empty here decouples this suite's assertions from whatever a downstream
# app happens to configure, the same way the oauth2 unit tests were made
# independent of it.
from backend.mystic_auth.core.settings import settings

settings.DEFAULT_APP_POLICIES = ""
