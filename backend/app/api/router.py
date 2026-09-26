from app.api.routes.plugin_usage import (
    router as plugin_usage_router,
)

from app.api.routes.plugin_rate_limits import (
    router as plugin_rate_limits_router,
)

from app.api.routes.plugin_runtime_gateway import (
    router as plugin_runtime_gateway_router,
)

from app.api.routes.moderation import router as moderation_router
from app.api.routes.events import router as events_router
from fastapi import APIRouter
from app.api.routes.platform_ai import router as platform_ai_router
from app.api.routes.ai_diagnostics import router as ai_diagnostics_router
from app.api.routes.billing import router as billing_router
from app.api.routes.support import router as support_router
from app.api.routes.merchant_page import router as merchant_page_router
from app.api.routes.public_locale import router as public_locale_router
from app.api.routes.public_exchange_rate import router as public_exchange_rate_router
from app.api.routes.seo import router as seo_router
from app.api.routes.maintenance import router as maintenance_router
from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.backups import router as backups_router
from app.api.routes.automations import router as automations_router
from app.api.routes.automation_schedules import router as automation_schedules_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.doctor import router as doctor_router
from app.api.routes.enterprise_dashboard import router as enterprise_dashboard_router
from app.api.routes.explorer import router as explorer_router
from app.api.routes.internal_explorer import router as internal_explorer_router
from app.api.routes.internal_automations import router as internal_automations_router
from app.api.routes.internal_ai import router as internal_ai_router
from app.api.routes.discord_guilds import router as discord_guilds_router
from app.api.routes.guild_registry import router as guild_registry_router
from app.api.routes.guild_roles import router as guild_roles_router
from app.api.routes.health import router as health_router
from app.api.routes.internal_discord import router as internal_discord_router
from app.api.routes.internal_guild_roles import router as internal_guild_roles_router
from app.api.routes.internal_member_actions import router as internal_member_actions_router
from app.api.routes.internal_members import router as internal_members_router
from app.api.routes.internal_modules import router as internal_modules_router
from app.api.routes.internal_permissions import router as internal_permissions_router
from app.api.routes.internal_verification import router as internal_verification_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.member_actions import router as member_actions_router
from app.api.routes.member_cases import router as member_cases_router
from app.api.routes.member_evidence import router as member_evidence_router
from app.api.routes.members import router as members_router
from app.api.routes.member_inspector import router as member_inspector_router
from app.api.routes.modules import router as modules_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.operations import router as operations_router
from app.api.routes.moderation_operations import router as moderation_operations_router
from app.api.routes.permissions import router as permissions_router
from app.api.routes.permission_simulator import router as permission_simulator_router
from app.api.routes.platform_access import router as platform_access_router
from app.api.routes.platform_users import router as platform_users_router
from app.api.routes.server_control import router as server_control_router
from app.api.routes.server_diff import router as server_diff_router
from app.api.routes.security import router as security_router
from app.api.routes.internal_security import router as internal_security_router
from app.api.routes.internal_runtime import router as internal_runtime_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.verification import router as verification_router
from app.api.routes.leadership import router as leadership_router
from app.api.routes.internal_leadership import router as internal_leadership_router
from app.api.routes.role_channel_management import router as role_channel_management_router
from app.api.routes.internal_role_channel_management import router as internal_role_channel_management_router
from app.api.routes.setup_wizard import router as setup_wizard_router
from app.api.routes.ai_gateway import router as ai_gateway_router
from app.api.routes.settings import router as settings_router
from app.api.routes.plugins import router as plugins_router
from app.api.routes.plugin_events import router as plugin_events_router
from app.api.routes.plugin_marketplace import router as plugin_marketplace_router
from app.api.routes.plugin_jobs import router as plugin_jobs_router
from app.api.routes.plugin_control import router as plugin_control_router
from app.api.routes.plugin_runtime_instances import router as plugin_runtime_instances_router
from app.api.routes.guild_plugins import router as guild_plugins_router
from app.api.routes.guild_access import router as guild_access_router
from app.api.routes.guild_dm_broadcast import router as guild_dm_broadcast_router, internal_router as internal_guild_dm_broadcast_router
from app.api.routes.plugin_welcome import router as plugin_welcome_router, internal_router as internal_plugin_welcome_router
from app.api.routes.plugin_antiflood import router as plugin_antiflood_router, internal_router as internal_plugin_antiflood_router
from app.api.routes.plugin_first_introduction import router as plugin_first_introduction_router, internal_router as internal_plugin_first_introduction_router
from app.api.routes.plugin_translator_groups import router as plugin_translator_groups_router, internal_router as internal_plugin_translator_groups_router
from app.api.routes.plugin_role_menu import router as plugin_role_menu_router, internal_router as internal_plugin_role_menu_router
from app.api.routes.plugin_ai_automod import router as plugin_ai_automod_router, internal_router as internal_plugin_ai_automod_router
from app.api.routes.plugin_event_manager import router as plugin_event_manager_router, internal_router as internal_plugin_event_manager_router
from app.api.routes.plugin_war_planner import router as plugin_war_planner_router, internal_router as internal_plugin_war_planner_router
from app.api.routes.plugin_activity_ranking import router as plugin_activity_ranking_router, internal_router as internal_plugin_activity_ranking_router
from app.api.routes.plugin_audit_security import router as plugin_audit_security_router, internal_router as internal_plugin_audit_security_router
from app.api.routes.plugin_cross_guild_network import router as plugin_cross_guild_network_router
from app.api.routes.core_setup_wizard import router as core_setup_wizard_router
from app.api.routes.verification_levels import router as verification_levels_router, internal_router as internal_verification_levels_router
from app.api.routes.custom_bot import router as custom_bot_router, internal_router as internal_custom_bot_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(billing_router)
api_router.include_router(support_router)
api_router.include_router(merchant_page_router)
api_router.include_router(public_locale_router)
api_router.include_router(public_exchange_rate_router)
api_router.include_router(seo_router)
api_router.include_router(maintenance_router)
api_router.include_router(auth_router)
api_router.include_router(backups_router)
api_router.include_router(automations_router)
api_router.include_router(automation_schedules_router)
api_router.include_router(dashboard_router)
api_router.include_router(doctor_router)
api_router.include_router(enterprise_dashboard_router)
api_router.include_router(explorer_router)
api_router.include_router(internal_explorer_router)
api_router.include_router(internal_automations_router)
api_router.include_router(internal_ai_router)
api_router.include_router(server_control_router)
api_router.include_router(server_diff_router)
api_router.include_router(security_router)
api_router.include_router(internal_security_router)
api_router.include_router(internal_runtime_router)
api_router.include_router(runtime_router)
api_router.include_router(discord_guilds_router)
api_router.include_router(guild_registry_router)
api_router.include_router(internal_discord_router)
api_router.include_router(modules_router)
api_router.include_router(notifications_router)
api_router.include_router(operations_router)
api_router.include_router(internal_modules_router)
api_router.include_router(members_router)
api_router.include_router(member_inspector_router)
api_router.include_router(internal_members_router)
api_router.include_router(member_actions_router)
api_router.include_router(member_cases_router)
api_router.include_router(member_evidence_router)
api_router.include_router(moderation_operations_router)
api_router.include_router(internal_member_actions_router)
api_router.include_router(guild_roles_router)
api_router.include_router(internal_guild_roles_router)
api_router.include_router(audit_router)
api_router.include_router(permissions_router)
api_router.include_router(permission_simulator_router)
api_router.include_router(platform_access_router)
api_router.include_router(platform_users_router)
api_router.include_router(jobs_router)
api_router.include_router(internal_permissions_router)
api_router.include_router(verification_router)
api_router.include_router(internal_verification_router)
api_router.include_router(verification_levels_router)
api_router.include_router(custom_bot_router)
api_router.include_router(internal_custom_bot_router)
api_router.include_router(internal_verification_levels_router)
api_router.include_router(leadership_router)
api_router.include_router(internal_leadership_router)
api_router.include_router(role_channel_management_router)
api_router.include_router(internal_role_channel_management_router)
api_router.include_router(setup_wizard_router)

