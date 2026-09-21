import { Component, OnInit, signal } from '@angular/core';
import { ShellComponent } from '../shared/shell.component';
import { MaintenanceService, PlatformMode } from '../core/maintenance.service';

@Component({
  standalone: true,
  imports: [ShellComponent],
  template: `
    <sn-shell title="Maintenance">
      <main class="page">
        <header>
          <span>SUPERADMIN · SYSTEM STATE</span>
          <h2>Maintenance</h2>
          <p>Control the operating state displayed across the GuildConsole website.</p>
        </header>

        @if (error()) { <div class="notice error">{{error()}}</div> }
        @if (success()) { <div class="notice success">{{success()}}</div> }

        <section class="modes">
          <button type="button" [class.active]="selected()==='normal'" (click)="selected.set('normal')">
            <i class="normal"></i><strong>Normal operation</strong>
            <small>No system banner is displayed.</small>
          </button>
          <button type="button" [class.active]="selected()==='maintenance'" (click)="selected.set('maintenance')">
            <i class="maintenance"></i><strong>Maintenance mode</strong>
            <small>Shows a red technical maintenance notice.</small>
          </button>
          <button type="button" [class.active]="selected()==='testing'" (click)="selected.set('testing')">
            <i class="testing"></i><strong>Testing mode</strong>
            <small>Shows that the system is operating in test mode.</small>
          </button>
        </section>

        <section class="preview" [class.maintenance]="selected()==='maintenance'" [class.testing]="selected()==='testing'">
          <small>GLOBAL BANNER PREVIEW</small>
          <strong>{{bannerText()}}</strong>
        </section>

        <div class="actions">
          <span>Current mode: <b>{{maintenance.mode().toUpperCase()}}</b></span>
          <button type="button" (click)="save()" [disabled]="saving() || selected()===maintenance.mode()">
            {{saving() ? 'Saving…' : 'Apply system mode'}}
          </button>
        </div>
      </main>
    </sn-shell>
  `,
  styles: [`
    .page{max-width:1100px;margin:auto;display:grid;gap:1rem}.page>header span{color:var(--primary);font-size:.68rem;font-weight:900;letter-spacing:.14em}h2,p{margin:.3rem 0}p{color:var(--muted)}
    .modes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.8rem}.modes button{min-height:150px;display:grid;align-content:center;justify-items:start;gap:.55rem;padding:1.2rem;text-align:left;color:var(--text);background:var(--panel);border:1px solid var(--line);border-radius:16px}.modes button:hover,.modes button.active{border-color:var(--primary);background:var(--primary-soft)}.modes i{width:12px;height:12px;border-radius:50%}.modes i.normal{background:var(--success);box-shadow:0 0 14px var(--success)}.modes i.maintenance{background:var(--danger);box-shadow:0 0 14px var(--danger)}.modes i.testing{background:var(--warning);box-shadow:0 0 14px var(--warning)}.modes strong{font-size:1rem}.modes small{color:var(--muted);line-height:1.5}
    .preview{min-height:64px;display:grid;place-items:center;gap:.15rem;padding:.8rem;border:1px solid var(--line);border-radius:12px;background:var(--panel);text-align:center}.preview small{color:var(--muted);font-size:.58rem;letter-spacing:.12em}.preview.maintenance{color:#fff;background:#a7192f;border-color:#ff6074}.preview.testing{color:#1b1300;background:#f5b942;border-color:#ffd778}.preview:not(.maintenance):not(.testing) strong{color:var(--muted)}
    .actions{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem;border:1px solid var(--line);border-radius:14px;background:var(--panel)}.actions span{color:var(--muted);font-size:.75rem}.actions b{color:var(--text)}.actions button{padding:.8rem 1rem;border-radius:9px;background:var(--primary);color:#03130e;font-weight:850}.actions button:disabled{opacity:.45;cursor:not-allowed}.notice{padding:.9rem;border:1px solid var(--line);border-radius:11px;background:var(--panel)}.error{color:var(--danger)}.success{color:var(--success)}
    @media(max-width:760px){.modes{grid-template-columns:1fr}.modes button{min-height:110px}.actions{align-items:stretch;flex-direction:column}.actions button{width:100%}}
  `],
})
export class MaintenanceComponent implements OnInit {
  readonly selected = signal<PlatformMode>('normal');
  readonly saving = signal(false);
  readonly error = signal('');
  readonly success = signal('');

  constructor(readonly maintenance: MaintenanceService) {}

  async ngOnInit(): Promise<void> { this.selected.set(await this.maintenance.load()); }

  bannerText(): string {
    if (this.selected() === 'maintenance') return 'TECHNICAL MAINTENANCE IS IN PROGRESS';
    if (this.selected() === 'testing') return 'THE SYSTEM IS OPERATING IN TEST MODE';
    return 'No banner — the system is operating normally';
  }

  async save(): Promise<void> {
    this.error.set(''); this.success.set(''); this.saving.set(true);
    try {
      await this.maintenance.save(this.selected());
      this.success.set('System mode updated. The banner is now active across the website.');
    } catch (error: any) {
      this.error.set(error?.error?.detail || 'Unable to update the system mode.');
    } finally { this.saving.set(false); }
  }
}
