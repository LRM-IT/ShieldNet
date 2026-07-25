import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';
import { ShellComponent } from '../shared/shell.component';

interface Provider {
  id: string;
  name: string;
  provider_type: string;
  api_base_url: string | null;
  key_hint: string | null;
  default_model: string | null;
  enabled: boolean;
  priority: number;
  timeout_seconds: number;
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
  imports: [CommonModule, FormsModule, TranslatePipe, ShellComponent],
  template: `
    <sn-shell [title]="'platform_ai.title' | snT:'Platform AI Center'">
      <div class="ai-page">
        <section class="panel hero">
          <div>
            <span class="eyebrow">{{ 'platform_ai.eyebrow' | snT:'AI CONTROL PLANE' }}</span>
            <h2>{{ 'platform_ai.heading' | snT:'Platform AI Center' }}</h2>
            <p>{{ 'platform_ai.description' | snT:'Manage encrypted provider credentials, default models and platform limits.' }}</p>
          </div>
          <button class="btn secondary" type="button" (click)="reload()" [disabled]="loading()">
            {{ loading() ? ('platform_ai.refreshing' | snT:'Refreshing…') : ('platform_ai.refresh' | snT:'Refresh') }}
          </button>
        </section>

        @if (error()) { <div class="notice error">{{ error() }}</div> }
        @if (success()) { <div class="notice success">{{ success() }}</div> }

        <section class="stats">
          <article class="panel stat"><span>{{ 'platform_ai.providers' | snT:'Providers' }}</span><strong>{{ providers().length }}</strong></article>
          <article class="panel stat"><span>{{ 'platform_ai.connected' | snT:'Connected' }}</span><strong>{{ connectedCount() }}</strong></article>
          <article class="panel stat"><span>{{ 'platform_ai.enabled' | snT:'Enabled' }}</span><strong>{{ enabledCount() }}</strong></article>
          <article class="panel stat runtime" [class.stopped]="settings.emergency_stop">
            <span>{{ 'platform_ai.runtime' | snT:'AI runtime' }}</span>
            <strong>{{ settings.emergency_stop ? ('platform_ai.stopped' | snT:'STOPPED') : ('platform_ai.ready' | snT:'READY') }}</strong>
          </article>
        </section>

        <section class="main-grid">
          <form class="panel add-card" (ngSubmit)="createProvider()">
            <div class="section-head">
              <span class="eyebrow">{{ 'platform_ai.new_provider' | snT:'NEW PROVIDER' }}</span>
              <h3>{{ 'platform_ai.add_provider' | snT:'Add provider' }}</h3>
              <p>{{ 'platform_ai.key_encrypted' | snT:'The API key is encrypted before storage.' }}</p>
            </div>

            <label><span>{{ 'platform_ai.name' | snT:'Name' }}</span><input [(ngModel)]="form.name" name="name" required [placeholder]="'platform_ai.name_placeholder' | snT:'Production OpenAI'" /></label>
            <label><span>{{ 'platform_ai.provider' | snT:'Provider' }}</span>
              <select [(ngModel)]="form.provider_type" name="provider_type">
                <option value="openai">OpenAI</option><option value="gemini">Google Gemini</option>
                <option value="google_translate">Google Translate</option><option value="groq">Groq</option>
                <option value="anthropic">Anthropic</option><option value="xai">xAI</option>
                <option value="deepl">DeepL</option><option value="libretranslate">LibreTranslate</option>
                <option value="openai_compatible">OpenAI-compatible</option>
              </select>
            </label>
            <label><span>{{ 'platform_ai.api_key' | snT:'API key' }}</span><input [(ngModel)]="form.api_key" name="api_key" type="password" required autocomplete="new-password" placeholder="••••••••••••" /></label>
            <label><span>{{ 'platform_ai.api_url' | snT:'API base URL' }}</span><input [(ngModel)]="form.api_base_url" name="api_base_url" [placeholder]="'platform_ai.optional' | snT:'Optional'" /></label>
            <label><span>{{ 'platform_ai.default_model' | snT:'Default model' }}</span><input [(ngModel)]="form.default_model" name="default_model" placeholder="gpt-5-mini" /></label>
            <div class="two">
              <label><span>{{ 'platform_ai.organization' | snT:'Organization' }}</span><input [(ngModel)]="form.organization_id" name="organization_id" /></label>
              <label><span>{{ 'platform_ai.project' | snT:'Project' }}</span><input [(ngModel)]="form.project_id" name="project_id" /></label>
            </div>
            <button class="btn primary full" [disabled]="saving()">{{ saving() ? ('platform_ai.saving' | snT:'Saving…') : ('platform_ai.save_provider' | snT:'Save provider') }}</button>
          </form>

          <section class="providers-col">
            <div class="list-title"><div><span class="eyebrow">{{ 'platform_ai.configured' | snT:'CONFIGURED' }}</span><h3>{{ 'platform_ai.provider_connections' | snT:'Provider connections' }}</h3></div><span class="count">{{ providers().length }}</span></div>
            @for (provider of providers(); track provider.id) {
              <article class="panel provider-card" [class.disabled]="!provider.enabled">
                <header>
                  <div class="provider-name"><span class="logo">{{ providerInitial(provider) }}</span><div><h3>{{ provider.name }}</h3><p>{{ provider.provider_type }} · {{ provider.key_hint || ('platform_ai.encrypted_key' | snT:'Encrypted key') }}</p></div></div>
                  <label class="toggle"><input type="checkbox" [(ngModel)]="provider.enabled" (change)="saveProvider(provider)" /><i></i><b>{{ provider.enabled ? ('platform_ai.enabled' | snT:'Enabled') : ('platform_ai.disabled' | snT:'Disabled') }}</b></label>
                </header>
                <div class="two provider-fields">
                  <label><span>{{ 'platform_ai.default_model' | snT:'Default model' }}</span><input [(ngModel)]="provider.default_model" /></label>
                  <label><span>{{ 'platform_ai.api_url' | snT:'API base URL' }}</span><input [(ngModel)]="provider.api_base_url" /></label>
                </div>
                <div class="meta">
                  <span class="health"><i [class.ok]="provider.last_health_status === 'connected'" [class.bad]="provider.last_health_status === 'error'"></i>{{ healthLabel(provider) }} @if (provider.last_health_latency_ms !== null) { · {{ provider.last_health_latency_ms }} ms }</span>
                  <span>{{ 'platform_ai.priority' | snT:'Priority' }}: {{ provider.priority }} · {{ 'platform_ai.timeout' | snT:'Timeout' }}: {{ provider.timeout_seconds }}s</span>
                </div>
                @if (provider.last_error) { <div class="provider-error">{{ provider.last_error }}</div> }
                <footer><button class="btn primary" type="button" (click)="saveProvider(provider)">{{ 'platform_ai.save' | snT:'Save' }}</button><button class="btn secondary" type="button" (click)="testProvider(provider)">{{ 'platform_ai.test_connection' | snT:'Test connection' }}</button><button class="btn danger" type="button" (click)="deleteProvider(provider)">{{ 'platform_ai.delete' | snT:'Delete' }}</button></footer>
              </article>
            } @empty {
              <article class="panel empty"><strong>AI</strong><h3>{{ 'platform_ai.no_providers' | snT:'No global AI providers configured' }}</h3><p>{{ 'platform_ai.no_providers_help' | snT:'Add the first provider using the form on this page.' }}</p></article>
            }
          </section>
        </section>

        <section class="panel settings-card">
          <div class="section-head"><span class="eyebrow">{{ 'platform_ai.routing' | snT:'ROUTING' }}</span><h3>{{ 'platform_ai.default_models' | snT:'Default models' }}</h3><p>{{ 'platform_ai.default_models_help' | snT:'Used when a Discord server has no local model override.' }}</p></div>
          <div class="models">
            <label><span>{{ 'platform_ai.translation' | snT:'Translation' }}</span><input [(ngModel)]="settings.defaults['translation']" /></label>
            <label><span>{{ 'platform_ai.moderation' | snT:'Moderation' }}</span><input [(ngModel)]="settings.defaults['moderation']" /></label>
            <label><span>{{ 'platform_ai.verification' | snT:'Verification' }}</span><input [(ngModel)]="settings.defaults['verification']" /></label>
            <label><span>{{ 'platform_ai.ocr' | snT:'OCR' }}</span><input [(ngModel)]="settings.defaults['ocr']" /></label>
            <label><span>{{ 'platform_ai.summaries' | snT:'Summaries' }}</span><input [(ngModel)]="settings.defaults['summaries']" /></label>
          </div>
          <div class="divider"></div>
          <div class="section-head"><span class="eyebrow">{{ 'platform_ai.protection' | snT:'PROTECTION' }}</span><h3>{{ 'platform_ai.limits' | snT:'Platform limits' }}</h3><p>{{ 'platform_ai.limits_help' | snT:'Protect the platform against unexpected or excessive AI usage.' }}</p></div>
          <div class="limits">
            <label><span>{{ 'platform_ai.requests_minute' | snT:'Requests / minute' }}</span><input type="number" min="0" [(ngModel)]="settings.limits['requests_per_minute']" /></label>
            <label><span>{{ 'platform_ai.requests_day' | snT:'Requests / day' }}</span><input type="number" min="0" [(ngModel)]="settings.limits['requests_per_day']" /></label>
            <label><span>{{ 'platform_ai.monthly_budget' | snT:'Monthly budget' }}</span><input type="number" min="0" step="0.01" [(ngModel)]="settings.limits['monthly_budget']" /></label>
          </div>
          <label class="emergency"><input type="checkbox" [(ngModel)]="settings.emergency_stop" /><i></i><span><strong>{{ 'platform_ai.emergency_stop' | snT:'Emergency stop' }}</strong><small>{{ 'platform_ai.emergency_help' | snT:'Immediately block every AI request handled by the platform runtime.' }}</small></span></label>
          <div class="save-row"><button class="btn primary" type="button" (click)="saveSettings()">{{ 'platform_ai.save_settings' | snT:'Save platform AI settings' }}</button></div>
        </section>
      </div>
    </sn-shell>
  `,
  styles: [`
    :host{display:block;min-width:0}*{box-sizing:border-box}.ai-page{display:grid;gap:1rem;width:100%;min-width:0}.panel{min-width:0;background:linear-gradient(145deg,var(--panel-glow),transparent 34%),var(--surface-1);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}
    .hero{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:1.2rem;overflow:hidden}.hero h2,.section-head h3,.list-title h3{margin:.28rem 0 0}.hero p,.section-head p{margin:.35rem 0 0;color:var(--muted);font-size:.72rem;line-height:1.45}.eyebrow{color:var(--primary);font-size:.56rem;font-weight:900;letter-spacing:.16em}.btn{min-height:40px;display:inline-flex;align-items:center;justify-content:center;padding:.65rem .9rem;border-radius:10px;border:1px solid var(--line);font-size:.68rem;font-weight:850;cursor:pointer;white-space:nowrap}.btn.primary{background:var(--primary);border-color:var(--primary);color:#041611}.btn.secondary{background:var(--surface-2);color:var(--text)}.btn.danger{background:rgba(255,92,114,.08);border-color:rgba(255,92,114,.25);color:#ff9aa8}.btn.full{width:100%}.notice{padding:.8rem 1rem;border-radius:12px;border:1px solid;font-size:.7rem;overflow-wrap:anywhere}.notice.error{color:#ff9aa8;background:rgba(255,92,114,.08);border-color:rgba(255,92,114,.25)}.notice.success{color:var(--success);background:rgba(53,226,178,.08);border-color:rgba(53,226,178,.24)}
    .stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem}.stat{display:flex;justify-content:space-between;align-items:center;gap:.7rem;padding:.95rem 1rem;overflow:hidden}.stat span{color:var(--muted);font-size:.63rem;overflow-wrap:anywhere}.stat strong{font-size:1.2rem}.stat.runtime strong{font-size:.72rem;color:var(--success)}.stat.runtime.stopped strong{color:#ff9aa8}.main-grid{display:grid;grid-template-columns:minmax(280px,360px) minmax(0,1fr);gap:1rem;align-items:start;min-width:0}.add-card{display:grid;gap:.72rem;padding:1rem;position:sticky;top:92px}.section-head{min-width:0}.add-card label,.two label,.models label,.limits label{display:grid;gap:.35rem;min-width:0;color:var(--muted);font-size:.62rem;font-weight:750}.two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.72rem;min-width:0}input,select{display:block;width:100%;min-width:0;height:42px;padding:.65rem .7rem;color:var(--text);background:var(--surface-2);border:1px solid var(--line);border-radius:10px;outline:none;font:inherit;font-size:.7rem}input:focus,select:focus{border-color:var(--primary);box-shadow:0 0 0 3px var(--primary-soft)}
    .providers-col{display:grid;gap:.75rem;min-width:0}.list-title{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:.1rem}.count{display:grid;place-items:center;min-width:30px;height:30px;padding:0 .45rem;border-radius:999px;color:var(--primary);background:var(--primary-soft);border:1px solid var(--line-strong);font-size:.65rem;font-weight:900}.provider-card{display:grid;gap:1rem;padding:1rem;overflow:hidden}.provider-card.disabled{opacity:.62}.provider-card header{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;min-width:0}.provider-name{display:flex;align-items:center;gap:.72rem;min-width:0}.logo{flex:0 0 42px;height:42px;display:grid;place-items:center;border-radius:12px;color:var(--primary);background:var(--primary-soft);border:1px solid var(--line-strong);font-weight:900}.provider-name>div{min-width:0}.provider-name h3{margin:0;font-size:.86rem;overflow-wrap:anywhere}.provider-name p{margin:.28rem 0 0;color:var(--muted);font-size:.59rem;overflow-wrap:anywhere}.toggle{display:flex;align-items:center;gap:.45rem;cursor:pointer}.toggle input{position:absolute;opacity:0;width:1px;height:1px}.toggle i{position:relative;width:38px;height:22px;border-radius:99px;background:var(--surface-3);border:1px solid var(--line)}.toggle i:after{content:"";position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:var(--muted);transition:.18s}.toggle input:checked+i{background:var(--primary-soft);border-color:var(--primary)}.toggle input:checked+i:after{left:19px;background:var(--primary)}.toggle b{font-size:.59rem;color:var(--muted)}.provider-fields{grid-template-columns:repeat(2,minmax(0,1fr))}.meta{display:flex;justify-content:space-between;gap:.7rem;flex-wrap:wrap;padding:.7rem .75rem;background:var(--surface-2);border:1px solid var(--line);border-radius:10px;color:var(--muted);font-size:.57rem}.health{display:flex;align-items:center;gap:.35rem}.health i{width:8px;height:8px;border-radius:50%;background:#76818a}.health i.ok{background:var(--success)}.health i.bad{background:#ff6f7f}.provider-error{padding:.7rem .75rem;color:#ff9aa8;background:rgba(255,92,114,.07);border:1px solid rgba(255,92,114,.2);border-radius:10px;font-size:.62rem;line-height:1.45;overflow-wrap:anywhere;max-height:140px;overflow:auto}.provider-card footer{display:flex;gap:.5rem;flex-wrap:wrap}.provider-card footer .danger{margin-left:auto}.empty{display:grid;place-items:center;text-align:center;padding:2.2rem 1rem}.empty>strong{display:grid;place-items:center;width:52px;height:52px;border-radius:15px;color:var(--primary);background:var(--primary-soft);border:1px solid var(--line-strong)}.empty h3{margin:.75rem 0 0}.empty p{margin:.35rem 0 0;color:var(--muted);font-size:.67rem}
    .settings-card{padding:1rem}.models{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.72rem;margin-top:.9rem}.limits{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.72rem;margin-top:.9rem}.divider{height:1px;margin:1.1rem 0;background:var(--line)}.emergency{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:.7rem;margin-top:1rem;padding:.8rem;border:1px solid rgba(255,92,114,.26);border-radius:12px;background:rgba(255,92,114,.055);cursor:pointer}.emergency input{position:absolute;opacity:0;width:1px;height:1px}.emergency>i{position:relative;width:40px;height:22px;border-radius:99px;background:var(--surface-3);border:1px solid var(--line)}.emergency>i:after{content:"";position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:var(--muted);transition:.18s}.emergency input:checked+i{background:rgba(255,92,114,.16);border-color:#ff6f7f}.emergency input:checked+i:after{left:21px;background:#ff6f7f}.emergency span{display:grid;gap:.2rem}.emergency strong{color:#ff9aa8;font-size:.7rem}.emergency small{color:var(--muted);font-size:.6rem;line-height:1.4}.save-row{display:flex;justify-content:flex-end;margin-top:1rem}
    @media(max-width:1180px){.models{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:980px){.main-grid{grid-template-columns:1fr}.add-card{position:static}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.models{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.hero,.provider-card header{display:grid;align-items:stretch}.hero .btn{width:100%}.two,.provider-fields,.models,.limits{grid-template-columns:1fr}.provider-card footer{display:grid;grid-template-columns:1fr 1fr}.provider-card footer .btn{width:100%}.provider-card footer .danger{grid-column:1/-1;margin-left:0}.save-row .btn{width:100%}}@media(max-width:480px){.stats{grid-template-columns:1fr}.provider-card footer{grid-template-columns:1fr}.provider-card footer .danger{grid-column:auto}.meta{display:grid}}
  `],
})
export class PlatformAIComponent implements OnInit {
  readonly providers = signal<Provider[]>([]);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly enabledCount = computed(() => this.providers().filter((x) => x.enabled).length);
  readonly connectedCount = computed(() => this.providers().filter((x) => x.last_health_status === 'connected').length);

