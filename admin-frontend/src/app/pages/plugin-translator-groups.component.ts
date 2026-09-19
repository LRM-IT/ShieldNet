import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';
import { GuildPluginService } from '../core/guild-plugin.service';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

interface Language { code: string; name: string; }
interface Channel { id: string; name: string; type: string; }
interface Binding { channel_id: string; language: string; }
interface Group { name: string; enabled: boolean; channels: Binding[]; expanded?: boolean; }
interface Settings { installed:boolean;enabled:boolean;groups:Group[];include_source_link:boolean;languages:Language[];cache_enabled:boolean;cache_ttl_hours:number;cache_max_entries:number;cache_min_characters:number;max_source_characters:number;fallback_to_original:boolean;forward_attachments:boolean;forward_stickers:boolean;protected_terms:string[];detect_source_language:boolean;detection_min_characters:number; }
interface CacheStats { entries:number;hits:number;misses:number; }

@Component({
  standalone: true,
  imports: [FormsModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'translator_groups.title'|snT:'Translator Groups'"><main class="page">
      <header><span>{{'translator_groups.eyebrow'|snT:'GUILD PLUGIN'}}</span><h2>{{'translator_groups.title'|snT:'Translator Groups'}}</h2>
        <p>{{'translator_groups.description'|snT:'Messages in one language channel are translated into the other channels of its group through AI Center.'}}</p></header>
      @if (error()) { <div class="panel error">{{ error() }}</div> }
      @if (success()) { <div class="panel success">{{ success() }}</div> }
      @if (!settings.installed) {
        <section class="panel"><p>{{'translator_groups.install_hint'|snT:'Install this plugin to configure translation groups.'}}</p>
          <button (click)="install()" [disabled]="busy()">{{'translator_groups.install'|snT:'Install plugin'}}</button></section>
      } @else {
        <section class="panel"><div class="heading"><div><h3>{{'translator_groups.setup'|snT:'Translation setup'}}</h3>
          <p>{{'translator_groups.setup_help'|snT:'Configure the translation route and provider in AI Center. Server Languages controls the available language codes.'}}</p></div>
          </div>
          <div class="checks-grid"><label class="check"><input type="checkbox" [(ngModel)]="settings.include_source_link"> {{'translator_groups.source_link'|snT:'Include link to source message'}}</label><label class="check"><input type="checkbox" [(ngModel)]="settings.forward_attachments"> {{'translator_groups.attachments'|snT:'Forward attachments'}}</label><label class="check"><input type="checkbox" [(ngModel)]="settings.forward_stickers"> {{'translator_groups.stickers'|snT:'Forward stickers'}}</label><label class="check"><input type="checkbox" [(ngModel)]="settings.fallback_to_original"> {{'translator_groups.fallback'|snT:'Send original text if AI fails'}}</label><label class="check"><input type="checkbox" [(ngModel)]="settings.detect_source_language"> {{'translator_groups.detect_language'|snT:'Detect the actual message language'}}</label></div>
          <div class="detail-grid"><label>{{'translator_groups.max_length'|snT:'Maximum source text length'}}<input type="number" min="100" max="12000" step="100" [(ngModel)]="settings.max_source_characters"><small>{{'translator_groups.max_length_help'|snT:'Longer messages are truncated before being sent to AI.'}}</small></label><label>{{'translator_groups.detection_length'|snT:'Minimum characters for detection'}}<input type="number" min="3" max="500" [(ngModel)]="settings.detection_min_characters" [disabled]="!settings.detect_source_language"><small>{{'translator_groups.detection_help'|snT:'Short messages use the language assigned to the source channel.'}}</small></label></div>
        </section>
        <section class="panel"><h3>{{'translator_groups.protected_title'|snT:'Words and phrases that must not be translated'}}</h3><p>{{'translator_groups.protected_help'|snT:'Add brand names, game terms, commands, role names or usernames. Enter one term per line; matching is case-insensitive and the original spelling is preserved.'}}</p><label>{{'translator_groups.protected_terms'|snT:'Protected terms'}}<textarea rows="7" [(ngModel)]="protectedTermsText" placeholder="GuildConsole&#10;/verify&#10;R5&#10;ShieldNet"></textarea><small>{{'translator_groups.protected_limit'|snT:'Up to 100 entries, 80 characters each.'}}</small></label></section>
        <section class="panel cache-panel"><div class="heading"><div><h3>{{'translator_groups.cache_title'|snT:'Translation cache'}}</h3><p>{{'translator_groups.cache_help'|snT:'Reuse translations of identical text and avoid repeated AI token charges.'}}</p></div><label class="check switch"><input type="checkbox" [(ngModel)]="settings.cache_enabled"> {{'translator_groups.cache_enabled'|snT:'Cache enabled'}}</label></div>
          <div class="cache-stats"><div><strong>{{cacheStats().entries}}</strong><span>{{'translator_groups.cached'|snT:'Cached translations'}}</span></div><div><strong>{{cacheStats().hits}}</strong><span>{{'translator_groups.saved_requests'|snT:'AI requests saved'}}</span></div><div><strong>{{cacheStats().misses}}</strong><span>{{'translator_groups.cache_misses'|snT:'Cache misses'}}</span></div><div><strong>{{hitRate()}}%</strong><span>{{'translator_groups.hit_rate'|snT:'Hit rate'}}</span></div></div>
          <div class="detail-grid" [class.disabled]="!settings.cache_enabled"><label>{{'translator_groups.retention'|snT:'Retention, hours'}}<input type="number" min="1" max="720" [(ngModel)]="settings.cache_ttl_hours"><small>{{'translator_groups.retention_help'|snT:'Expired translations are generated again.'}}</small></label><label>{{'translator_groups.max_entries'|snT:'Maximum entries'}}<input type="number" min="100" max="50000" step="100" [(ngModel)]="settings.cache_max_entries"><small>{{'translator_groups.max_entries_help'|snT:'Oldest entries are removed first.'}}</small></label><label>{{'translator_groups.min_length'|snT:'Minimum text length'}}<input type="number" min="1" max="500" [(ngModel)]="settings.cache_min_characters"><small>{{'translator_groups.min_length_help'|snT:'Shorter messages bypass the cache.'}}</small></label></div>
          <div class="cache-actions"><span>{{'translator_groups.cache_scope'|snT:'Cache keys are isolated per Discord server and target language.'}}</span><button class="secondary danger" (click)="clearCache()" [disabled]="busy()||!cacheStats().entries">{{'translator_groups.clear_cache'|snT:'Clear cache'}}</button></div>
        </section>
        <section class="panel"><div class="heading"><div><h3>{{'translator_groups.groups'|snT:'Groups'}}</h3><p>{{'translator_groups.groups_help'|snT:'Each group links two or more text channels.'}}</p></div>
          <button (click)="addGroup()" [disabled]="busy()">{{'translator_groups.add_group'|snT:'Add group'}}</button></div>
          @for (group of settings.groups; track $index; let gi = $index) {
            <article class="group">
              <button class="group-summary" type="button" (click)="group.expanded=!group.expanded" [attr.aria-expanded]="group.expanded">
                <span><strong>{{ group.name || ('translator_groups.new_group'|snT:'New group') }}</strong><small>{{ group.channels.length }} {{'translator_groups.channels'|snT:'channels'}} · {{ group.enabled ? ('translator_groups.enabled'|snT:'Enabled') : ('translator_groups.disabled'|snT:'Disabled') }}</small></span>
                <span class="chevron" [class.open]="group.expanded">⌄</span>
              </button>
              @if (group.expanded) {
                <div class="group-body">
                  <div class="heading"><label>{{'translator_groups.group_name'|snT:'Group name'}}<input [(ngModel)]="group.name" maxlength="60"></label>
                    <div class="actions"><label class="check"><input type="checkbox" [(ngModel)]="group.enabled"> {{'translator_groups.enabled'|snT:'Enabled'}}</label>
                      <button class="secondary" (click)="settings.groups.splice(gi, 1)">{{'translator_groups.delete_group'|snT:'Delete group'}}</button></div></div>
                  @for (binding of group.channels; track $index; let bi = $index) {
                    <div class="binding"><label>{{'translator_groups.channel'|snT:'Channel'}}<select [(ngModel)]="binding.channel_id">
                        <option value="">{{'translator_groups.select_channel'|snT:'Select channel'}}</option>
                        @for (channel of channels(); track channel.id) { <option [value]="channel.id">#{{ channel.name }}</option> }
                      </select></label>
                      <label>{{'translator_groups.language'|snT:'Language'}}<select [(ngModel)]="binding.language"><option value="">{{'translator_groups.select_language'|snT:'Select language'}}</option>
                        @for (language of settings.languages; track language.code) { <option [value]="language.code">{{ language.name }} ({{ language.code }})</option> }
                      </select></label>
                      <button class="secondary remove" (click)="group.channels.splice(bi, 1)">{{'translator_groups.remove'|snT:'Remove'}}</button></div>
                  }
                  <button class="secondary" (click)="group.channels.push({channel_id: '', language: ''})">{{'translator_groups.add_channel'|snT:'Add channel'}}</button>
                </div>
              }
            </article>
          } @empty { <p>{{'translator_groups.empty_groups'|snT:'No translation groups yet.'}}</p> }
        </section>
        <section class="panel"><h3>{{'translator_groups.commands'|snT:'Basic Discord commands'}}</h3><p>{{'translator_groups.commands_help'|snT:'Administrators can use /group_add, /group_language in a channel, and /group_unlanguage. All other settings stay here.'}}</p>
          <p>{{'translator_groups.requirements'|snT:'The bot needs Message Content access and permission to manage webhooks in target channels. Translation does not run until this plugin and the AI Center translation route are enabled.'}}</p></section>
        <button class="save" (click)="save()" [disabled]="busy()">{{'translator_groups.save'|snT:'Save settings'}}</button>
      }
    </main></sn-shell>
  `,
  styles: [`
    .page{max-width:1050px;margin:auto;display:grid;gap:1rem;padding-bottom:3rem}
    header span{color:var(--primary);font-size:.7rem;font-weight:800;letter-spacing:.12em}
    h2{margin:.3rem 0;font-size:1.8rem}h3{margin:0 0 .6rem}p{color:var(--muted);margin:.3rem 0 1rem}
    .panel,.group{padding:1.25rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}
    .group{margin-top:1rem;padding:0;overflow:hidden;background:var(--surface-1)}.group-summary{width:100%;padding:1.1rem 1.25rem;display:flex;align-items:center;justify-content:space-between;text-align:left;border:0;border-radius:0;background:transparent;color:var(--text)}.group-summary span:first-child{display:grid;gap:.25rem}.group-summary strong{font-size:1.05rem}.group-summary small{color:var(--muted);font-weight:500}.chevron{font-size:1.5rem;line-height:1;transition:transform .18s ease}.chevron.open{transform:rotate(180deg)}.group-body{padding:0 1.25rem 1.25rem;border-top:1px solid var(--line)}.heading,.actions{display:flex;justify-content:space-between;align-items:start;gap:1rem}
    .binding{display:grid;grid-template-columns:1fr 1fr auto;gap:.7rem;align-items:end;margin:.7rem 0}.checks-grid,.detail-grid,.cache-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem}.detail-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.cache-stats div{display:grid;gap:.15rem;padding:.85rem;border:1px solid var(--line);border-radius:11px;background:var(--surface-1)}.cache-stats strong{font-size:1.25rem;color:var(--primary)}.cache-stats span,.cache-actions,small{color:var(--muted);font-size:.75rem}.cache-actions{display:flex;align-items:center;justify-content:space-between;gap:1rem}.disabled{opacity:.5;pointer-events:none}.danger{color:#ff9ea3!important}
    label{display:grid;gap:.4rem;margin:.5rem 0;color:var(--text);font-weight:650;min-width:0}
    label.check{display:flex;align-items:center;gap:.5rem}
    input:not([type=checkbox]),select,textarea{width:100%;padding:.72rem;border:1px solid var(--line);border-radius:9px;background:#111922;color:var(--text);font:inherit;box-sizing:border-box}textarea{resize:vertical}
    button{padding:.7rem 1rem;border:0;border-radius:9px;background:var(--primary);color:#07120f;font-weight:800;cursor:pointer;white-space:nowrap}
    button.secondary{background:transparent;color:var(--text);border:1px solid var(--line)}button:disabled{opacity:.55;cursor:not-allowed}
    .save{justify-self:end}.error{color:#ff9ea3}.success{color:#76e8b8}
    @media(max-width:800px){.checks-grid,.cache-stats{grid-template-columns:1fr 1fr}.detail-grid{grid-template-columns:1fr}}@media(max-width:650px){.binding,.checks-grid,.cache-stats{grid-template-columns:1fr}.heading,.cache-actions{flex-wrap:wrap}}
  `],
})
export class PluginTranslatorGroupsComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly plugins = inject(GuildPluginService);
  private readonly i18n = inject(TranslationService);
  readonly guildId = this.route.snapshot.paramMap.get('guildId') || '';
  readonly channels = signal<Channel[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly cacheStats = signal<CacheStats>({entries:0,hits:0,misses:0});
  settings: Settings = {installed:false,enabled:false,groups:[],include_source_link:true,languages:[],cache_enabled:true,cache_ttl_hours:72,cache_max_entries:2000,cache_min_characters:4,max_source_characters:4000,fallback_to_original:true,forward_attachments:true,forward_stickers:true,protected_terms:[],detect_source_language:true,detection_min_characters:8};
  protectedTermsText='';
  private get url(): string { return `/api/v1/discord/guilds/${this.guildId}/plugins/translator-groups/settings`; }

  async ngOnInit(): Promise<void> {
    try {
      const [settings, structure, cache] = await Promise.all([
        firstValueFrom(this.http.get<Settings>(this.url)),
        firstValueFrom(this.http.get<{channels: Channel[]}>(`/api/v1/discord/guilds/${this.guildId}/structure`)),
        firstValueFrom(this.http.get<CacheStats>(`${this.url.replace('/settings','')}/cache`)),
      ]);
      this.settings = {...settings, groups:(settings.groups || []).map(group => ({...group, expanded:false}))};
      this.protectedTermsText=(settings.protected_terms||[]).join('\n');
      this.cacheStats.set(cache);
      this.channels.set((structure.channels || []).filter(item => ['text', '0', 'guild_text'].includes(String(item.type).toLowerCase())));
    } catch { this.error.set(this.i18n.t('translator_groups.load_error','Could not load translation settings.')); }
  }

  addGroup(): void { this.settings.groups.push({name:'',enabled:true,channels:[],expanded:true}); }
  hitRate(): number { const value=this.cacheStats();const total=value.hits+value.misses;return total?Math.round(value.hits*100/total):0; }
  async clearCache():Promise<void>{this.busy.set(true);this.error.set('');try{await firstValueFrom(this.http.delete(`${this.url.replace('/settings','')}/cache`));this.cacheStats.set({entries:0,hits:0,misses:0});this.success.set(this.i18n.t('translator_groups.cache_cleared','Translation cache cleared.'))}catch(error:any){this.error.set(error?.error?.detail||this.i18n.t('translator_groups.cache_error','Could not clear translation cache.'))}finally{this.busy.set(false)}}

  async install(): Promise<void> {
    this.busy.set(true); this.error.set('');
    try { await this.plugins.install(this.guildId, 'translator_groups'); await this.ngOnInit(); }
    catch (error: any) { this.error.set(error?.error?.detail || this.i18n.t('translator_groups.install_error','Could not install plugin.')); }
    finally { this.busy.set(false); }
  }

  async toggle(): Promise<void> {
    this.busy.set(true); this.error.set('');
    try {
      if (this.settings.enabled) await this.plugins.disable(this.guildId, 'translator_groups');
      else await this.plugins.enable(this.guildId, 'translator_groups');
      await this.ngOnInit();
    } catch (error: any) { this.error.set(error?.error?.detail || this.i18n.t('translator_groups.state_error','Could not change plugin state.')); }
    finally { this.busy.set(false); }
  }

  async save(): Promise<void> {
    this.busy.set(true); this.error.set(''); this.success.set('');
    const protected_terms=[...new Set(this.protectedTermsText.split(/\r?\n/).map(x=>x.trim()).filter(Boolean))];
    const payload = {groups:this.settings.groups.map(({name,enabled,channels})=>({name,enabled,channels})),include_source_link:this.settings.include_source_link,cache_enabled:this.settings.cache_enabled,cache_ttl_hours:this.settings.cache_ttl_hours,cache_max_entries:this.settings.cache_max_entries,cache_min_characters:this.settings.cache_min_characters,max_source_characters:this.settings.max_source_characters,fallback_to_original:this.settings.fallback_to_original,forward_attachments:this.settings.forward_attachments,forward_stickers:this.settings.forward_stickers,protected_terms,detect_source_language:this.settings.detect_source_language,detection_min_characters:this.settings.detection_min_characters};
    try { const saved=await firstValueFrom(this.http.put<Settings>(this.url, payload)); this.settings={...saved,groups:(saved.groups||[]).map(group=>({...group,expanded:false}))}; this.success.set(this.i18n.t('translator_groups.saved','Translation settings saved.')); }
    catch (error: any) { this.error.set(error?.error?.detail || this.i18n.t('translator_groups.save_error','Could not save translation settings.')); }
    finally { this.busy.set(false); }
  }
}
