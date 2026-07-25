import { Injectable, signal } from '@angular/core';

export type ToastKind = 'success' | 'error' | 'warning' | 'info';

export interface ShieldToast {
  id: number;
  kind: ToastKind;
  title: string;
  message?: string;
  timeout: number;
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly items = signal<ShieldToast[]>([]);
  private sequence = 0;

  show(kind: ToastKind, title: string, message = '', timeout = 4500): number {
    const id = ++this.sequence;
    this.items.update(items => [...items, { id, kind, title, message, timeout }]);
    if (timeout > 0) {
      window.setTimeout(() => this.dismiss(id), timeout);
    }
    return id;
  }

  success(title: string, message = '', timeout = 4000): number {
    return this.show('success', title, message, timeout);
  }

  error(title: string, message = '', timeout = 6500): number {
    return this.show('error', title, message, timeout);
  }

  warning(title: string, message = '', timeout = 5500): number {
    return this.show('warning', title, message, timeout);
  }

  info(title: string, message = '', timeout = 4500): number {
    return this.show('info', title, message, timeout);
  }

  dismiss(id: number): void {
    this.items.update(items => items.filter(item => item.id !== id));
  }

  clear(): void {
    this.items.set([]);
  }
}