  form: any = this.emptyForm();
  settings: PlatformAISettings = { defaults: {}, limits: {}, emergency_stop: false };

  constructor(private readonly http: HttpClient, private readonly i18n: TranslationService) {}
  ngOnInit(): void { void this.reload(); }
  providerInitial(provider: Provider): string { return (provider.name || provider.provider_type || 'AI').slice(0, 2).toUpperCase(); }
  healthLabel(provider: Provider): string { return provider.last_health_status === 'connected' ? 'Connected' : provider.last_health_status === 'error' ? 'Connection error' : 'Not tested'; }

  async reload(): Promise<void> {
    this.loading.set(true); this.error.set('');
    try {
      const [providers, settings] = await Promise.all([
        firstValueFrom(this.http.get<Provider[]>('/api/v1/platform/ai/providers')),
        firstValueFrom(this.http.get<PlatformAISettings>('/api/v1/platform/ai/settings')),
      ]);
      this.providers.set(providers);
      this.settings = { defaults: settings.defaults || {}, limits: settings.limits || {}, emergency_stop: !!settings.emergency_stop };
    } catch (e: any) { this.error.set(e?.error?.detail || 'Unable to load Platform AI Center.'); }
    finally { this.loading.set(false); }
  }

  async createProvider(): Promise<void> {
    this.saving.set(true); this.error.set(''); this.success.set('');
    try {
      await firstValueFrom(this.http.post('/api/v1/platform/ai/providers', { ...this.form, api_base_url: this.form.api_base_url || null, default_model: this.form.default_model || null, organization_id: this.form.organization_id || null, project_id: this.form.project_id || null }));
      this.form = this.emptyForm(); this.success.set(this.i18n.t('platform_ai.provider_saved', 'Provider saved.')); await this.reload();
    } catch (e: any) { this.error.set(e?.error?.detail || 'Unable to save provider.'); }
    finally { this.saving.set(false); }
  }

