import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { GuildAccess } from './api.models';

@Injectable({ providedIn: 'root' })
export class GuildService {
  constructor(private readonly http: HttpClient) {}

  list(): Promise<GuildAccess[]> {
    return firstValueFrom(
      this.http.get<GuildAccess[]>('/api/v1/discord/guilds'),
    );
  }

  remove(guildId: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`/api/v1/discord/guilds/${guildId}`));
  }
}
