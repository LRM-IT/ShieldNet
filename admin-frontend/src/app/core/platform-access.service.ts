import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface PlatformAccessIdentity {
  user_id: string;
  discord_user_id: string | null;
  roles: string[];
  highest_role: string | null;
  is_superadmin: boolean;
  auth_source: string;
  platform_role?: string | null;
  has_platform_access?: boolean;
  can_manage_platform_admins?: boolean;
}

export interface PlatformAccessOverview {
  guild_count: number;
  active_memberships: number;
  user_count: number;
  configured_superadmins: number;
  configuration_key: string;
}

export interface PlatformDiscordAdmin {
  id: string;
  discord_user_id: string;
  role: 'platform_admin' | 'platform_operator' | 'platform_auditor';
  display_name?: string | null;
  description?: string | null;
  is_active: boolean;
  expires_at?: string | null;
  last_login_at?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface PlatformDiscordAdminCreate {
  discord_user_id: string;
  role: PlatformDiscordAdmin['role'];
  display_name?: string;
  description?: string;
  expires_at?: string | null;
}


export interface PlatformSession {
  id: string;
  user_id: string;
  display_name: string;
  login: string;
  discord_user_id?: string | null;
  auth_source: string;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
  expires_at: string;
  revoked_at?: string | null;
  active: boolean;
}

export interface PlatformLoginAttempt {
  id: number;
  user_id?: string | null;
  display_name?: string | null;
  email?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  successful: boolean;
  failure_reason?: string | null;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class PlatformAccessService {
  constructor(private readonly http: HttpClient) {}

  identity(): Observable<PlatformAccessIdentity> {
    return this.http.get<PlatformAccessIdentity>('/api/v1/platform/access/me');
  }

  overview(): Observable<PlatformAccessOverview> {
    return this.http.get<PlatformAccessOverview>('/api/v1/platform/access/overview');
  }

  discordAdmins(): Observable<PlatformDiscordAdmin[]> {
    return this.http.get<PlatformDiscordAdmin[]>('/api/v1/platform/access/discord-admins');
  }

  addDiscordAdmin(payload: PlatformDiscordAdminCreate): Observable<PlatformDiscordAdmin> {
    return this.http.post<PlatformDiscordAdmin>('/api/v1/platform/access/discord-admins', payload);
  }

  updateDiscordAdmin(id: string, payload: Partial<PlatformDiscordAdmin>): Observable<PlatformDiscordAdmin> {
    return this.http.patch<PlatformDiscordAdmin>(`/api/v1/platform/access/discord-admins/${id}`, payload);
  }

  revokeSessions(id: string): Observable<void> {
    return this.http.post<void>(`/api/v1/platform/access/discord-admins/${id}/revoke-sessions`, {});
  }

  deleteDiscordAdmin(id: string): Observable<void> {
    return this.http.delete<void>(`/api/v1/platform/access/discord-admins/${id}`);
  }

  sessions(): Observable<PlatformSession[]> {
    return this.http.get<PlatformSession[]>('/api/v1/platform/access/sessions');
  }

  revokeSession(id: string): Observable<void> {
    return this.http.post<void>(`/api/v1/platform/access/sessions/${id}/revoke`, {});
  }

  loginAttempts(): Observable<PlatformLoginAttempt[]> {
    return this.http.get<PlatformLoginAttempt[]>('/api/v1/platform/access/login-attempts');
  }
}
