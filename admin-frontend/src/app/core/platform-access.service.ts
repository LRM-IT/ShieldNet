export interface PlatformDiscordAdmin { id:string; discord_user_id:string; role:string; display_name?:string|null; description?:string|null; is_active:boolean; expires_at?:string|null; last_login_at?:string|null; created_at:string; }
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface PlatformAccessIdentity {
  user_id: string;
  discord_user_id: string | null;
  roles: string[];
  highest_role: string | null;
  is_superadmin: boolean;
  superadmin_source: string | null;
  auth_source?: string;
  can_manage_platform_admins?: boolean;
}

export interface PlatformAccessOverview {
  guild_count: number;
  active_memberships: number;
  user_count: number;
  configured_superadmins: number;
  configuration_key: string;
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

  discordAdmins() { return this.http.get<PlatformDiscordAdmin[]>('/api/v1/platform/access/discord-admins'); }
  addDiscordAdmin(payload: {discord_user_id:string; role:string; display_name?:string; description?:string}) { return this.http.post<PlatformDiscordAdmin>('/api/v1/platform/access/discord-admins', payload); }
  updateDiscordAdmin(id:string,payload:Partial<PlatformDiscordAdmin>) { return this.http.patch<PlatformDiscordAdmin>(`/api/v1/platform/access/discord-admins/${id}`, payload); }
  deleteDiscordAdmin(id:string) { return this.http.delete(`/api/v1/platform/access/discord-admins/${id}`); }
}
