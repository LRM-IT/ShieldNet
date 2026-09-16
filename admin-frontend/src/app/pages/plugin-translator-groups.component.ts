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
interface Settings { installed: boolean; enabled: boolean; groups: Group[]; include_source_link: boolean; languages: Language[]; }

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
          <button (click)="toggle()" [disabled]="busy()">{{ settings.enabled ? 'Disable' : 'Enable' }} plugin</button></div>
          <label class="check"><input type="checkbox" [(ngModel)]="settings.include_source_link"> Include link to source message</label>
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
    .binding{display:grid;grid-template-columns:1fr 1fr auto;gap:.7rem;align-items:end;margin:.7rem 0}
    label{display:grid;gap:.4rem;margin:.5rem 0;color:var(--text);font-weight:650;min-width:0}
    label.check{display:flex;align-items:center;gap:.5rem}
    input:not([type=checkbox]),select{width:100%;padding:.72rem;border:1px solid var(--line);border-radius:9px;background:#111922;color:var(--text);font:inherit}
    button{padding:.7rem 1rem;border:0;border-radius:9px;background:var(--primary);color:#07120f;font-weight:800;cursor:pointer;white-space:nowrap}
    button.secondary{background:transparent;color:var(--text);border:1px solid var(--line)}button:disabled{opacity:.55;cursor:not-allowed}
    .save{justify-self:end}.error{color:#ff9ea3}.success{color:#76e8b8}
    @media(max-width:650px){.binding{grid-template-columns:1fr}.heading{flex-wrap:wrap}}
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
  settings: Settings = {installed:false,enabled:false,groups:[],include_source_link:true,languages:[]};
  private get url(): string { return `/api/v1/discord/guilds/${this.guildId}/plugins/translator-groups/settings`; }

  async ngOnInit(): Promise<void> {
    try {
      const [settings, structure] = await Promise.all([
        firstValueFrom(this.http.get<Settings>(this.url)),
        firstValueFrom(this.http.get<{channels: Channel[]}>(`/api/v1/discord/guilds/${this.guildId}/structure`)),
      ]);
      this.settings = {...settings, groups:(settings.groups || []).map(group => ({...group, expanded:false}))};
      this.channels.set((structure.channels || []).filter(item => ['text', '0', 'guild_text'].includes(String(item.type).toLowerCase())));
    } catch { this.error.set('Could not load translation settings.'); }
  }

  addGroup(): void { this.settings.groups.push({name:'',enabled:true,channels:[],expanded:true}); }

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
    const payload = {groups:this.settings.groups.map(({name,enabled,channels})=>({name,enabled,channels})),include_source_link:this.settings.include_source_link};
    try { const saved=await firstValueFrom(this.http.put<Settings>(this.url, payload)); this.settings={...saved,groups:(saved.groups||[]).map(group=>({...group,expanded:false}))}; this.success.set('Translation settings saved.'); }
    catch (error: any) { this.error.set(error?.error?.detail || 'Could not save translation settings.'); }
    finally { this.busy.set(false); }
  }
}
