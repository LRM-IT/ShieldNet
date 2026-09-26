import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class GuildRoleService {
  constructor(private readonly http: HttpClient) {}
  list(guildId: string, includeUnassignable = false): Promise<any[]> {
    const suffix = includeUnassignable ? '?include_unassignable=true' : '';
    return firstValueFrom(
      this.http.get<any[]>(`/api/v1/discord/guilds/${guildId}/roles${suffix}`),
    );
  }
}