  async saveProvider(provider: Provider): Promise<void> {
    this.error.set(''); this.success.set('');
    try { await firstValueFrom(this.http.patch(`/api/v1/platform/ai/providers/${provider.id}`, { enabled: provider.enabled, api_base_url: provider.api_base_url || null, default_model: provider.default_model || null })); this.success.set(this.i18n.t('platform_ai.provider_updated', 'Provider updated.')); await this.reload(); }
    catch (e: any) { this.error.set(e?.error?.detail || 'Unable to update provider.'); }
  }

  async testProvider(provider: Provider): Promise<void> {
    this.error.set(''); this.success.set('');
    try { await firstValueFrom(this.http.post(`/api/v1/platform/ai/providers/${provider.id}/test`, {})); this.success.set(this.i18n.t('platform_ai.test_completed', 'Connection test completed.')); await this.reload(); }
    catch (e: any) { this.error.set(e?.error?.detail || 'Provider connection test failed.'); }
  }

  async deleteProvider(provider: Provider): Promise<void> {
    if (!confirm(`Delete provider ${provider.name}?`)) return;
    try { await firstValueFrom(this.http.delete(`/api/v1/platform/ai/providers/${provider.id}`)); this.success.set(this.i18n.t('platform_ai.provider_deleted', 'Provider deleted.')); await this.reload(); }
    catch (e: any) { this.error.set(e?.error?.detail || 'Unable to delete provider.'); }
  }

  async saveSettings(): Promise<void> {
    this.error.set(''); this.success.set('');
    try { await firstValueFrom(this.http.put('/api/v1/platform/ai/settings', this.settings)); this.success.set(this.i18n.t('platform_ai.settings_saved', 'Platform AI settings saved.')); await this.reload(); }
    catch (e: any) { this.error.set(e?.error?.detail || 'Unable to save platform AI settings.'); }
  }

  private emptyForm() { return { name: '', provider_type: 'openai', api_key: '', api_base_url: '', default_model: '', organization_id: '', project_id: '' }; }
}
