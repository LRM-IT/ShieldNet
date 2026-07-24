import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export interface PluginUsageStatusCount { status_code: number; requests: number; }
export interface PluginUsageScopeCount { scope: string; requests: number; }
export interface PluginUsageSummary {
  guild_id: number | string;
  plugin_key: string;
  requests_today: number;
  requests_total: number;
  successful_today: number;
  successful_total: number;
  errors_today: number;
  errors_total: number;
  rate_limited_today: number;
  rate_limited_total: number;
  average_duration_ms_today: number;
  average_duration_ms_total: number;
  last_request_at: string | null;
  status_breakdown_today: PluginUsageStatusCount[];
  scope_breakdown_today: PluginUsageScopeCount[];
  generated_at: string;
}
export interface PluginUsageHistoryPoint {
  day: string;
  requests: number;
  successful: number;
  errors: number;
  rate_limited: number;
  average_duration_ms: number;
}
export interface PluginUsageHistory {
  guild_id: number | string;
  plugin_key: string;
  days: number;
  points: PluginUsageHistoryPoint[];
  generated_at: string;
}

@Injectable({ providedIn: 'root' })
export class PluginUsageService {
  constructor(private readonly http: HttpClient) {}

  summary(guildId: string, pluginKey: string): Promise<PluginUsageSummary> {
    return firstValueFrom(this.http.get<PluginUsageSummary>(
      `/api/v1/discord/guilds/${encodeURIComponent(guildId)}/plugins/${encodeURIComponent(pluginKey)}/usage`,
    ));
  }

  history(guildId: string, pluginKey: string, days: 7 | 30 | 90): Promise<PluginUsageHistory> {
    return firstValueFrom(this.http.get<PluginUsageHistory>(
      `/api/v1/discord/guilds/${encodeURIComponent(guildId)}/plugins/${encodeURIComponent(pluginKey)}/usage/history`,
      { params: { days } },
    ));
  }
}
