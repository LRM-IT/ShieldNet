import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { timeout } from 'rxjs/operators';

export interface ExplorerData {
  guild: any;
  counts: Record<string, number>;
  roles: any[];
  channels: any[];
  webhooks: any[];
  emojis: any[];
  invites: any[];
}

export interface DiscordStructureRefreshResult {
  success?: boolean;
  message?: string;
  channels?: number;
  roles?: number;
}

@Injectable({ providedIn: 'root' })
export class ExplorerService {
  constructor(private readonly http: HttpClient) {}

  load(id: string): Observable<ExplorerData> {
    return this.http.get<ExplorerData>(
      `/api/v1/discord/guilds/${id}/explorer`,
      { params: { _ts: Date.now().toString() } },
    ).pipe(timeout(15000));
  }

  refreshStructure(id: string): Observable<DiscordStructureRefreshResult> {
    return this.http.post<DiscordStructureRefreshResult>(
      `/api/v1/discord/guilds/${id}/structure/refresh`,
      {},
    );
  }
}