api_router.include_router(ai_gateway_router)
api_router.include_router(plugins_router)
api_router.include_router(plugin_events_router)
api_router.include_router(plugin_marketplace_router)
api_router.include_router(plugin_jobs_router)
api_router.include_router(plugin_control_router)
api_router.include_router(plugin_runtime_instances_router)
api_router.include_router(guild_plugins_router)
api_router.include_router(guild_access_router)
api_router.include_router(guild_dm_broadcast_router)
api_router.include_router(internal_guild_dm_broadcast_router)
api_router.include_router(plugin_welcome_router)
api_router.include_router(internal_plugin_welcome_router)
api_router.include_router(plugin_antiflood_router)
api_router.include_router(internal_plugin_antiflood_router)
api_router.include_router(plugin_first_introduction_router)
api_router.include_router(internal_plugin_first_introduction_router)
api_router.include_router(plugin_translator_groups_router)
api_router.include_router(internal_plugin_translator_groups_router)
api_router.include_router(plugin_role_menu_router)
api_router.include_router(internal_plugin_role_menu_router)
api_router.include_router(plugin_ai_automod_router)
api_router.include_router(internal_plugin_ai_automod_router)
api_router.include_router(plugin_event_manager_router)
api_router.include_router(internal_plugin_event_manager_router)
api_router.include_router(plugin_war_planner_router)
api_router.include_router(internal_plugin_war_planner_router)
api_router.include_router(plugin_activity_ranking_router)
api_router.include_router(internal_plugin_activity_ranking_router)
api_router.include_router(plugin_audit_security_router)
api_router.include_router(internal_plugin_audit_security_router)
api_router.include_router(plugin_cross_guild_network_router)
api_router.include_router(core_setup_wizard_router)
api_router.include_router(settings_router)
api_router.include_router(moderation_router)
api_router.include_router(events_router)

api_router.include_router(platform_ai_router)
api_router.include_router(ai_diagnostics_router)
# ShieldNet Plugin Runtime Gateway
api_router.include_router(
    plugin_runtime_gateway_router
)

api_router.include_router(
    plugin_rate_limits_router
)

api_router.include_router(
    plugin_usage_router
)


