import { CommonModule } from '@angular/common';
import { Component, ElementRef, HostListener, ViewChild, effect, signal } from '@angular/core';
import { ModalService } from '../core/modal.service';
import { ToastService } from '../core/toast.service';

@Component({
  selector: 'sn-modal-host',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (modal.request(); as request) {
      <div class="overlay" (click)="close()">
        <section class="dialog" [class.details]="request.kind === 'details'" role="dialog" aria-modal="true" (click)="$event.stopPropagation()">
          <header>
            <div class="mark">{{ request.danger ? '!' : request.kind === 'prompt' ? '✎' : request.kind === 'details' ? 'i' : '?' }}</div>
            <div>
              <strong>{{ request.title }}</strong>
              @if (request.message) { <p>{{ request.message }}</p> }
            </div>
            @if (request.kind === 'details') {
              <button type="button" class="icon-close" (click)="close()" aria-label="Close">×</button>
            }
          </header>

          @if (request.kind === 'prompt') {
            <input #field
                   [value]="inputValue()"
                   (input)="inputValue.set($any($event.target).value)"
                   (keydown.enter)="submit()"
                   autocomplete="off" />
          }

          @if (request.kind === 'details') {
            <div class="detail-grid">
              @for (row of request.rows; track row.label + row.value) {
                <div class="detail-row" [class.wide]="row.wide">
                  <span>{{ row.label }}</span>
                  <code *ngIf="row.code; else textValue">{{ row.value }}</code>
                  <ng-template #textValue><strong>{{ row.value || '—' }}</strong></ng-template>
                </div>
              }
            </div>

            @if (request.raw) {
              <div class="raw-block">
                <div class="raw-head">
                  <span>JSON</span>
                  <button type="button" class="secondary compact" (click)="copyRaw()">
                    {{ request.copyLabel }}
                  </button>
                </div>
                <pre>{{ request.raw }}</pre>
              </div>
            }
          }

          <footer>
            @if (request.kind === 'details') {
              <button type="button" class="secondary" (click)="close()">{{ request.closeLabel }}</button>
            } @else {
              <button type="button" class="secondary" (click)="close()">{{ request.cancelLabel }}</button>
              <button type="button" class="primary" [class.danger]="request.danger"
                      [disabled]="request.kind === 'prompt' && request.required && !inputValue().trim()"
                      (click)="submit()">
                {{ request.confirmLabel }}
              </button>
            }
          </footer>
        </section>
      </div>
    }
  `,
  styles: [`
    .overlay{position:fixed;inset:0;z-index:250;display:grid;place-items:center;padding:1rem;background:rgba(1,4,8,.76);backdrop-filter:blur(10px)}
    .dialog{width:min(500px,100%);max-height:min(88vh,900px);overflow:auto;padding:1rem;background:linear-gradient(180deg,rgba(18,29,39,.99),rgba(7,11,18,.99));border:1px solid rgba(53,226,178,.22);border-radius:16px;box-shadow:0 30px 90px rgba(0,0,0,.58);animation:dialog-in .18s ease-out}
    .dialog.details{width:min(760px,100%)}
    header{display:grid;grid-template-columns:42px 1fr auto;gap:.8rem;align-items:start}.mark{width:40px;height:40px;display:grid;place-items:center;color:var(--primary);border:1px solid rgba(53,226,178,.22);border-radius:10px;background:rgba(53,226,178,.07);font-weight:900}
    header strong{font-size:.95rem}header p{margin:.35rem 0 0;color:var(--muted);font-size:.73rem;line-height:1.5}
    .icon-close{width:30px;height:30px;color:var(--muted);background:transparent;border:0;border-radius:8px;font-size:1.2rem;cursor:pointer}.icon-close:hover{color:var(--text);background:rgba(255,255,255,.05)}
    input{width:100%;margin-top:1rem;padding:.8rem .9rem;color:var(--text);background:rgba(0,0,0,.22);border:1px solid var(--line);border-radius:10px;outline:none}input:focus{border-color:rgba(53,226,178,.42);box-shadow:0 0 0 3px rgba(53,226,178,.07)}
    .detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem;margin-top:1rem}
    .detail-row{display:grid;gap:.3rem;padding:.75rem;background:rgba(255,255,255,.025);border:1px solid var(--line);border-radius:10px;min-width:0}.detail-row.wide{grid-column:1/-1}
    .detail-row span{color:var(--muted);font-size:.68rem;text-transform:uppercase;letter-spacing:.08em}.detail-row strong,.detail-row code{font-size:.78rem;overflow-wrap:anywhere}.detail-row code{color:#cfd5ff}
    .raw-block{margin-top:.85rem;border:1px solid var(--line);border-radius:10px;overflow:hidden}.raw-head{display:flex;justify-content:space-between;align-items:center;padding:.55rem .7rem;background:rgba(255,255,255,.025);color:var(--muted);font-size:.68rem}.raw-block pre{margin:0;padding:.8rem;max-height:260px;overflow:auto;background:rgba(0,0,0,.22);color:#cfd5ff;font-size:.7rem;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
    footer{display:flex;justify-content:flex-end;gap:.65rem;margin-top:1rem;padding-top:1rem;border-top:1px solid var(--line)}
    button{min-height:38px;padding:0 .9rem;border-radius:9px;cursor:pointer}.compact{min-height:30px;padding:0 .65rem;font-size:.68rem}.secondary{color:var(--text);background:rgba(255,255,255,.035);border:1px solid var(--line)}.primary{color:#03140f;background:var(--primary);border:1px solid var(--primary);font-weight:800}.primary.danger{color:white;background:#c93f55;border-color:#e75a70}button:disabled{opacity:.45;cursor:not-allowed}
    @media(max-width:620px){.detail-grid{grid-template-columns:1fr}.detail-row.wide{grid-column:auto}}
    @keyframes dialog-in{from{opacity:0;transform:translateY(8px) scale(.985)}to{opacity:1;transform:none}}
  `],
})
export class ModalHostComponent {
  @ViewChild('field') field?: ElementRef<HTMLInputElement>;
  readonly inputValue = signal('');

  constructor(
    readonly modal: ModalService,
    private readonly toast: ToastService,
  ) {
    effect(() => {
      const request = this.modal.request();
      this.inputValue.set(request?.value ?? '');
      if (request?.kind === 'prompt') {
        window.setTimeout(() => this.field?.nativeElement.focus(), 0);
      }
    });
  }

  @HostListener('document:keydown.escape')
  escape(): void {
    if (this.modal.request()) this.close();
  }

  close(): void {
    const request = this.modal.request();
    if (!request) return;
    this.modal.close(request.kind === 'confirm' ? false : null);
  }

  submit(): void {
    const request = this.modal.request();
    if (!request) return;

    if (request.kind === 'confirm') {
      this.modal.resolve(true);
      return;
    }

    if (request.kind === 'prompt') {
      const value = this.inputValue();
      if (request.required && !value.trim()) return;
      this.modal.resolve(value);
    }
  }

  async copyRaw(): Promise<void> {
    const request = this.modal.request();
    if (!request?.raw) return;

    try {
      await navigator.clipboard.writeText(request.raw);
      this.toast.success(request.copyLabel, '✓');
    } catch {
      this.toast.error('Copy failed', request.raw);
    }
  }
}
