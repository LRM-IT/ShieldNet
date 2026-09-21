import { HttpClient } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export type PlatformMode = 'normal' | 'maintenance' | 'testing';

@Injectable({ providedIn: 'root' })
export class MaintenanceService {
  readonly mode = signal<PlatformMode>('normal');

  constructor(private readonly http: HttpClient) {}

  async load(): Promise<PlatformMode> {
    try {
      const response = await firstValueFrom(
        this.http.get<{ mode: PlatformMode }>('/api/v1/public/maintenance'),
      );
      this.mode.set(response.mode);
    } catch {
      this.mode.set('normal');
    }
    return this.mode();
  }

  async save(mode: PlatformMode): Promise<PlatformMode> {
    const response = await firstValueFrom(
      this.http.put<{ mode: PlatformMode }>('/api/v1/platform/maintenance', { mode }),
    );
    this.mode.set(response.mode);
    return response.mode;
  }
}
