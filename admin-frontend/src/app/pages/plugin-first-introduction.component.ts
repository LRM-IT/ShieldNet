import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';
import { GuildPluginService } from '../core/guild-plugin.service';
import { DiscordChannelPickerComponent } from '../shared/discord-channel-picker.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

interface Language { code: string; name: string; flag: string | null; }
interface Role { id: string; name: string; managed?: boolean; assignable?: boolean; }
interface Group { id: string; name: string; enabled: boolean; channel_id: string | null; access_role_id: string | null; role_name_mask: string; language_roles: Record<string,string>; default_language_code: string | null; message_id: string | null; }
interface Settings { installed: boolean; enabled: boolean; languages: Language[]; groups: Group[]; }

@Component({
  standalone: true, imports: [FormsModule, ShellComponent, DiscordChannelPickerComponent, TranslatePipe],
  template: `
  <sn-shell [title]="'language_plugin.title'|snT:'Language Selection'"><main class="page">
    <header><span>{{'language_plugin.eyebrow'|snT:'GUILD PLUGIN'}}</span><h2>{{'language_plugin.title'|snT:'Language Selection'}}</h2><p>{{'language_plugin.description'|snT:'Independent language panels and roles for each access level.'}}</p></header>
    @if (error()) { <div class="panel error">{{error()}}</div> }
    @if (success()) { <div class="panel success">{{success()}}</div> }
    @if (!settings.installed) { <section class="panel"><button (click)="install()" [disabled]="busy()">{{'language_plugin.install'|snT:'Install plugin'}}</button></section> }
    @else {
      <section class="panel row"><div><h3>{{'language_plugin.groups'|snT:'Language groups'}}</h3><p>{{'language_plugin.groups_help'|snT:'Name groups according to your server structure. Each group has its own channel and reaction panel.'}}</p></div></section>
      @for (group of settings.groups; track group.id) {
        <section class="panel group-panel"><details><summary><strong>{{group.name}}</strong><span class="chevron">⌄</span></summary>
          <div class="group-body"><div class="row"><p>/language_panel group:{{group.id}}</p>
            <label class="inline"><input type="checkbox" [(ngModel)]="group.enabled"> {{'language_plugin.group_enabled'|snT:'Active group'}}</label></div>
          <label>{{'language_plugin.group_name'|snT:'Group name'}}<input [(ngModel)]="group.name" maxlength="80"></label>
          <label>{{'language_plugin.channel'|snT:'Discord thread or text channel'}}
            <sn-discord-channel-picker [guildId]="guildId" [value]="group.channel_id" (valueChange)="group.channel_id=$event" /></label>
          <label>{{'language_plugin.access_role'|snT:'Group access role'}}<select [(ngModel)]="group.access_role_id"><option [ngValue]="null">{{'language_plugin.select_access_role'|snT:'Select an access role'}}</option>
            @for (role of allRoles(); track role.id) { <option [value]="role.id">{{role.name}}</option> }</select></label>
          <p>{{'language_plugin.access_role_help'|snT:'Only members with this access role can select a language in the group.'}}</p>
          <label>{{'language_plugin.default_language'|snT:'Default language'}}<select [(ngModel)]="group.default_language_code"><option [ngValue]="null">{{'language_plugin.no_default_language'|snT:'No default language'}}</option>
            @for (language of settings.languages; track language.code) { <option [value]="language.code">{{language.flag}} {{language.name}}</option> }</select></label>
          <p>{{'language_plugin.default_language_help'|snT:'This language role remains assigned to members with the access role even after another flag is selected.'}}</p>
          <div class="builder"><h4>{{'language_plugin.language_roles'|snT:'Language roles'}}</h4><p>{{'language_plugin.mask_variables'|snT:'Variables: {group}, {flag}, {name}, {code}.'}}</p>
            <label>{{'language_plugin.name_mask'|snT:'Role name mask'}}<input [(ngModel)]="group.role_name_mask" maxlength="100" placeholder="{group} - {name}"></label>
            <div class="preview">@for (language of settings.languages; track language.code) { <small>{{language.code}} → {{rolePreview(group, language)}}</small> }</div>
            <button (click)="ensureRoles(group)" [disabled]="busy() || !settings.languages.length">{{provisioning() === group.id ? ('language_plugin.creating_roles'|snT:'Creating roles…') : ('language_plugin.ensure_roles'|snT:'Find or create roles')}}</button>
          </div>
          @for (language of settings.languages; track language.code) {
            <label>{{language.flag || ('language_plugin.no_flag'|snT:'No flag')}} {{language.name}} ({{language.code}})
              <select [(ngModel)]="group.language_roles[language.code]"><option value="">{{'language_plugin.select_role'|snT:'Select a role'}}</option>
                @for (role of assignableRoles(); track role.id) { <option [value]="role.id">{{role.name}}</option> }</select></label>
          } @empty { <p>{{'language_plugin.configure_languages_first'|snT:'Configure the server languages first.'}}</p> }
          @if (group.message_id) { <p>{{'language_plugin.published_panel'|snT:'Published panel'}}: {{group.message_id}}</p> }
          <button (click)="publish(group)" [disabled]="busy() || !settings.enabled || !group.enabled">{{'language_plugin.publish'|snT:'Publish in the selected channel'}}</button>
          <button class="secondary" (click)="removeGroup(group.id)" [disabled]="busy() || settings.groups.length === 1">{{'language_plugin.delete_group'|snT:'Delete group'}}</button>
          </div></details></section>
      }
      <section class="panel"><div class="row"><button class="secondary" (click)="addGroup()" [disabled]="busy() || settings.groups.length >= 10">{{'language_plugin.add_group'|snT:'Add group'}}</button>
        <button (click)="save()" [disabled]="busy()">{{'language_plugin.save'|snT:'Save settings'}}</button></div>
        <p>{{'language_plugin.workflow_help'|snT:'Save groups, create language roles, enable the plugin and publish every active group panel with /language_panel.'}}</p>
        <p>{{'language_plugin.permissions_help'|snT:'The bot needs View Channel, Send Messages, Add Reactions, Read Message History and Manage Messages, with its role above the language roles.'}}</p></section>
    }
  </main></sn-shell>`,
  styles: [`
    .page{max-width:960px;margin:auto;display:grid;gap:1rem;padding-bottom:3rem}header span{color:var(--primary);font-size:.7rem;font-weight:800;letter-spacing:.12em}
    h2{margin:.3rem 0;font-size:1.8rem}h3,h4{margin:0 0 .6rem}p{color:var(--muted);margin:.3rem 0 1rem}.panel{padding:1.25rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}
    .row{display:flex;justify-content:space-between;align-items:start;gap:1rem;flex-wrap:wrap}.group-panel{padding:0}.group-panel summary{list-style:none;display:flex;align-items:center;justify-content:space-between;cursor:pointer;padding:1.25rem}.group-panel summary::-webkit-details-marker{display:none}.group-panel summary strong{font-size:1.15rem}.chevron{font-size:1.5rem;transition:transform .15s}.group-panel details[open] .chevron{transform:rotate(180deg)}.group-body{padding:0 1.25rem 1.25rem;border-top:1px solid var(--line)}.builder{margin:1rem 0;padding:1rem;border:1px solid var(--line);border-radius:12px}.preview{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0 1rem}.preview small{padding:.35rem .6rem;border:1px solid var(--line);border-radius:7px;color:var(--muted)}
    label{display:grid;gap:.4rem;margin:.85rem 0;color:var(--text);font-weight:650}.inline{display:flex;align-items:center;gap:.5rem}.inline input{width:auto}
    select,input{width:100%;padding:.72rem;border:1px solid var(--line);border-radius:9px;background:#111922;color:var(--text);font:inherit}
    button{padding:.7rem 1rem;border:0;border-radius:9px;background:var(--primary);color:#07120f;font-weight:800;cursor:pointer}.secondary{background:#26343e;color:var(--text)}button:disabled{opacity:.55;cursor:not-allowed}.error{color:#ff9ea3}.success{color:#76e8b8}
  `],
})
export class PluginFirstIntroductionComponent implements OnInit {
  private readonly http = inject(HttpClient); private readonly route = inject(ActivatedRoute); private readonly plugins = inject(GuildPluginService); private readonly i18n = inject(TranslationService);
  readonly guildId = this.route.snapshot.paramMap.get('guildId') || '';
  readonly allRoles = signal<Role[]>([]); readonly assignableRoles = signal<Role[]>([]);
  readonly busy = signal(false); readonly provisioning = signal(''); readonly error = signal(''); readonly success = signal('');
  settings: Settings = {installed:false,enabled:false,languages:[],groups:[]};
  private get url(): string { return `/api/v1/discord/guilds/${this.guildId}/plugins/first-introduction/settings`; }
  async ngOnInit(): Promise<void> {
    try { const [settings, structure] = await Promise.all([firstValueFrom(this.http.get<Settings>(this.url)),firstValueFrom(this.http.get<{roles:Role[]}>(`/api/v1/discord/guilds/${this.guildId}/structure`))]);
      this.settings = settings; const roles = (structure.roles || []).filter(role => !role.managed && role.name !== '@everyone');
      this.allRoles.set(roles); this.assignableRoles.set(roles.filter(role => role.assignable));
    } catch { this.error.set(this.i18n.t('language_plugin.load_error','Could not load settings or Discord roles.')); }
  }
  async install(): Promise<void> { this.busy.set(true); this.error.set(''); try { await this.plugins.install(this.guildId,'first_introduction'); await this.ngOnInit(); }
    catch { this.error.set(this.i18n.t('language_plugin.install_error','Could not install the plugin.')); } finally { this.busy.set(false); } }
  async toggle(): Promise<void> { this.busy.set(true); this.error.set(''); try { if (this.settings.enabled) await this.plugins.disable(this.guildId,'first_introduction');
      else await this.plugins.enable(this.guildId,'first_introduction'); await this.ngOnInit(); }
    catch { this.error.set(this.i18n.t('language_plugin.toggle_error','Could not change the plugin state. Check the group settings.')); } finally { this.busy.set(false); } }
  private payload(): object { return {groups:this.settings.groups.map(group => ({id:group.id,name:group.name.trim(),enabled:group.enabled,
    channel_id:group.channel_id?.trim() || null,access_role_id:group.access_role_id || null,role_name_mask:group.role_name_mask,default_language_code:group.default_language_code || null,
    language_roles:Object.fromEntries(Object.entries(group.language_roles || {}).filter(([,value]) => value))}))}; }
  private async persist(): Promise<void> { this.settings = await firstValueFrom(this.http.put<Settings>(this.url,this.payload())); }
  async save(): Promise<void> { this.busy.set(true); this.error.set(''); this.success.set(''); try { await this.persist(); this.success.set(this.i18n.t('language_plugin.saved','Settings saved. Publish the panels for active groups.')); }
    catch { this.error.set(this.i18n.t('language_plugin.save_error','Could not save settings.')); } finally { this.busy.set(false); } }
  addGroup(): void { const id = `group${Date.now().toString(36)}`; this.settings.groups.push({id,name:this.i18n.t('language_plugin.new_group','New group'),enabled:false,channel_id:null,access_role_id:null,role_name_mask:'{group} - {name}',language_roles:{},default_language_code:null,message_id:null}); }
  removeGroup(id:string): void { this.settings.groups = this.settings.groups.filter(group => group.id !== id); }
  rolePreview(group:Group,language:Language): string { return (group.role_name_mask || '').replace(/\{group\}/g,group.name).replace(/\{flag\}/g,language.flag || '').replace(/\{name\}/g,language.name).replace(/\{code\}/g,language.code).trim(); }
  async publish(group:Group): Promise<void> {
    if (this.busy()) return; this.busy.set(true); this.error.set(''); this.success.set('');
    const base = `/api/v1/discord/guilds/${this.guildId}/plugins/first-introduction/panels`;
    try { await this.persist(); const result = await firstValueFrom(this.http.post<{job_id:string}>(`${base}/publish`,{group_id:group.id}));
      let complete = false;
      for (let attempt=0;attempt<30;attempt++) { await new Promise(resolve => setTimeout(resolve,1500));
        const status = await firstValueFrom(this.http.get<{status:string;error:string|null;message_id:string|null}>(`${base}/jobs/${result.job_id}`));
        if (status.status === 'failed') throw new Error(this.i18n.t('language_plugin.publish_failed','Could not publish the message.'));
        if (status.status !== 'completed') continue;
        complete = true; await this.ngOnInit(); this.success.set(this.i18n.t('language_plugin.published','The panel for {group} was published in Discord.').replace('{group}',group.name)); break;
      }
      if (!complete) throw new Error(this.i18n.t('language_plugin.publish_pending','Publishing is still in progress. Refresh the page later.'));
    } catch (error:any) { this.error.set(error?.message || this.i18n.t('language_plugin.publish_error','Could not publish the panel.')); }
    finally { this.busy.set(false); }
  }
  async ensureRoles(group:Group): Promise<void> {
    if (this.busy()) return; this.busy.set(true); this.provisioning.set(group.id); this.error.set(''); this.success.set('');
    const base = `/api/v1/discord/guilds/${this.guildId}/plugins/first-introduction/roles`;
    try { await this.persist(); const result = await firstValueFrom(this.http.post<{jobs:string[]}>(`${base}/ensure`,{group_id:group.id,role_name_mask:group.role_name_mask}));
      if (result.jobs.length) { let complete = false; for (let attempt=0;attempt<40;attempt++) { await new Promise(resolve => setTimeout(resolve,1500));
        const status = await firstValueFrom(this.http.post<{complete:boolean;items:{name:string;status:string;error:string|null}[]}>(`${base}/status`,result.jobs));
        if (!status.complete) continue; const failed = status.items.filter(item => item.status !== 'completed');
        if (failed.length) this.error.set(failed.map(item => `${item.name}: ${this.i18n.t('language_plugin.role_creation_error','Role creation failed')}`).join('; ')); complete = true; break; }
        if (!complete) throw new Error(this.i18n.t('language_plugin.discord_timeout','Discord timed out. Refresh the page.')); }
      await this.ngOnInit(); if (!this.error()) this.success.set(this.i18n.t('language_plugin.roles_ready','Language roles for {group} are ready.').replace('{group}',group.name));
    } catch (error:any) { this.error.set(error?.message || this.i18n.t('language_plugin.roles_error','Could not create the roles.')); }
    finally { this.busy.set(false); this.provisioning.set(''); }
  }
}
