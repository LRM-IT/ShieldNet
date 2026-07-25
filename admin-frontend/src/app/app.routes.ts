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
import { LoginComponent } from './pages/login.component';
import { PlatformLoginComponent } from './pages/platform-login.component';
import { EnterpriseDashboardComponent } from './pages/enterprise-dashboard.component';
import { GuildComponent } from './pages/guild.component';
import { ProfileComponent } from './pages/profile.component';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: 'control/auth', component: PlatformLoginComponent },
  { path: 'profile', component: ProfileComponent, canActivate: [authGuard] },
  { path: 'platform/access', component: PlatformAccessComponent, canActivate: [authGuard] },
  { path: 'platform/plugins', component: PluginsComponent, canActivate: [authGuard] },
  { path: 'platform/jobs', component: JobsCenterComponent, canActivate: [authGuard] },
  { path: 'platform/operations', component: OperationsComponent, canActivate: [authGuard] },
  { path: 'platform/health', component: HealthMonitorComponent, canActivate: [authGuard] },
  { path: 'platform/logs', component: LiveLogsComponent, canActivate: [authGuard] },
  { path: 'platform/notifications', component: NotificationsComponent, canActivate: [authGuard] },
  { path: 'platform/doctor', component: DoctorComponent, canActivate: [authGuard] },
  {
    path: '',
    component: EnterpriseDashboardComponent,
    canActivate: [authGuard],
  },
  {
    path: 'guild/:guildId',
    component: GuildComponent,
    canActivate: [authGuard],
  },
  { path: 'guild/:guildId/explorer', component: ExplorerComponent, canActivate: [authGuard] },
  { path: 'guild/:guildId/permission-simulator', component: PermissionSimulatorComponent, canActivate: [authGuard] },
  { path: 'guild/:guildId/server-diff', component: ServerDiffComponent, canActivate: [authGuard] },
  { path: 'guild/:guildId/backups', component: BackupsComponent, canActivate: [authGuard] },
  { path: 'guild/:guildId/automations', component: AutomationsComponent, canActivate: [authGuard] },
  { path: 'guild/:guildId/plugin-runtime', component: PluginRuntimeUsageComponent, canActivate: [authGuard] },
  { path: 'guild/:guildId/automation-monitor', component: AutomationMonitorComponent, canActivate: [authGuard] },
  { path: 'guild/:guildId/workflow-scheduler', component: WorkflowSchedulerComponent, canActivate: [authGuard] },
  {
    path: 'guild/:guildId/members',
    component: MembersComponent,
    canActivate: [authGuard],
  },
  { path: 'guild/:guildId/members/:userId', component: MemberInspectorComponent, canActivate: [authGuard] },
  {
    path: 'guild/:guildId/moderation',
    component: ModerationOperationsComponent,
    canActivate: [authGuard],
  },
  {
    path: 'guild/:guildId/security',
    component: SecurityComponent,
    canActivate: [authGuard],
  },
  {
    path: 'guild/:guildId/audit',
    component: AuditComponent,
    canActivate: [authGuard],
  },
  {
    path: 'guild/:guildId/permissions',
    component: PermissionsComponent,
    canActivate: [authGuard],
  },
  {
    path: 'guild/:guildId/verification',
    component: VerificationComponent,
    canActivate: [authGuard],
  },
  {
    path: 'guild/:guildId/control',
    component: ServerControlComponent,
    canActivate: [authGuard],
  },
  { path: '**', redirectTo: '' },
];
