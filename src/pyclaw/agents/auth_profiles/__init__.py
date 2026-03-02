"""Auth profile management — multi-mode credential store."""

from pyclaw.agents.auth_profiles.profiles import (
    list_profiles_for_provider,
    mark_auth_profile_good,
    set_auth_profile_order,
    upsert_auth_profile,
)
from pyclaw.agents.auth_profiles.store import (
    ensure_auth_profile_store,
    load_auth_profile_store,
    save_auth_profile_store,
    update_auth_profile_store_with_lock,
)
from pyclaw.agents.auth_profiles.types import (
    ApiKeyCredential,
    AuthProfileCredential,
    AuthProfileStore,
    OAuthCredential,
    ProfileUsageStats,
    TokenCredential,
)
from pyclaw.agents.auth_profiles.usage import (
    is_profile_in_cooldown,
    mark_auth_profile_cooldown,
    mark_auth_profile_failure,
    mark_auth_profile_used,
)

__all__ = [
    "ApiKeyCredential",
    "AuthProfileCredential",
    "AuthProfileStore",
    "OAuthCredential",
    "ProfileUsageStats",
    "TokenCredential",
    "ensure_auth_profile_store",
    "is_profile_in_cooldown",
    "list_profiles_for_provider",
    "load_auth_profile_store",
    "mark_auth_profile_cooldown",
    "mark_auth_profile_failure",
    "mark_auth_profile_good",
    "mark_auth_profile_used",
    "save_auth_profile_store",
    "set_auth_profile_order",
    "update_auth_profile_store_with_lock",
    "upsert_auth_profile",
]
