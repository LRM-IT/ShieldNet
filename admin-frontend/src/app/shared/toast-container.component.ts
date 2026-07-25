import { Component } from '@angular/core';
import { ToastService } from '../core/toast.service';

@Component({
  selector: 'sn-toast-container',
  standalone: true,
  template: `
    <section class="toast-stack" aria-live="polite" aria-atomic="false">
      @for (toast of toasts.items(); track toast.id) {
        <article class="toast" [class]="toast.kind">
          <span class="icon">{{ icon(toast.kind) }}</span>
          <div>
            <strong>{{ toast.title }}</strong>
            @if (toast.message) { <p>{{ toast.message }}</p> }
          </div>
          <button type="button" (click)="toasts.dismiss(toast.id)" aria-label="Close">×</button>
        </article>
      }
    </section>
  `,
  styles: [`
    .toast-stack{position:fixed;right:1rem;bottom:1rem;z-index:300;display:grid;gap:.7rem;width:min(390px,calc(100vw - 2rem));pointer-events:none}
    .toast{pointer-events:auto;display:grid;grid-template-columns:34px 1fr auto;gap:.75rem;align-items:start;padding:.9rem 1rem;background:rgba(8,14,22,.97);border:1px solid var(--line);border-left:3px solid #7793a4;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.46);animation:toast-in .2s ease-out}
    .toast.success{border-left-color:var(--success)}.toast.error{border-left-color:#ff6175}.toast.warning{border-left-color:#ffc35c}.toast.info{border-left-color:#67b7ff}
    .icon{width:32px;height:32px;display:grid;place-items:center;border:1px solid var(--line);border-radius:9px;color:var(--primary);background:rgba(255,255,255,.035)}
    strong{display:block;font-size:.78rem}p{margin:.25rem 0 0;color:var(--muted);font-size:.69rem;line-height:1.45}
    button{width:28px;height:28px;color:var(--muted);background:transparent;border:0;border-radius:7px;font-size:1.15rem;cursor:pointer}button:hover{color:var(--text);background:rgba(255,255,255,.05)}
    @keyframes toast-in{from{opacity:0;transform:translateY(10px) scale(.98)}to{opacity:1;transform:none}}
  `],
})
export class ToastContainerComponent {
  constructor(readonly toasts: ToastService) {}
  icon(kind: string): string {
    return kind === 'success' ? '✓' : kind === 'error' ? '!' : kind === 'warning' ? '△' : 'i';
  }
}
