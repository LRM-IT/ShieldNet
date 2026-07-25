import { Injectable, inject, signal } from '@angular/core';
import { Subject } from 'rxjs';

import { AuthService } from './auth.service';

export interface ShieldNetEvent<T = unknown> {
  type: string;
  payload: T;
  guild_id?: string | null;
  actor_id?: string | null;
  source?: string;
  correlation_id?: string;
  created_at?: string;
}

export type EventBusState = 'idle' | 'connecting' | 'online' | 'offline';

@Injectable({ providedIn: 'root' })
export class EventBusService {
  private readonly auth = inject(AuthService);
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private manuallyClosed = false;
  private readonly stream = new Subject<ShieldNetEvent>();

  readonly state = signal<EventBusState>('idle');
  readonly lastEvent = signal<ShieldNetEvent | null>(null);
  readonly events$ = this.stream.asObservable();

  connect(): void {
    if (this.socket && (
      this.socket.readyState === WebSocket.OPEN ||
      this.socket.readyState === WebSocket.CONNECTING
    )) return;

    if (!this.auth.accessToken) {
      this.state.set('idle');
      return;
    }

    this.manuallyClosed = false;
    this.open();
  }

  disconnect(): void {
    this.manuallyClosed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.socket?.close(1000, 'client shutdown');
    this.socket = null;
    this.state.set('idle');
  }

  private open(): void {
    const token = this.auth.accessToken;
    if (!token) {
      this.state.set('idle');
      return;
    }

    this.state.set('connecting');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/api/v1/events/ws`;

    try {
      this.socket = new WebSocket(url, ['shieldnet', token]);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.state.set('online');
    };

    this.socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as ShieldNetEvent;
        if (!event?.type) return;
        this.lastEvent.set(event);
        this.stream.next(event);
      } catch {
        // Ignore malformed frames; the connection remains usable.
      }
    };

    this.socket.onerror = () => this.state.set('offline');
    this.socket.onclose = (event) => {
      this.socket = null;
      if (event.code === 1008) {
        this.state.set('offline');
        return;
      }
      if (!this.manuallyClosed) this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    this.state.set('offline');
    if (this.manuallyClosed || this.reconnectTimer) return;
    const delay = Math.min(30_000, 1_000 * (2 ** Math.min(this.reconnectAttempt++, 5)));
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.open();
    }, delay);
  }
}
