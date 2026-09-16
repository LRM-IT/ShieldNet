import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class VerificationService {
  constructor(private readonly http: HttpClient) {}

  getSettings(guildId: string): Promise<any> {
    return firstValueFrom(
      this.http.get(
        `/api/v1/discord/guilds/${guildId}/verification/settings`,
      ),
    );
  }

  saveSettings(
    guildId: string,
    payload: any,
  ): Promise<any> {
    return firstValueFrom(
      this.http.put(
        `/api/v1/discord/guilds/${guildId}/verification/settings`,
        payload,
      ),
    );
  }

  levels(guildId:string):Promise<any[]> { return firstValueFrom(this.http.get<any[]>(`/api/v1/discord/guilds/${guildId}/verification/levels`)); }
  createLevel(guildId:string,payload:any):Promise<any> { return firstValueFrom(this.http.post(`/api/v1/discord/guilds/${guildId}/verification/levels`,payload)); }
  updateLevel(guildId:string,id:string,payload:any):Promise<any> { return firstValueFrom(this.http.put(`/api/v1/discord/guilds/${guildId}/verification/levels/${id}`,payload)); }
  deleteLevel(guildId:string,id:string):Promise<any> { return firstValueFrom(this.http.delete(`/api/v1/discord/guilds/${guildId}/verification/levels/${id}`)); }
  uploadLevelTemplate(guildId:string,id:string,file:File,marker:any):Promise<any> { const form=new FormData(); form.append('file',file); form.append('marker_json',JSON.stringify(marker)); return firstValueFrom(this.http.post(`/api/v1/discord/guilds/${guildId}/verification/levels/${id}/template`,form)); }

  listRequests(
    guildId: string,
    status?: string,
  ): Promise<any> {
    const suffix = status
      ? `?status=${encodeURIComponent(status)}`
      : '';

    return firstValueFrom(
      this.http.get(
        `/api/v1/discord/guilds/${guildId}/verification/requests${suffix}`,
      ),
    );
  }

  approve(
    guildId: string,
    requestId: string,
    reason: string | null,
  ): Promise<any> {
    return firstValueFrom(
      this.http.post(
        `/api/v1/discord/guilds/${guildId}/verification/requests/${requestId}/approve`,
        { reason },
      ),
    );
  }

  reject(
    guildId: string,
    requestId: string,
    reason: string,
  ): Promise<any> {
    return firstValueFrom(
      this.http.post(
        `/api/v1/discord/guilds/${guildId}/verification/requests/${requestId}/reject`,
        { reason },
      ),
    );
  }
  retry(
    guildId: string,
    requestId: string,
  ): Promise<any> {
    return firstValueFrom(
      this.http.post(
        `/api/v1/discord/guilds/${guildId}/verification/requests/${requestId}/retry`,
        {},
      ),
    );
  }

  summary(guildId: string): Promise<any> {
    return firstValueFrom(this.http.get(`/api/v1/discord/guilds/${guildId}/verification/summary`));
  }

  cancel(guildId: string, requestId: string): Promise<any> {
    return firstValueFrom(this.http.post(`/api/v1/discord/guilds/${guildId}/verification/requests/${requestId}/cancel`, {}));
  }

  requeue(guildId: string, requestId: string): Promise<any> {
    return firstValueFrom(this.http.post(`/api/v1/discord/guilds/${guildId}/verification/requests/${requestId}/requeue`, {}));
  }

  resendReview(guildId: string, requestId: string): Promise<any> {
    return firstValueFrom(this.http.post(`/api/v1/discord/guilds/${guildId}/verification/requests/${requestId}/resend-review`, {}));
  }

  bulkCancel(
    guildId: string,
    requestIds: string[],
  ): Promise<any> {
    return firstValueFrom(
      this.http.post(
        `/api/v1/discord/guilds/${guildId}/verification/bulk/cancel`,
        { request_ids: requestIds },
      ),
    );
  }

  bulkRequeue(
    guildId: string,
    requestIds: string[],
  ): Promise<any> {
    return firstValueFrom(
      this.http.post(
        `/api/v1/discord/guilds/${guildId}/verification/bulk/requeue`,
        { request_ids: requestIds },
      ),
    );
  }

  recoverStale(
    guildId: string,
    olderThanMinutes: number,
  ): Promise<any> {
    return firstValueFrom(
      this.http.post(
        `/api/v1/discord/guilds/${guildId}/verification/recover-stale`,
        { older_than_minutes: olderThanMinutes },
      ),
    );
  }

  requestChanges(guildId: string, requestId: string, reason: string): Promise<any> {
    return firstValueFrom(this.http.post(`/api/v1/discord/guilds/${guildId}/verification/requests/${requestId}/request-changes`, { reason }));
  }

  history(guildId: string, requestId: string): Promise<any> {
    return firstValueFrom(this.http.get(`/api/v1/discord/guilds/${guildId}/verification/requests/${requestId}/history`));
  }

  exportUrl(
    guildId: string,
    status?: string,
  ): string {
    const suffix = status
      ? `?status=${encodeURIComponent(status)}`
      : '';

    return `/api/v1/discord/guilds/${guildId}/verification/export.csv${suffix}`;
  }

}
