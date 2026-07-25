import { Injectable, signal } from '@angular/core';

export type ModalKind = 'confirm' | 'prompt' | 'details';

export interface ModalDetailRow {
  label: string;
  value: string;
  code?: boolean;
  wide?: boolean;
}

export interface ModalRequest {
  kind: ModalKind;
  title: string;
  message: string;
  value: string;
  confirmLabel: string;
  cancelLabel: string;
  danger: boolean;
  required: boolean;
  rows: ModalDetailRow[];
  raw: string;
  copyLabel: string;
  closeLabel: string;
}

@Injectable({ providedIn: 'root' })
export class ModalService {
  readonly request = signal<ModalRequest | null>(null);

  private confirmResolver: ((value: boolean) => void) | null = null;
  private promptResolver: ((value: string | null) => void) | null = null;

  confirm(
    message: string,
    options: Partial<Omit<ModalRequest, 'kind' | 'message' | 'value' | 'required' | 'rows' | 'raw' | 'copyLabel' | 'closeLabel'>> = {},
  ): Promise<boolean> {
    this.close(false);
    return new Promise<boolean>(resolve => {
      this.confirmResolver = resolve;
      this.request.set({
        kind: 'confirm',
        title: options.title ?? 'Confirm action',
        message,
        value: '',
        confirmLabel: options.confirmLabel ?? 'Confirm',
        cancelLabel: options.cancelLabel ?? 'Cancel',
        danger: options.danger ?? false,
        required: false,
        rows: [],
        raw: '',
        copyLabel: 'Copy',
        closeLabel: 'Close',
      });
    });
  }

  prompt(
    message: string,
    value = '',
    options: Partial<Omit<ModalRequest, 'kind' | 'message' | 'value' | 'rows' | 'raw' | 'copyLabel' | 'closeLabel'>> = {},
  ): Promise<string | null> {
    this.close(null);
    return new Promise<string | null>(resolve => {
      this.promptResolver = resolve;
      this.request.set({
        kind: 'prompt',
        title: options.title ?? 'Enter value',
        message,
        value,
        confirmLabel: options.confirmLabel ?? 'Save',
        cancelLabel: options.cancelLabel ?? 'Cancel',
        danger: options.danger ?? false,
        required: options.required ?? false,
        rows: [],
        raw: '',
        copyLabel: 'Copy',
        closeLabel: 'Close',
      });
    });
  }

  details(
    title: string,
    rows: ModalDetailRow[],
    options: {
      message?: string;
      raw?: string;
      copyLabel?: string;
      closeLabel?: string;
      danger?: boolean;
    } = {},
  ): void {
    this.close(null);
    this.request.set({
      kind: 'details',
      title,
      message: options.message ?? '',
      value: '',
      confirmLabel: '',
      cancelLabel: '',
      danger: options.danger ?? false,
      required: false,
      rows,
      raw: options.raw ?? '',
      copyLabel: options.copyLabel ?? 'Copy',
      closeLabel: options.closeLabel ?? 'Close',
    });
  }

  resolve(value: boolean | string): void {
    const request = this.request();
    this.request.set(null);

    if (request?.kind === 'confirm') {
      const resolver = this.confirmResolver;
      this.confirmResolver = null;
      resolver?.(Boolean(value));
      return;
    }

    if (request?.kind === 'prompt') {
      const resolver = this.promptResolver;
      this.promptResolver = null;
      resolver?.(String(value));
    }
  }

  close(value: boolean | null = null): void {
    const request = this.request();
    this.request.set(null);

    if (request?.kind === 'confirm') {
      const resolver = this.confirmResolver;
      this.confirmResolver = null;
      resolver?.(Boolean(value));
      return;
    }

    if (request?.kind === 'prompt') {
      const resolver = this.promptResolver;
      this.promptResolver = null;
      resolver?.(null);
    }
  }
}
