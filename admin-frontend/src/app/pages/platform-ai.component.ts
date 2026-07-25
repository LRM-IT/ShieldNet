import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';

interface Provider {
  id: string;
  name: string;
  provider_type: string;
  api_base_url: string | null;
  key_hint: string | null;
  organization_id: string | null;
  project_id: string | null;
  default_model: string | null;
  enabled: boolean;
  priority: number;
  timeout_seconds: number;
  max_retries: number;
  last_health_status: string | null;
  last_health_latency_ms: number | null;
  last_error: string | null;
}

interface PlatformAISettings {
  defaults: Record<string, string | null>;
  limits: Record<string, number | null>;
  emergency_stop: boolean;
}

@Component({
  selector: 'sn-platform-ai',
  standalone: true,
  imports: [CommonModule, FormsModule, ShellComponent],
  template: `
    <sn-shell title="Platform AI Center">
      <section class="hero">
        <div>
          <span>AI CONTROL PLANE</span>
          <h2>Platform AI Center</h2>
          <p>Encrypted provider credentials, default models and platform limits.</p>
        </div>
        <button (click)="reload()" [disabled]="loading()">Refresh</button>
      </section>

      @if (error()) { <div class="message error">{{ error() }}</div> }
      @if (success()) { <div class="message success">{{ success() }}</div> }

      <section class="stats">
        <article><strong>{{ providers().length }}</strong><span>Providers</span></article>
        <article><strong>{{ connectedCount() }}</strong><span>Connected</span></article>
        <article><strong>{{ enabledCount() }}</strong><span>Enabled</span></article>
        <article [class.stop]="settings.emergency_stop">
          <strong>{{ settings.emergency_stop ? 'STOP' : 'READY' }}</strong><span>AI runtime</span>
        </article>
      </section>

      <section class="layout">
        <form class="panel" (ngSubmit)="createProvider()">
          <header><h3>Add provider</h3><p>The API key is encrypted before storage.</p></header>

          <label>Name<input [(ngModel)]="form.name" name="name" required placeholder="Production OpenAI" /></label>
          <label>Provider
            <select [(ngModel)]="form.provider_type" name="provider_type">
              <option value="openai">OpenAI</option>
              <option value="gemini">Google Gemini</option>
              <option value="google_translate">Google Translate</option>
              <option value="groq">Groq</option>
              <option value="anthropic">Anthropic</option>
              <option value="xai">xAI</option>
              <option value="deepl">DeepL</option>
              <option value="libretranslate">LibreTranslate</option>
              <option value="openai_compatible">OpenAI-compatible</option>
            </select>
          </label>
          <label>API key<input [(ngModel)]="form.api_key" name="api_key" type="password" required autocomplete="new-password" /></label>
          <label>API base URL<input [(ngModel)]="form.api_base_url" name="api_base_url" placeholder="Optional" /></label>
          <label>Default model<input [(ngModel)]="form.default_model" name="default_model" placeholder="gpt-5-mini" /></label>
          <div class="two">
            <label>Organization<input [(ngModel)]="form.organization_id" name="organization_id" /></label>
            <label>Project<input [(ngModel)]="form.project_id" name="project_id" /></label>
          </div>
          <button class="primary" [disabled]="saving()">{{ saving() ? 'Saving…' : 'Save provider' }}</button>
        </form>

        <section class="providers">
          @for (provider of providers(); track provider.id) {
            <article class="panel provider" [class.disabled]="!provider.enabled">
              <header>
                <div>
                  <h3>{{ provider.name }}</h3>
                  <p>{{ provider.provider_type }} · {{ provider.key_hint || 'Encrypted key' }}</p>
                </div>
                <label class="switch">
                  <input type="checkbox" [(ngModel)]="provider.enabled" (change)="saveProvider(provider)" />
                  <span>{{ provider.enabled ? 'Enabled' : 'Disabled' }}</span>
                </label>
              </header>

              <div class="provider-grid">
                <label>Default model<input [(ngModel)]="provider.default_model" /></label>
                <label>API base URL<input [(ngModel)]="provider.api_base_url" /></label>
              </div>

              <div class="health">
                <span [class.connected]="provider.last_health_status === 'connected'"></span>
                {{ provider.last_health_status || 'Not tested' }}
                @if (provider.last_health_latency_ms) { · {{ provider.last_health_latency_ms }} ms }
              </div>

              @if (provider.last_error) { <div class="provider-error">{{ provider.last_error }}</div> }

              <footer>
                <button (click)="saveProvider(provider)">Save</button>
                <button (click)="testProvider(provider)">Test connection</button>
                <button class="danger" (click)="deleteProvider(provider)">Delete</button>
              </footer>
            </article>
          } @empty {
            <article class="panel empty">No global AI providers configured.</article>
          }
        </section>
      </section>

      <section class="panel settings">
        <header><h3>Default models</h3><p>Used when a Discord server has no local override.</p></header>
        <div class="settings-grid">
          <label>Translation<input [(ngModel)]="settings.defaults['translation']" /></label>
          <label>Moderation<input [(ngModel)]="settings.defaults['moderation']" /></label>
          <label>Verification<input [(ngModel)]="settings.defaults['verification']" /></label>
          <label>OCR<input [(ngModel)]="settings.defaults['ocr']" /></label>
          <label>Summaries<input [(ngModel)]="settings.defaults['summaries']" /></label>
        </div>

        <header class="secondary-head"><h3>Limits</h3><p>Platform-wide protection against runaway usage.</p></header>
        <div class="settings-grid">
          <label>Requests/minute<input type="number" [(ngModel)]="settings.limits['requests_per_minute']" /></label>
          <label>Requests/day<input type="number" [(ngModel)]="settings.limits['requests_per_day']" /></label>
          <label>Monthly budget<input type="number" step="0.01" [(ngModel)]="settings.limits['monthly_budget']" /></label>
        </div>

        <label class="emergency">
          <input type="checkbox" [(ngModel)]="settings.emergency_stop" />
          <span><strong>Emergency stop</strong><small>Disable all platform AI requests immediately.</small></span>
        </label>

        <button class="primary" (click)="saveSettings()">Save platform AI settings</button>
      </section>
    </sn-shell>
  `,
  styles: [`
    .hero,.panel,.message,.stats article{border:1px solid var(--line);border-radius:16px;background:rgba(16,22,38,.72)}
    .hero{display:flex;justify-content:space-between;align-items:center;padding:1.2rem;margin-bottom:1rem}.hero span{color:var(--primary);font-size:.7rem;letter-spacing:.15em}.hero h2{margin:.25rem 0}.hero p,.panel header p{margin:.2rem 0 0;color:var(--muted)}
    button,input,select{border:1px solid var(--line);border-radius:9px;background:rgba(6,10,16,.9);color:var(--text);padding:.65rem}button{cursor:pointer}.primary{background:var(--primary);color:#04130f;font-weight:800}
    .message{padding:.8rem;margin-bottom:1rem}.error{color:#ff9bad}.success{color:var(--primary)}
    .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1rem}.stats article{padding:1rem;display:grid;gap:.2rem}.stats strong{font-size:1.35rem}.stats span{color:var(--muted);font-size:.78rem}.stats .stop{border-color:#9e3a4d;color:#ff9bad}
    .layout{display:grid;grid-template-columns:360px 1fr;gap:1rem;align-items:start}.panel{padding:1rem}.panel header{display:flex;justify-content:space-between;gap:1rem;margin-bottom:1rem}.panel h3{margin:0}.layout form{display:grid;gap:.75rem}.layout label,.settings label{display:grid;gap:.35rem;color:var(--muted);font-size:.8rem}.two,.provider-grid,.settings-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.75rem}
    .providers{display:grid;gap:.75rem}.provider.disabled{opacity:.65}.provider header p{font-size:.75rem}.switch{display:flex!important;align-items:center;grid-template-columns:auto 1fr!important}.health{margin:.8rem 0;color:var(--muted)}.health span{display:inline-block;width:.55rem;height:.55rem;border-radius:50%;background:#75808a;margin-right:.4rem}.health span.connected{background:var(--primary);box-shadow:0 0 10px rgba(53,226,178,.6)}.provider-error{color:#ff9bad;font-size:.8rem;margin-bottom:.7rem}.provider footer{display:flex;gap:.5rem;flex-wrap:wrap}.danger{color:#ff9bad}
    .settings{margin-top:1rem}.secondary-head{margin-top:1.4rem!important}.settings-grid{grid-template-columns:repeat(3,1fr)}.emergency{display:flex!important;grid-template-columns:auto 1fr!important;align-items:center;margin:1rem 0;padding:.8rem;border:1px solid #9e3a4d;border-radius:10px}.emergency span{display:grid}.emergency small{color:var(--muted)}.empty{text-align:center;color:var(--muted)}
    @media(max-width:1000px){.layout{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}}@media(max-width:650px){.stats,.settings-grid,.two,.provider-grid{grid-template-columns:1fr}.hero{align-items:flex-start;flex-direction:column;gap:.8rem}}
  `],
})
export class PlatformAIComponent implements OnInit {
  readonly providers = signal<Provider[]>([]);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly success = signal('');

