import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { GlobalLanguage } from './global-language.service';

export interface GuildWorkspaceLanguage extends GlobalLanguage {
  selected: boolean;
  enabled: boolean;
  is_primary: boolean;
  is_fallback: boolean;
}

export interface GuildLanguageSaveItem {
  code: string;
  enabled: boolean;
  is_primary: boolean;
  is_fallback: boolean;
  sort_order: number;
}

@Injectable({ providedIn: 'root' })
export class GuildLanguageService {
  constructor(private readonly http: HttpClient) {}

  list(guildId: string): Promise<GuildWorkspaceLanguage[]> {
    return firstValueFrom(
      this.http.get<GuildWorkspaceLanguage[]>(
        `/api/v1/discord/guilds/${guildId}/languages`,
      ),
    );
  }

  save(
    guildId: string,
    items: GuildLanguageSaveItem[],
  ): Promise<GuildWorkspaceLanguage[]> {
    return firstValueFrom(
      this.http.put<GuildWorkspaceLanguage[]>(
        `/api/v1/discord/guilds/${guildId}/languages`,
        { items },
      ),
    );
  }

  available(
    guildId: string,
  ): Promise<GuildWorkspaceLanguage[]> {
    return firstValueFrom(
      this.http.get<GuildWorkspaceLanguage[]>(
        `/api/v1/discord/guilds/${guildId}/available-languages`,
      ),
    );
  }
}
