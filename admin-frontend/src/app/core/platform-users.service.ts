import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface PlatformOwnerGuild {
  guild_id: string;
  name: string;
  icon_url: string | null;
  status: string;
  bot_status: string;
}

export interface PlatformOwner {
  id: string;
  display_name: string | null;
  login: string;
  email: string;
  email_verified: boolean;
  avatar_url: string | null;
  discord_user_id: string | null;
  status: string;
  preferred_locale: string | null;
  last_login_at: string | null;
  created_at: string;
  guilds: PlatformOwnerGuild[];
}

@Injectable({ providedIn: 'root' })
export class PlatformUsersService {
  constructor(private readonly http: HttpClient) {}

  list(search = ''): Observable<{ items: PlatformOwner[]; total: number }> {
    const params = search ? new HttpParams().set('search', search) : undefined;
    return this.http.get<{ items: PlatformOwner[]; total: number }>('/api/v1/platform/users', { params });
  }

  sendDm(userId: string, message: string): Observable<{ id: string; status: string }> {
    return this.http.post<{ id: string; status: string }>(`/api/v1/platform/users/${userId}/dm`, { message });
  }
}
