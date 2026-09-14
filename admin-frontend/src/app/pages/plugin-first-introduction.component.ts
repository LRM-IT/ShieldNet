import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';
import { GuildPluginService } from '../core/guild-plugin.service';
import { DiscordChannelPickerComponent } from '../shared/discord-channel-picker.component';

interface Language { code: string; name: string; flag: string | null; }
interface Role { id: string; name: string; managed?: boolean; assignable?: boolean; }
interface Group { id: string; name: string; enabled: boolean; channel_id: string | null; access_role_id: string | null; role_name_mask: string; language_roles: Record<string,string>; message_id: string | null; }
interface Settings { installed: boolean; enabled: boolean; languages: Language[]; groups: Group[]; }

@Component({
  standalone: true, imports: [FormsModule, ShellComponent, DiscordChannelPickerComponent],
  template: `
  <sn-shell title="Language Selection"><main class="page">
    <header><span>GUILD PLUGIN</span><h2>Language Selection</h2><p>Окремі мовні панелі та ролі для кожного рівня доступу.</p></header>
    @if (error()) { <div class="panel error">{{error()}}</div> }
    @if (success()) { <div class="panel success">{{success()}}</div> }
    @if (!settings.installed) { <section class="panel"><button (click)="install()" [disabled]="busy()">Установити плагін</button></section> }
    @else {
      <section class="panel row"><div><h3>Групи мов</h3><p>R1, R4 та R5 мають власні гілки й панелі реакцій.</p></div>
        <button (click)="toggle()" [disabled]="busy()">{{settings.enabled ? 'Вимкнути плагін' : 'Увімкнути плагін'}}</button></section>
      @for (group of settings.groups; track group.id) {
        <section class="panel">
          <div class="row"><div><h3>{{group.name}} ({{group.id}})</h3><p>/language_panel group:{{group.id}}</p></div>
            <label class="inline"><input type="checkbox" [(ngModel)]="group.enabled"> Активна група</label></div>
          <label>Назва групи<input [(ngModel)]="group.name" maxlength="80"></label>
          <label>Гілка або текстовий канал Discord
            <sn-discord-channel-picker [guildId]="guildId" [value]="group.channel_id" (valueChange)="group.channel_id=$event" /></label>
          <label>Роль доступу до групи<select [(ngModel)]="group.access_role_id"><option [ngValue]="null">Виберіть роль доступу</option>
            @for (role of allRoles(); track role.id) { <option [value]="role.id">{{role.name}}</option> }</select></label>
          <p>Лише учасник з роллю доступу може вибрати мову в цій групі. Для R4/R5 виберіть роль відповідного рівня.</p>
          <div class="builder"><h4>Мовні ролі</h4><p>Маска: &#123;group&#125;, &#123;flag&#125;, &#123;name&#125;, &#123;code&#125;.</p>
            <label>Маска назви<input [(ngModel)]="group.role_name_mask" maxlength="100" placeholder="{group} - {name}"></label>
            <div class="preview">@for (language of settings.languages; track language.code) { <small>{{language.code}} → {{rolePreview(group, language)}}</small> }</div>
            <button (click)="ensureRoles(group)" [disabled]="busy() || !settings.languages.length">{{provisioning() === group.id ? 'Створюємо ролі…' : 'Знайти або створити ролі'}}</button>
          </div>
          @for (language of settings.languages; track language.code) {
            <label>{{language.flag || 'No flag'}} {{language.name}} ({{language.code}})
              <select [(ngModel)]="group.language_roles[language.code]"><option value="">Виберіть роль</option>
                @for (role of assignableRoles(); track role.id) { <option [value]="role.id">{{role.name}}</option> }</select></label>
          } @empty { <p>Спочатку налаштуйте мови сервера.</p> }
          @if (group.message_id) { <p>Опублікована панель: {{group.message_id}}</p> }
          @if (!['r1','r4','r5'].includes(group.id)) { <button class="secondary" (click)="removeGroup(group.id)" [disabled]="busy()">Видалити групу</button> }
        </section>
      }
      <section class="panel"><div class="row"><button class="secondary" (click)="addGroup()" [disabled]="busy() || settings.groups.length >= 10">Додати групу</button>
        <button (click)="save()" [disabled]="busy()">Зберегти налаштування</button></div>
        <p>Збережіть групи, створіть мовні ролі, увімкніть плагін і опублікуйте панель кожної активної групи командою /language_panel.</p>
        <p>Боту потрібні View Channel, Send Messages, Add Reactions, Read Message History, Manage Messages і роль вище мовних ролей.</p></section>
    }
  </main></sn-shell>`,
  styles: [`
    .page{max-width:960px;margin:auto;display:grid;gap:1rem;padding-bottom:3rem}header span{color:var(--primary);font-size:.7rem;font-weight:800;letter-spacing:.12em}
    h2{margin:.3rem 0;font-size:1.8rem}h3,h4{margin:0 0 .6rem}p{color:var(--muted);margin:.3rem 0 1rem}.panel{padding:1.25rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}
    .row{display:flex;justify-content:space-between;align-items:start;gap:1rem;flex-wrap:wrap}.builder{margin:1rem 0;padding:1rem;border:1px solid var(--line);border-radius:12px}.preview{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0 1rem}.preview small{padding:.35rem .6rem;border:1px solid var(--line);border-radius:7px;color:var(--muted)}
    label{display:grid;gap:.4rem;margin:.85rem 0;color:var(--text);font-weight:650}.inline{display:flex;align-items:center;gap:.5rem}.inline input{width:auto}
    select,input{width:100%;padding:.72rem;border:1px solid var(--line);border-radius:9px;background:#111922;color:var(--text);font:inherit}
    button{padding:.7rem 1rem;border:0;border-radius:9px;background:var(--primary);color:#07120f;font-weight:800;cursor:pointer}.secondary{background:#26343e;color:var(--text)}button:disabled{opacity:.55;cursor:not-allowed}.error{color:#ff9ea3}.success{color:#76e8b8}
  `],
})
export class PluginFirstIntroductionComponent implements OnInit {
  private readonly http = inject(HttpClient); private readonly route = inject(ActivatedRoute); private readonly plugins = inject(GuildPluginService);
  readonly guildId = this.route.snapshot.paramMap.get('guildId') || '';
  readonly allRoles = signal<Role[]>([]); readonly assignableRoles = signal<Role[]>([]);
  readonly busy = signal(false); readonly provisioning = signal(''); readonly error = signal(''); readonly success = signal('');
  settings: Settings = {installed:false,enabled:false,languages:[],groups:[]};
  private get url(): string { return `/api/v1/discord/guilds/${this.guildId}/plugins/first-introduction/settings`; }
  async ngOnInit(): Promise<void> {
    try { const [settings, structure] = await Promise.all([firstValueFrom(this.http.get<Settings>(this.url)),firstValueFrom(this.http.get<{roles:Role[]}>(`/api/v1/discord/guilds/${this.guildId}/structure`))]);
      this.settings = settings; const roles = (structure.roles || []).filter(role => !role.managed && role.name !== '@everyone');
      this.allRoles.set(roles); this.assignableRoles.set(roles.filter(role => role.assignable));
    } catch { this.error.set('Не вдалося завантажити налаштування або Discord-ролі.'); }
  }
  async install(): Promise<void> { this.busy.set(true); this.error.set(''); try { await this.plugins.install(this.guildId,'first_introduction'); await this.ngOnInit(); }
    catch (error:any) { this.error.set(error?.error?.detail || 'Не вдалося встановити плагін.'); } finally { this.busy.set(false); } }
  async toggle(): Promise<void> { this.busy.set(true); this.error.set(''); try { if (this.settings.enabled) await this.plugins.disable(this.guildId,'first_introduction');
      else await this.plugins.enable(this.guildId,'first_introduction'); await this.ngOnInit(); }
    catch (error:any) { this.error.set(error?.error?.detail || 'Не вдалося змінити стан плагіна. Перевірте налаштування груп.'); } finally { this.busy.set(false); } }
  private payload(): object { return {groups:this.settings.groups.map(group => ({id:group.id,name:group.name.trim(),enabled:group.enabled,
    channel_id:group.channel_id?.trim() || null,access_role_id:group.access_role_id || null,role_name_mask:group.role_name_mask,
    language_roles:Object.fromEntries(Object.entries(group.language_roles || {}).filter(([,value]) => value))}))}; }
  private async persist(): Promise<void> { this.settings = await firstValueFrom(this.http.put<Settings>(this.url,this.payload())); }
  async save(): Promise<void> { this.busy.set(true); this.error.set(''); this.success.set(''); try { await this.persist(); this.success.set('Налаштування збережено. Опублікуйте панелі активних груп.'); }
    catch (error:any) { this.error.set(error?.error?.detail || 'Не вдалося зберегти налаштування.'); } finally { this.busy.set(false); } }
  addGroup(): void { const id = `group${Date.now().toString(36)}`; this.settings.groups.push({id,name:'Нова група',enabled:false,channel_id:null,access_role_id:null,role_name_mask:'{group} - {name}',language_roles:{},message_id:null}); }
  removeGroup(id:string): void { this.settings.groups = this.settings.groups.filter(group => group.id !== id); }
  rolePreview(group:Group,language:Language): string { return (group.role_name_mask || '').replace(/\{group\}/g,group.name).replace(/\{flag\}/g,language.flag || '').replace(/\{name\}/g,language.name).replace(/\{code\}/g,language.code).trim(); }
  async ensureRoles(group:Group): Promise<void> {
    if (this.busy()) return; this.busy.set(true); this.provisioning.set(group.id); this.error.set(''); this.success.set('');
    const base = `/api/v1/discord/guilds/${this.guildId}/plugins/first-introduction/roles`;
    try { await this.persist(); const result = await firstValueFrom(this.http.post<{jobs:string[]}>(`${base}/ensure`,{group_id:group.id,role_name_mask:group.role_name_mask}));
      if (result.jobs.length) { let complete = false; for (let attempt=0;attempt<40;attempt++) { await new Promise(resolve => setTimeout(resolve,1500));
        const status = await firstValueFrom(this.http.post<{complete:boolean;items:{name:string;status:string;error:string|null}[]}>(`${base}/status`,result.jobs));
        if (!status.complete) continue; const failed = status.items.filter(item => item.status !== 'completed');
        if (failed.length) this.error.set(failed.map(item => `${item.name}: ${item.error || 'Помилка створення ролі'}`).join('; ')); complete = true; break; }
        if (!complete) throw new Error('Час очікування Discord вичерпано. Оновіть сторінку.'); }
      await this.ngOnInit(); if (!this.error()) this.success.set(`Мовні ролі групи ${group.name} готові.`);
    } catch (error:any) { this.error.set(error?.error?.detail || error?.message || 'Не вдалося створити ролі.'); }
    finally { this.busy.set(false); this.provisioning.set(''); }
  }
}
