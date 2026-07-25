import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export interface PluginRuntimeInstance {
  id: string;
  guild_id: number | string;
  plugin_key: string;
  state: string;
  generation: number;
  package_version: string | null;
  package_path: string | null;
  manifest_json: Record<string, unknown>;
  started_at: string | null;
  stopped_at: string | null;
  last_heartbeat_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

@Injectable({ providedIn: 'root' })
export class PluginRuntimeService {
  constructor(private readonly http: HttpClient) {}

  list(guildId: string): Promise<PluginRuntimeInstance[]> {
    return firstValueFrom(this.http.get<PluginRuntimeInstance[]>(
      `/api/v1/discord/guilds/${encodeURIComponent(guildId)}/plugin-runtime`,
    ));
  }

  start(guildId: string, pluginKey: string): Promise<PluginRuntimeInstance> {
    return firstValueFrom(this.http.post<PluginRuntimeInstance>(
      `/api/v1/discord/guilds/${encodeURIComponent(guildId)}/plugin-runtime/${encodeURIComponent(pluginKey)}/start`, {},
    ));
  }

  stop(guildId: string, pluginKey: string): Promise<PluginRuntimeInstance> {
    return firstValueFrom(this.http.post<PluginRuntimeInstance>(
      `/api/v1/discord/guilds/${encodeURIComponent(guildId)}/plugin-runtime/${encodeURIComponent(pluginKey)}/stop`, {},
    ));
  }
}
