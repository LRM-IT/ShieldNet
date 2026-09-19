import { TemplateDesignerComponent } from './pages/template-designer.component';
import { MediaAssetsComponent } from './pages/media-assets.component';
import { TemplateBankComponent } from './pages/template-bank.component';
import { GuildAIComponent } from './pages/guild-ai.component';
import { PlatformLanguagesComponent } from './pages/platform-languages.component';
import { GuildLanguagesComponent } from './pages/guild-languages.component';
import { PluginVotingComponent } from './pages/plugin-voting.component';
import { VotingTemplatesComponent } from './pages/voting-templates.component';
import { HealthMonitorComponent } from './pages/health-monitor.component';
import { LiveLogsComponent } from './pages/live-logs.component';
import { PluginRuntimeUsageComponent } from './pages/plugin-runtime-usage.component';
import { GuildDMBroadcastComponent } from './pages/guild-dm-broadcast.component';
import { PluginWelcomeComponent } from './pages/plugin-welcome.component';
import { PluginAntiFloodComponent } from './pages/plugin-antiflood.component';
import { PluginFirstIntroductionComponent } from './pages/plugin-first-introduction.component';
import { PluginTranslatorGroupsComponent } from './pages/plugin-translator-groups.component';
import { PluginRoleMenuComponent } from './pages/plugin-role-menu.component';
import { PluginAIAutoModComponent } from './pages/plugin-ai-automod.component';
import { PluginEventManagerComponent } from './pages/plugin-event-manager.component';
import { PluginWarPlannerComponent } from './pages/plugin-war-planner.component';
import { PluginActivityRankingComponent } from './pages/plugin-activity-ranking.component';
import { PluginAuditSecurityComponent } from './pages/plugin-audit-security.component';
import { PluginCrossGuildNetworkComponent } from './pages/plugin-cross-guild-network.component';
import { PluginsComponent } from './pages/plugins.component';
import { AIIntegrationsComponent } from './pages/ai-integrations.component';
import { LeadershipComponent } from './pages/leadership.component';
import { WorkflowSchedulerComponent } from './pages/workflow-scheduler.component';
import { BackupsComponent } from './pages/backups.component';
import { AutomationMonitorComponent } from './pages/automation-monitor.component';
import { AutomationsComponent } from './pages/automations.component';
import { DoctorComponent } from './pages/doctor.component';
import { ServerDiffComponent } from './pages/server-diff.component';
import { PermissionSimulatorComponent } from './pages/permission-simulator.component';
import { MemberInspectorComponent } from './pages/member-inspector.component';
import { ExplorerComponent } from './pages/explorer.component';
import { NotificationsComponent } from './pages/notifications.component';
import { OperationsComponent } from './pages/operations.component';
import { SecurityComponent } from './pages/security.component';
import { JobsCenterComponent } from './pages/jobs-center.component';
import { PlatformAccessComponent } from './pages/platform-access.component';
import { PlatformUsersComponent } from './pages/platform-users.component';
import { PlatformUserProfileComponent } from './pages/platform-user-profile.component';
import { ModerationOperationsComponent } from './pages/moderation-operations.component';
import { MembersComponent } from './pages/members.component';
import { ServerControlComponent } from './pages/server-control.component';
import { VerificationComponent } from './pages/verification.component';
import { PermissionsComponent } from './pages/permissions.component';
import { AuditComponent } from './pages/audit.component';
import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';
import { guildGuard, platformGuard, superadminGuard } from './core/context.guards';
import { LoginComponent } from './pages/login.component';
import { PlatformLoginComponent } from './pages/platform-login.component';
import { EnterpriseDashboardComponent } from './pages/enterprise-dashboard.component';
import { GuildComponent } from './pages/guild.component';
import { ProfileComponent } from './pages/profile.component';
import { LandingComponent } from './pages/landing.component';
import { ServerSelectorComponent } from './pages/server-selector.component';
import { AccessDeniedComponent } from './pages/access-denied.component';
import { GuildAccessComponent } from './pages/guild-access.component';

