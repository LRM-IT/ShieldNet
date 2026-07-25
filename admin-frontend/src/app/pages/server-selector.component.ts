import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { GuildAccess } from '../core/api.models';
import { GuildService } from '../core/guild.service';
import { ShellComponent } from '../shared/shell.component';

@Component({
  standalone: true,
  imports: [ShellComponent, RouterLink],
  template: `<sn-shell title="Guild Control Center"><section class="head"><div><span>YOUR DISCORD SERVERS</span><h2>Select a server</h2><p>Open the management workspace for one of your authorized servers.</p></div></section><section class="grid">@for(guild of guilds(); track guild.guild_id){<a class="card" [routerLink]="['/guild',guild.guild_id]"><div class="avatar">{{ guild.name.slice(0,1).toUpperCase() }}</div><div><strong>{{guild.name}}</strong><small>{{guild.member_count}} members · {{guild.access_role}}</small></div><b>→</b></a>}@empty{<div class="empty">No authorized servers.</div>}</section></sn-shell>`,
  styles:[`.head{padding:1rem 0 1.5rem}.head span{color:var(--accent);font-size:.66rem;font-weight:900;letter-spacing:.14em}.head h2{margin:.35rem 0}.head p{margin:0;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.card{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:.8rem;padding:1.1rem;border:1px solid var(--line);border-radius:14px;background:var(--panel);color:var(--text);text-decoration:none}.avatar{width:44px;height:44px;display:grid;place-items:center;border-radius:11px;background:rgba(53,226,178,.12);color:var(--accent);font-weight:900}.card div:nth-child(2){display:grid;gap:.25rem}.card small{color:var(--muted)}.card b{color:var(--accent)}.empty{padding:2rem;border:1px solid var(--line);border-radius:14px;color:var(--muted)}@media(max-width:900px){.grid{grid-template-columns:1fr}}`]
})
export class ServerSelectorComponent implements OnInit {
  readonly guilds = signal<GuildAccess[]>([]);
  constructor(private service: GuildService) {}
  async ngOnInit(){ this.guilds.set(await this.service.list()); }
}
