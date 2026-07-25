import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface OperationsSnapshot {
  generated_at: string;
  components: Record<string, {
    status: string;
    latency_ms?: number | null;
    queue_depth?: number;
    memory_bytes?: number | null;
    cpu_count?: number;
    load_1m?: number;
    load_5m?: number;
    load_15m?: number;
    load_percent?: number;
    memory_total_bytes?: number;
    memory_used_bytes?: number;
    memory_percent?: number;
    disk_total_bytes?: number;
    disk_used_bytes?: number;
    disk_percent?: number;
  }>;
  workers: Array<{
    worker_name: string;
    worker_type: string;
    status: string;
    reported_status: string;
    metadata: Record<string, unknown>;
    started_at: string;
    last_seen_at: string;
  }>;
  events: Array<{
    id: string;
    guild_id: string | null;
    event_type: string;
    target_type: string | null;
    target_id: string | null;
    result: string;
    message: string | null;
    created_at: string;
  }>;
}

@Injectable({ providedIn: 'root' })
export class OperationsService {
  constructor(private readonly http: HttpClient) {}
  snapshot(): Observable<OperationsSnapshot> {
    return this.http.get<OperationsSnapshot>('/api/v1/platform/operations/snapshot');
  }
}