import { GuildAccessOverviewComponent } from './pages/guild-access-overview.component';
import { BillingComponent } from './pages/billing.component';
import { GuildBillingComponent } from './pages/guild-billing.component';
import { DocumentationComponent } from './pages/documentation.component';
import { SupportComponent } from './pages/support.component';
import { MerchantInformationComponent } from './pages/merchant-information.component';
import { SeoComponent } from './pages/seo.component';
import { SystemSettingsComponent } from './pages/system-settings.component';
import { PublicDocumentationComponent } from './pages/public-documentation.component';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: 'control/auth', component: PlatformLoginComponent },
  { path: 'profile', component: ProfileComponent, canActivate: [authGuard] },
  { path: 'access-denied', component: AccessDeniedComponent },
  { path: 'servers', component: ServerSelectorComponent, canActivate: [authGuard] },
  { path: 'billing', component: GuildBillingComponent, canActivate: [authGuard] },
  { path: 'documentation', component: DocumentationComponent, canActivate: [authGuard] },
  { path: 'support', component: SupportComponent, canActivate: [authGuard] },
  { path: 'privacy-policy', component: MerchantInformationComponent },
  { path: 'docs', component: PublicDocumentationComponent },
  { path: 'merchant-information', redirectTo: 'privacy-policy', pathMatch: 'full' },
  { path: 'platform/languages', component: PlatformLanguagesComponent },
  { path: 'platform/template-bank', component: TemplateBankComponent, canActivate: [platformGuard] },
  { path: 'platform/voting-templates', component: VotingTemplatesComponent, canActivate: [platformGuard] },
  { path: 'platform/media-assets', component: MediaAssetsComponent, canActivate: [platformGuard] },
  { path: 'platform/template-designer', component: TemplateDesignerComponent, canActivate: [platformGuard] },
  { path: 'platform/access', component: PlatformAccessComponent, canActivate: [platformGuard] },
  { path: 'platform/users', component: PlatformUsersComponent, canActivate: [superadminGuard] },
  { path: 'platform/users/:userId', component: PlatformUserProfileComponent, canActivate: [superadminGuard] },
  { path: 'platform/plugins', component: PluginsComponent, canActivate: [platformGuard] },
  { path: 'platform/billing', component: BillingComponent, canActivate: [superadminGuard] },
  { path: 'platform/system-settings', component: SystemSettingsComponent, canActivate: [superadminGuard] },
  { path: 'platform/seo', component: SeoComponent, canActivate: [superadminGuard] },
  { path: 'platform/privacy-policy', component: MerchantInformationComponent, canActivate: [superadminGuard] },
  { path: 'platform/jobs', component: JobsCenterComponent, canActivate: [platformGuard] },
  { path: 'platform/operations', component: OperationsComponent, canActivate: [platformGuard] },
  { path: 'platform/health', component: HealthMonitorComponent, canActivate: [platformGuard] },
  { path: 'platform/logs', component: LiveLogsComponent, canActivate: [platformGuard] },
  { path: 'platform/notifications', component: NotificationsComponent, canActivate: [platformGuard] },
  { path: 'platform/doctor', component: DoctorComponent, canActivate: [platformGuard] },
  { path: '', component: LoginComponent },
  { path: 'app', component: LandingComponent, canActivate: [authGuard] },
  { path: 'platform', component: EnterpriseDashboardComponent, canActivate: [platformGuard] },
  {
    path: 'guild/:guildId',
    component: GuildComponent,
    canActivate: [guildGuard],
  },
  { path: 'guild/:guildId/access-overview', component: GuildAccessOverviewComponent, canActivate: [guildGuard] },
  { path: 'guild/:guildId/billing', redirectTo: '/billing' },
{ path: 'guild/:guildId/access', component: GuildAccessComponent, canActivate: [guildGuard], data: { guildModule: 'access' } },
  { path: 'guild/:guildId/explorer', component: ExplorerComponent, canActivate: [guildGuard], data: { guildModule: 'members' } },
  { path: 'guild/:guildId/ai', component: GuildAIComponent, canActivate: [guildGuard], data: { guildModule: 'settings' } },
  { path: 'guild/:guildId/languages', component: GuildLanguagesComponent, canActivate: [guildGuard], data: { guildModule: 'settings' } },
  { path: 'guild/:guildId/permission-simulator', component: PermissionSimulatorComponent, canActivate: [guildGuard], data: { guildModule: 'settings' } },
  { path: 'guild/:guildId/server-diff', component: ServerDiffComponent, canActivate: [guildGuard], data: { guildModule: 'settings' } },
  { path: 'guild/:guildId/backups', component: BackupsComponent, canActivate: [guildGuard], data: { guildModule: 'settings' } },
  { path: 'guild/:guildId/automations', component: AutomationsComponent, canActivate: [guildGuard], data: { guildModule: 'automations' } },
  { path: 'guild/:guildId/plugin-runtime', component: PluginRuntimeUsageComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/documentation', component: DocumentationComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/:pluginKey/documentation', component: DocumentationComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/guild-dm-broadcast', component: GuildDMBroadcastComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/welcome', component: PluginWelcomeComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/antiflood', component: PluginAntiFloodComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/language-selection', component: PluginFirstIntroductionComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/translator-groups', component: PluginTranslatorGroupsComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/role-menu', component: PluginRoleMenuComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/ai-automod', component: PluginAIAutoModComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/event-manager', component: PluginEventManagerComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/war-planner', component: PluginWarPlannerComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/activity-ranking', component: PluginActivityRankingComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/audit-security', component: PluginAuditSecurityComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/plugins/cross-guild-network', component: PluginCrossGuildNetworkComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/reaction-roles', redirectTo: 'guild/:guildId/plugins/role-menu', pathMatch: 'full' },
  { path: 'guild/:guildId/plugins/voting', component: PluginVotingComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
  { path: 'guild/:guildId/automation-monitor', component: AutomationMonitorComponent, canActivate: [guildGuard], data: { guildModule: 'automations' } },
  { path: 'guild/:guildId/workflow-scheduler', component: WorkflowSchedulerComponent, canActivate: [guildGuard], data: { guildModule: 'automations' } },
  {
    path: 'guild/:guildId/members',
    component: MembersComponent,
    canActivate: [guildGuard],
    data: { guildModule: 'members' },
  },
  { path: 'guild/:guildId/members/:userId', component: MemberInspectorComponent, canActivate: [guildGuard], data: { guildModule: 'members' } },
  {
    path: 'guild/:guildId/moderation',
    component: ModerationOperationsComponent,
    canActivate: [guildGuard],
    data: { guildModule: 'moderation' },
  },
  {
    path: 'guild/:guildId/security',
    component: SecurityComponent,
    canActivate: [guildGuard],
    data: { guildModule: 'security' },
  },
  {
    path: 'guild/:guildId/audit',
    component: AuditComponent,
    canActivate: [guildGuard],
    data: { guildModule: 'audit' },
  },
  {
    path: 'guild/:guildId/permissions',
    component: PermissionsComponent,
    canActivate: [guildGuard],
    data: { guildModule: 'settings' },
  },
  {
    path: 'guild/:guildId/verification',
    component: VerificationComponent,
    canActivate: [guildGuard],
    data: { guildModule: 'verification' },
  },
  {
    path: 'guild/:guildId/control',
    component: ServerControlComponent,
    canActivate: [guildGuard],
    data: { guildModule: 'settings' },
  },
  { path: '**', redirectTo: '' },
];
