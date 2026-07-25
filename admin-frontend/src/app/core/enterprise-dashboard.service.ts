import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export interface EnterpriseDashboardOverview {
  generated_at: string;
  overall_status: 'healthy' | 'degraded' | 'critical';
  scope: 'global' | 'assigned';
  components: {
    backend: { status: string };
    postgresql: { status: string; latency_ms: number };
    valkey: { status: string; latency_ms: number | null; memory_bytes: number | null; queue_depth: number };
  };
  metrics: Record<string, number>;
  workers: Array<{ name: string; type: string; status: string; reported_status: string; last_seen_at: string; metadata: Record<string, unknown> }>;
  guilds: Array<{ guild_id: string; name: string; icon_url: string | null; member_count: number; status: string; bot_status: string; last_sync_at: string | null; sync_status: 'fresh' | 'stale' | 'never'; enabled_plugins: number }>;
}

@Injectable({ providedIn: 'root' })
export class EnterpriseDashboardService {
  constructor(private readonly http: HttpClient) {}

  overview(): Promise<EnterpriseDashboardOverview> {
    return firstValueFrom(this.http.get<EnterpriseDashboardOverview>('/api/v1/platform/dashboard/overview'));
  }
}