  form: any = {
    name: '',
    provider_type: 'openai',
    api_key: '',
    api_base_url: '',
    default_model: '',
    organization_id: '',
    project_id: '',
  };

  settings: PlatformAISettings = {
    defaults: {},
    limits: {},
    emergency_stop: false,
  };

  constructor(private readonly http: HttpClient) {}

  ngOnInit(): void { void this.reload(); }

  enabledCount(): number { return this.providers().filter(x => x.enabled).length; }
  connectedCount(): number { return this.providers().filter(x => x.last_health_status === 'connected').length; }

  async reload(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const [providers, settings] = await Promise.all([
        firstValueFrom(this.http.get<Provider[]>('/api/v1/platform/ai/providers')),
        firstValueFrom(this.http.get<PlatformAISettings>('/api/v1/platform/ai/settings')),
      ]);
      this.providers.set(providers);
      this.settings = {
        defaults: settings.defaults || {},
        limits: settings.limits || {},
        emergency_stop: !!settings.emergency_stop,
      };
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to load Platform AI Center.');
    } finally {
      this.loading.set(false);
    }
  }

  async createProvider(): Promise<void> {
    this.saving.set(true); this.error.set(''); this.success.set('');
    try {
      await firstValueFrom(this.http.post('/api/v1/platform/ai/providers', {
        ...this.form,
        api_base_url: this.form.api_base_url || null,
        default_model: this.form.default_model || null,
        organization_id: this.form.organization_id || null,
        project_id: this.form.project_id || null,
      }));
      this.form = { name:'', provider_type:'openai', api_key:'', api_base_url:'', default_model:'', organization_id:'', project_id:'' };
      this.success.set('Provider saved.');
      await this.reload();
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to save provider.');
    } finally {
      this.saving.set(false);
    }
  }

  async saveProvider(provider: Provider): Promise<void> {
    this.error.set(''); this.success.set('');
    try {
      await firstValueFrom(this.http.patch(`/api/v1/platform/ai/providers/${provider.id}`, {
        enabled: provider.enabled,
        api_base_url: provider.api_base_url,
        default_model: provider.default_model,
      }));
      this.success.set(`${provider.name} updated.`);
      await this.reload();
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to update provider.');
    }
  }

  async testProvider(provider: Provider): Promise<void> {
    this.error.set(''); this.success.set('');
    try {
      await firstValueFrom(this.http.post(`/api/v1/platform/ai/providers/${provider.id}/test`, {}));
      this.success.set(`${provider.name} connection test completed.`);
      await this.reload();
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Provider connection test failed.');
    }
  }

  async deleteProvider(provider: Provider): Promise<void> {
    if (!confirm(`Delete provider ${provider.name}?`)) return;
    try {
      await firstValueFrom(this.http.delete(`/api/v1/platform/ai/providers/${provider.id}`));
      await this.reload();
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to delete provider.');
    }
  }

  async saveSettings(): Promise<void> {
    this.error.set(''); this.success.set('');
    try {
      await firstValueFrom(this.http.put('/api/v1/platform/ai/settings', this.settings));
      this.success.set('Platform AI settings saved.');
      await this.reload();
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to save platform AI settings.');
    }
  }
}
