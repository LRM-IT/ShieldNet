import { HealthMonitorComponent } from './pages/health-monitor.component';
import { LiveLogsComponent } from './pages/live-logs.component';
import { PluginRuntimeUsageComponent } from './pages/plugin-runtime-usage.component';
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
import { ModerationOperationsComponent } from './pages/moderation-operations.component';
import { MembersComponent } from './pages/members.component';
import { ServerControlComponent } from './pages/server-control.component';
import { VerificationComponent } from './pages/verification.component';
import { PermissionsComponent } from './pages/permissions.component';
import { AuditComponent } from './pages/audit.component';
import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';
import { guildGuard, platformGuard } from './core/context.guards';
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

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: 'control/auth', component: PlatformLoginComponent },
  { path: 'profile', component: ProfileComponent, canActivate: [authGuard] },
  { path: 'access-denied', component: AccessDeniedComponent },
  { path: 'servers', component: ServerSelectorComponent, canActivate: [authGuard] },
  { path: 'platform/access', component: PlatformAccessComponent, canActivate: [platformGuard] },
  { path: 'platform/plugins', component: PluginsComponent, canActivate: [platformGuard] },
  { path: 'platform/jobs', component: JobsCenterComponent, canActivate: [platformGuard] },
  { path: 'platform/operations', component: OperationsComponent, canActivate: [platformGuard] },
  { path: 'platform/health', component: HealthMonitorComponent, canActivate: [platformGuard] },
  { path: 'platform/logs', component: LiveLogsComponent, canActivate: [platformGuard] },
  { path: 'platform/notifications', component: NotificationsComponent, canActivate: [platformGuard] },
  { path: 'platform/doctor', component: DoctorComponent, canActivate: [platformGuard] },
  { path: '', component: LandingComponent, canActivate: [authGuard] },
  { path: 'platform', component: EnterpriseDashboardComponent, canActivate: [platformGuard] },
  {
    path: 'guild/:guildId',
    component: GuildComponent,
    canActivate: [guildGuard],
  },
  { path: 'guild/:guildId/access-overview', component: GuildAccessOverviewComponent, canActivate: [guildGuard] },
{ path: 'guild/:guildId/access', component: GuildAccessComponent, canActivate: [guildGuard], data: { guildModule: 'access' } },
  { path: 'guild/:guildId/explorer', component: ExplorerComponent, canActivate: [guildGuard], data: { guildModule: 'members' } },
  { path: 'guild/:guildId/permission-simulator', component: PermissionSimulatorComponent, canActivate: [guildGuard], data: { guildModule: 'settings' } },
  { path: 'guild/:guildId/server-diff', component: ServerDiffComponent, canActivate: [guildGuard], data: { guildModule: 'settings' } },
  { path: 'guild/:guildId/backups', component: BackupsComponent, canActivate: [guildGuard], data: { guildModule: 'settings' } },
  { path: 'guild/:guildId/automations', component: AutomationsComponent, canActivate: [guildGuard], data: { guildModule: 'automations' } },
  { path: 'guild/:guildId/plugin-runtime', component: PluginRuntimeUsageComponent, canActivate: [guildGuard], data: { guildModule: 'plugins' } },
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
