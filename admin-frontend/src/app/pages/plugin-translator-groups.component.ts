import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';
import { GuildPluginService } from '../core/guild-plugin.service';

interface Language { code: string; name: string; }
interface Channel { id: string; name: string; type: string; }
interface Binding { channel_id: string; language: string; }
interface Group { name: string; enabled: boolean; channels: Binding[]; expanded?: boolean; }
interface Settings { installed:boolean;enabled:boolean;groups:Group[];include_source_link:boolean;languages:Language[];cache_enabled:boolean;cache_ttl_hours:number;cache_max_entries:number;cache_min_characters:number;max_source_characters:number;fallback_to_original:boolean;forward_attachments:boolean;forward_stickers:boolean;protected_terms:string[]; }
interface CacheStats { entries:number;hits:number;misses:number; }

@Component({
  standalone: true,
  imports: [FormsModule, ShellComponent],
  template: `
    <sn-shell title="Translator Groups"><main class="page">
      <header><span>GUILD PLUGIN</span><h2>Translator Groups</h2>
        <p>Messages in one language channel are translated into the other channels of its group through AI Center.</p></header>
      @if (error()) { <div class="panel error">{{ error() }}</div> }
      @if (success()) { <div class="panel success">{{ success() }}</div> }
      @if (!settings.installed) {
        <section class="panel"><p>Install this plugin to configure translation groups.</p>
          <button (click)="install()" [disabled]="busy()">Install plugin</button></section>
      } @else {
        <section class="panel"><div class="heading"><div><h3>Translation setup</h3>
          <p>Configure the <strong>translation</strong> route and provider in AI Center. Server Languages controls the available language codes.</p></div>
          </div>
          <div class="checks-grid"><label class="check"><input type="checkbox" [(ngModel)]="settings.include_source_link"> Include link to source message</label><label class="check"><input type="checkbox" [(ngModel)]="settings.forward_attachments"> Forward attachments</label><label class="check"><input type="checkbox" [(ngModel)]="settings.forward_stickers"> Forward stickers</label><label class="check"><input type="checkbox" [(ngModel)]="settings.fallback_to_original"> Send original text if AI fails</label></div>
          <label>Maximum source text length<input type="number" min="100" max="12000" step="100" [(ngModel)]="settings.max_source_characters"><small>Longer messages are truncated before being sent to AI.</small></label>
        </section>
        <section class="panel"><h3>Words and phrases that must not be translated</h3><p>Add brand names, game terms, commands, role names or usernames. Enter one term per line; matching is case-insensitive and the original spelling is preserved.</p><label>Protected terms<textarea rows="7" [(ngModel)]="protectedTermsText" placeholder="GuildConsole&#10;/verify&#10;R5&#10;ShieldNet"></textarea><small>Up to 100 entries, 80 characters each.</small></label></section>
        <section class="panel cache-panel"><div class="heading"><div><h3>Translation cache</h3><p>Reuse translations of identical text and avoid repeated AI token charges.</p></div><label class="check switch"><input type="checkbox" [(ngModel)]="settings.cache_enabled"> Cache enabled</label></div>
          <div class="cache-stats"><div><strong>{{cacheStats().entries}}</strong><span>Cached translations</span></div><div><strong>{{cacheStats().hits}}</strong><span>AI requests saved</span></div><div><strong>{{cacheStats().misses}}</strong><span>Cache misses</span></div><div><strong>{{hitRate()}}%</strong><span>Hit rate</span></div></div>
          <div class="detail-grid" [class.disabled]="!settings.cache_enabled"><label>Retention, hours<input type="number" min="1" max="720" [(ngModel)]="settings.cache_ttl_hours"><small>Expired translations are generated again.</small></label><label>Maximum entries<input type="number" min="100" max="50000" step="100" [(ngModel)]="settings.cache_max_entries"><small>Oldest entries are removed first.</small></label><label>Minimum text length<input type="number" min="1" max="500" [(ngModel)]="settings.cache_min_characters"><small>Shorter messages bypass the cache.</small></label></div>
          <div class="cache-actions"><span>Cache keys are isolated per Discord server and target language.</span><button class="secondary danger" (click)="clearCache()" [disabled]="busy()||!cacheStats().entries">Clear cache</button></div>
        </section>
        <section class="panel"><div class="heading"><div><h3>Groups</h3><p>Each group links two or more text channels.</p></div>
          <button (click)="addGroup()" [disabled]="busy()">Add group</button></div>
          @for (group of settings.groups; track $index; let gi = $index) {
            <article class="group">
              <button class="group-summary" type="button" (click)="group.expanded=!group.expanded" [attr.aria-expanded]="group.expanded">
                <span><strong>{{ group.name || 'New group' }}</strong><small>{{ group.channels.length }} channels · {{ group.enabled ? 'Enabled' : 'Disabled' }}</small></span>
                <span class="chevron" [class.open]="group.expanded">⌄</span>
              </button>
              @if (group.expanded) {
                <div class="group-body">
                  <div class="heading"><label>Group name<input [(ngModel)]="group.name" maxlength="60"></label>
                    <div class="actions"><label class="check"><input type="checkbox" [(ngModel)]="group.enabled"> Enabled</label>
                      <button class="secondary" (click)="settings.groups.splice(gi, 1)">Delete group</button></div></div>
                  @for (binding of group.channels; track $index; let bi = $index) {
                    <div class="binding"><label>Channel<select [(ngModel)]="binding.channel_id">
                        <option value="">Select channel</option>
                        @for (channel of channels(); track channel.id) { <option [value]="channel.id">#{{ channel.name }}</option> }
                      </select></label>
                      <label>Language<select [(ngModel)]="binding.language"><option value="">Select language</option>
                        @for (language of settings.languages; track language.code) { <option [value]="language.code">{{ language.name }} ({{ language.code }})</option> }
                      </select></label>
                      <button class="secondary remove" (click)="group.channels.splice(bi, 1)">Remove</button></div>
                  }
                  <button class="secondary" (click)="group.channels.push({channel_id: '', language: ''})">Add channel</button>
                </div>
              }
            </article>
          } @empty { <p>No translation groups yet.</p> }
        </section>
        <section class="panel"><h3>Basic Discord commands</h3><p>Administrators can use <strong>/group_add</strong>, <strong>/group_language</strong> in a channel, and <strong>/group_unlanguage</strong>. All other settings stay here.</p>
          <p>The bot needs Message Content access and permission to manage webhooks in target channels. Translation does not run until this plugin and the AI Center translation route are enabled.</p></section>
        <button class="save" (click)="save()" [disabled]="busy()">Save settings</button>
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
  readonly guildId = this.route.snapshot.paramMap.get('guildId') || '';
  readonly channels = signal<Channel[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly cacheStats = signal<CacheStats>({entries:0,hits:0,misses:0});
  settings: Settings = {installed:false,enabled:false,groups:[],include_source_link:true,languages:[],cache_enabled:true,cache_ttl_hours:72,cache_max_entries:2000,cache_min_characters:4,max_source_characters:4000,fallback_to_original:true,forward_attachments:true,forward_stickers:true,protected_terms:[]};
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
    } catch { this.error.set('Could not load translation settings.'); }
  }

  addGroup(): void { this.settings.groups.push({name:'',enabled:true,channels:[],expanded:true}); }
  hitRate(): number { const value=this.cacheStats();const total=value.hits+value.misses;return total?Math.round(value.hits*100/total):0; }
  async clearCache():Promise<void>{this.busy.set(true);this.error.set('');try{await firstValueFrom(this.http.delete(`${this.url.replace('/settings','')}/cache`));this.cacheStats.set({entries:0,hits:0,misses:0});this.success.set('Translation cache cleared.')}catch(error:any){this.error.set(error?.error?.detail||'Could not clear translation cache.')}finally{this.busy.set(false)}}

  async install(): Promise<void> {
    this.busy.set(true); this.error.set('');
    try { await this.plugins.install(this.guildId, 'translator_groups'); await this.ngOnInit(); }
    catch (error: any) { this.error.set(error?.error?.detail || 'Could not install plugin.'); }
    finally { this.busy.set(false); }
  }

  async toggle(): Promise<void> {
    this.busy.set(true); this.error.set('');
    try {
      if (this.settings.enabled) await this.plugins.disable(this.guildId, 'translator_groups');
      else await this.plugins.enable(this.guildId, 'translator_groups');
      await this.ngOnInit();
    } catch (error: any) { this.error.set(error?.error?.detail || 'Could not change plugin state.'); }
    finally { this.busy.set(false); }
  }

  async save(): Promise<void> {
    this.busy.set(true); this.error.set(''); this.success.set('');
    const protected_terms=[...new Set(this.protectedTermsText.split(/\r?\n/).map(x=>x.trim()).filter(Boolean))];
    const payload = {groups:this.settings.groups.map(({name,enabled,channels})=>({name,enabled,channels})),include_source_link:this.settings.include_source_link,cache_enabled:this.settings.cache_enabled,cache_ttl_hours:this.settings.cache_ttl_hours,cache_max_entries:this.settings.cache_max_entries,cache_min_characters:this.settings.cache_min_characters,max_source_characters:this.settings.max_source_characters,fallback_to_original:this.settings.fallback_to_original,forward_attachments:this.settings.forward_attachments,forward_stickers:this.settings.forward_stickers,protected_terms};
    try { const saved=await firstValueFrom(this.http.put<Settings>(this.url, payload)); this.settings={...saved,groups:(saved.groups||[]).map(group=>({...group,expanded:false}))}; this.success.set('Translation settings saved.'); }
    catch (error: any) { this.error.set(error?.error?.detail || 'Could not save translation settings.'); }
    finally { this.busy.set(false); }
  }
}
