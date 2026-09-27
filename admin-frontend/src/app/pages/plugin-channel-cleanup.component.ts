import { DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { GuildPluginService } from '../core/guild-plugin.service';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';
import { DiscordChannelPickerComponent } from '../shared/discord-channel-picker.component';
import { ShellComponent } from '../shared/shell.component';

@Component({
  standalone: true,
  imports: [FormsModule, DatePipe, TranslatePipe, ShellComponent, DiscordChannelPickerComponent],
  template: `
    <sn-shell [title]="'channel_cleanup.title'|snT:'Channel Cleanup'"><main class="page">
      <header><span>{{'channel_cleanup.eyebrow'|snT:'GUILD PLUGIN'}}</span><h2>{{'channel_cleanup.title'|snT:'Channel Cleanup'}}</h2><p>{{'channel_cleanup.intro'|snT:'Automatically remove old messages from selected text channels, threads and every post in selected forums.'}}</p></header>
      @if (error()) { <div class="notice error">{{ error() }}</div> }
      @if (success()) { <div class="notice success">{{ success() }}</div> }

      @if (!settings.installed) {
        <section class="card install"><div><h3>{{'channel_cleanup.install_title'|snT:'Install Channel Cleanup'}}</h3><p>{{'channel_cleanup.install_help'|snT:'Add the plugin before configuring retention rules.'}}</p></div><button (click)="install()">{{'channel_cleanup.install'|snT:'Install plugin'}}</button></section>
      } @else {
        <section class="card status">
          <div><h3>{{ (settings.enabled ? 'channel_cleanup.enabled' : 'channel_cleanup.disabled') | snT:(settings.enabled ? 'Plugin enabled' : 'Plugin disabled') }}</h3><p>{{'channel_cleanup.state_help'|snT:'Cleanup only runs while this plugin is enabled.'}}</p></div>
          <button [class.secondary]="settings.enabled" (click)="toggle()">{{ (settings.enabled ? 'channel_cleanup.disable' : 'channel_cleanup.enable') | snT:(settings.enabled ? 'Disable plugin' : 'Enable plugin') }}</button>
        </section>

        <section class="notice warning"><strong>{{'channel_cleanup.warning_title'|snT:'Messages are deleted permanently.'}}</strong>{{'channel_cleanup.warning_text'|snT:'Discord does not provide a way to restore them. Verify every channel and retention period before enabling a rule.'}}</section>

        <section class="card schedule">
          <div><h3>{{'channel_cleanup.schedule'|snT:'Schedule'}}</h3><p>{{'channel_cleanup.schedule_help'|snT:'The bot checks all enabled rules at this interval.'}}</p></div>
          <label><span>{{'channel_cleanup.interval'|snT:'Run every, hours'}}</span><input type="number" min="1" max="168" [(ngModel)]="settings.interval_hours"></label>
        </section>

        <section class="card heading"><div><h3>{{'channel_cleanup.rules'|snT:'Cleanup rules'}}</h3><p>{{'channel_cleanup.rules_help'|snT:'Selecting a forum applies the rule to all active and archived posts in that forum.'}}</p></div><button (click)="add()">{{'channel_cleanup.add_rule'|snT:'Add rule'}}</button></section>
        @for (target of settings.targets; track target.id; let i = $index) {
          <article class="card rule">
            <div class="grid">
              <label class="field"><span>{{'channel_cleanup.destination'|snT:'Channel, thread or forum'}}</span><sn-discord-channel-picker [guildId]="guildId" [value]="target.channel_id" [showHint]="false" (valueChange)="target.channel_id=$event"/><small>{{'channel_cleanup.destination_help'|snT:'Forums include every post; a thread only cleans that thread.'}}</small></label>
              <label class="field"><span>{{'channel_cleanup.retention'|snT:'Delete messages older than, days'}}</span><input type="number" min="1" max="3650" [(ngModel)]="target.retention_days"><small>{{'channel_cleanup.retention_help'|snT:'Age is calculated from the message creation time.'}}</small></label>
            </div>
            <div class="options">
              <label><input type="checkbox" [(ngModel)]="target.enabled"><span><strong>{{'channel_cleanup.rule_enabled'|snT:'Rule enabled'}}</strong><small>{{'channel_cleanup.rule_enabled_help'|snT:'Include this destination in scheduled cleanup.'}}</small></span></label>
              <label><input type="checkbox" [(ngModel)]="target.keep_pinned"><span><strong>{{'channel_cleanup.keep_pinned'|snT:'Keep pinned messages'}}</strong><small>{{'channel_cleanup.keep_pinned_help'|snT:'Pinned messages remain even when they are older.'}}</small></span></label>
            </div>
            <footer><button class="danger" (click)="settings.targets.splice(i,1)">{{'channel_cleanup.remove_rule'|snT:'Remove rule'}}</button></footer>
          </article>
        } @empty { <section class="card empty">{{'channel_cleanup.no_rules'|snT:'No cleanup rules yet.'}}</section> }

        <section class="card results">
          <div><h3>{{'channel_cleanup.last_run'|snT:'Last cleanup'}}</h3>
            @if (settings.last_result) { <p>{{ settings.last_result.finished_at | date:'medium' }} · {{ settings.last_result.deleted_messages }} {{'channel_cleanup.deleted'|snT:'messages deleted'}} · {{ settings.last_result.scanned_channels }} {{'channel_cleanup.scanned'|snT:'destinations scanned'}}</p> }
            @else { <p>{{'channel_cleanup.never_run'|snT:'No cleanup has run yet.'}}</p> }
            @if (settings.last_result?.errors?.length) { <ul>@for (item of settings.last_result.errors; track item) { <li>{{ item }}</li> }</ul> }
          </div>
          <div class="actions"><button class="secondary" (click)="runNow()" [disabled]="!settings.enabled || settings.run_pending">{{ (settings.run_pending ? 'channel_cleanup.queued' : 'channel_cleanup.run_now') | snT:(settings.run_pending ? 'Cleanup queued' : 'Run now') }}</button><button (click)="save()">{{'channel_cleanup.save'|snT:'Save settings'}}</button></div>
        </section>
      }
    </main></sn-shell>
  `,
  styles: [`
    .page{max-width:1120px;margin:auto;display:grid;gap:1rem;padding-bottom:3rem}header>span{color:var(--primary);font-size:.7rem;font-weight:800;letter-spacing:.12em}h2{margin:.3rem 0;font-size:1.9rem}h3,p{margin:.2rem 0}p,small{color:var(--muted)}
    .card,.notice{padding:1.2rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}.install,.status,.heading,.schedule,.results{display:flex;justify-content:space-between;align-items:center;gap:1rem}.warning{border-color:#8c6727;color:#ffd687}.warning strong{display:block;margin-bottom:.3rem}.error{color:#ff9ea3}.success{color:#76e8b8}
    button{min-height:44px;padding:.7rem 1rem;border:0;border-radius:9px;background:var(--primary);color:#07120f;font-weight:800;cursor:pointer}button:disabled{cursor:not-allowed;opacity:.5}.secondary,.danger{background:transparent;color:var(--text);border:1px solid var(--line)}.danger{color:#ff9ea3}
    .schedule label{display:grid;gap:.35rem;color:var(--muted);font-size:.78rem}.schedule input{width:150px}.grid{display:grid;grid-template-columns:2fr 1fr;gap:1rem}.field{display:grid;grid-template-rows:auto 52px auto;gap:.4rem;color:var(--muted);font-size:.78rem}.field sn-discord-channel-picker{height:52px}input[type=number]{box-sizing:border-box;min-height:52px;padding:.7rem .8rem;border:1px solid var(--line);border-radius:9px;background:var(--panel-2);color:var(--text);font:inherit}
    .rule{display:grid;gap:1rem}.options{display:flex;flex-wrap:wrap;gap:.7rem}.options label{min-width:240px;display:flex;gap:.7rem;align-items:center;padding:.7rem;border:1px solid var(--line);border-radius:9px;background:var(--panel-2);cursor:pointer}.options input{width:18px;height:18px;accent-color:var(--primary)}.options span{display:grid;gap:.15rem}.options small{font-size:.68rem}.rule footer{display:flex;justify-content:flex-end}.empty{text-align:center;color:var(--muted)}.actions{display:flex;gap:.7rem;flex-shrink:0}ul{margin:.7rem 0 0;color:#ffb1b6}
    @media(max-width:760px){.install,.status,.heading,.schedule,.results{align-items:stretch;flex-direction:column}.grid{grid-template-columns:1fr}.schedule input,.actions,.actions button,.heading button,.status button,.install button{width:100%}.actions{display:grid}.options label{min-width:0;width:100%}}
  `],
})
export class PluginChannelCleanupComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly plugins = inject(GuildPluginService);
  private readonly i18n = inject(TranslationService);
  readonly guildId = this.route.snapshot.paramMap.get('guildId') || '';
  settings: any = { installed: false, enabled: false, interval_hours: 24, targets: [] };
  readonly error = signal('');
  readonly success = signal('');
  private get url() { return `/api/v1/discord/guilds/${this.guildId}/plugins/channel-cleanup`; }

  async ngOnInit() { await this.load(); }
  private t(key: string, fallback: string) { return this.i18n.t(`channel_cleanup.${key}`, fallback); }
  async load() { try { this.settings = await firstValueFrom(this.http.get<any>(`${this.url}/settings`)); } catch (e: any) { this.error.set(e?.error?.detail || this.t('load_error', 'Could not load cleanup settings.')); } }
  add() { this.settings.targets.push({ id: `cleanup-${Date.now().toString(36)}`, channel_id: null, retention_days: 30, keep_pinned: true, enabled: true }); }
  async install() { try { await this.plugins.install(this.guildId, 'channel_cleanup'); await this.load(); } catch (e: any) { this.error.set(e?.error?.detail || this.t('install_error', 'Install failed.')); } }
  async toggle() { try { this.settings.enabled ? await this.plugins.disable(this.guildId, 'channel_cleanup') : await this.plugins.enable(this.guildId, 'channel_cleanup'); await this.load(); } catch (e: any) { this.error.set(e?.error?.detail || this.t('state_error', 'State change failed.')); } }
  async save() { this.error.set(''); this.success.set(''); try { this.settings = await firstValueFrom(this.http.put<any>(`${this.url}/settings`, { interval_hours: Number(this.settings.interval_hours), targets: this.settings.targets.map((x: any) => ({ ...x, retention_days: Number(x.retention_days) })) })); this.success.set(this.t('saved', 'Cleanup settings saved.')); } catch (e: any) { this.error.set(e?.error?.detail || this.t('save_error', 'Save failed.')); } }
  async runNow() { await this.save(); if (this.error()) return; try { await firstValueFrom(this.http.post(`${this.url}/run`, {})); this.settings.run_pending = true; this.success.set(this.t('queued_notice', 'Cleanup was queued and will start within one minute.')); } catch (e: any) { this.error.set(e?.error?.detail || this.t('queue_error', 'Could not queue cleanup.')); } }
}
