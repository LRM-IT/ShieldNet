import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export interface GuildPluginInstallation {
  id: string;
  guild_id: number | string;
  plugin_key: string;
  status: 'installed' | 'enabled' | 'disabled' | 'error';
  enabled: boolean;
  configuration: Record<string, unknown>;
  installed_by_user_id: string | null;
  installed_at: string;
  enabled_at: string | null;
  disabled_at: string | null;
  last_health_check_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

@Injectable({ providedIn: 'root' })
export class GuildPluginService {
  constructor(private readonly http: HttpClient) {}

  listInstalled(guildId: string): Promise<GuildPluginInstallation[]> {
    return firstValueFrom(
      this.http.get<GuildPluginInstallation[]>(
        `/api/v1/discord/guilds/${encodeURIComponent(guildId)}/plugins`,
      ),
    );
  }

  enable(guildId: string, pluginKey: string): Promise<GuildPluginInstallation> {
    return firstValueFrom(
      this.http.post<GuildPluginInstallation>(
        `/api/v1/discord/guilds/${encodeURIComponent(guildId)}/plugins/${encodeURIComponent(pluginKey)}/enable`,
        {},
      ),
    );
  }

  disable(guildId: string, pluginKey: string): Promise<GuildPluginInstallation> {
    return firstValueFrom(
      this.http.post<GuildPluginInstallation>(
        `/api/v1/discord/guilds/${encodeURIComponent(guildId)}/plugins/${encodeURIComponent(pluginKey)}/disable`,
        {},
      ),
    );
  }

  updateSettings(
    guildId: string,
    pluginKey: string,
    configuration: Record<string, unknown>,
  ): Promise<GuildPluginInstallation> {
    return firstValueFrom(
      this.http.patch<GuildPluginInstallation>(
        `/api/v1/discord/guilds/${encodeURIComponent(guildId)}/plugins/${encodeURIComponent(pluginKey)}/settings`,
        { configuration },
      ),
    );
  }
}
