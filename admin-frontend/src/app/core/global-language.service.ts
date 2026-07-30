import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export interface GlobalLanguage {
  id: number;
  code: string;
  name: string;
  native_name: string;
  flag?: string | null;
  locale?: string | null;
  is_active: boolean;
  sort_order: number;
}

@Injectable({ providedIn: 'root' })
export class GlobalLanguageService {
  constructor(private readonly http: HttpClient) {}

  listActive(): Promise<GlobalLanguage[]> {
    return firstValueFrom(
      this.http.get<GlobalLanguage[]>('/api/v1/languages'),
    );
  }

  listAll(): Promise<GlobalLanguage[]> {
    return firstValueFrom(
      this.http.get<GlobalLanguage[]>('/api/v1/platform/languages'),
    );
  }

  create(payload: Partial<GlobalLanguage>): Promise<GlobalLanguage> {
    return firstValueFrom(
      this.http.post<GlobalLanguage>('/api/v1/platform/languages', payload),
    );
  }

  update(id: number, payload: Partial<GlobalLanguage>): Promise<GlobalLanguage> {
    return firstValueFrom(
      this.http.patch<GlobalLanguage>(
        `/api/v1/platform/languages/${id}`,
        payload,
      ),
    );
  }

  remove(id: number): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`/api/v1/platform/languages/${id}`),
    );
  }
}
