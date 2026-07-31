import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

type Provider = {
  id: string; name: string; provider_type: string; api_base_url?: string;
  key_hint?: string; default_model?: string; enabled: boolean; priority: number;
  timeout_seconds: number; max_retries: number; capabilities: string[];
  last_health_status?: string; last_health_latency_ms?: number; last_error?: string;
};
type RouteTarget = { id?: string; provider_id: string; position: number; model?: string; timeout_seconds?: number; retries: number; enabled: boolean; configuration: any; };
type AiRoute = { id?: string; guild_id?: string; capability: string; enabled: boolean; max_total_attempts: number; failure_threshold: number; cooldown_seconds: number; configuration: any; targets: RouteTarget[]; };

@Component({
  selector: 'app-guild-ai',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
  <section class="page">
    <header><div><h1>AI Center</h1><p>Provider tokens and server-level fault-tolerant routing.</p></div>
      <button class="primary" (click)="openProvider()">+ Add provider</button></header>

    <nav><button [class.active]="tab==='providers'" (click)="tab='providers'">Providers</button>
      <button [class.active]="tab==='routes'" (click)="tab='routes'">Fault-tolerance routes</button></nav>

    <div *ngIf="error" class="error">{{error}}</div>

    <div *ngIf="tab==='providers'" class="grid">
      <article *ngFor="let p of providers" class="card">
        <div class="row"><strong>{{p.name}}</strong><span [class.ok]="p.last_health_status==='connected'">{{p.last_health_status || 'not tested'}}</span></div>
        <p>{{p.provider_type}} · {{p.default_model || 'model not selected'}}</p>
        <small>Key: {{p.key_hint || '—'}} · priority {{p.priority}} · timeout {{p.timeout_seconds}}s</small>
        <div class="actions"><button (click)="test(p)">Test</button><button (click)="openProvider(p)">Edit</button><button class="danger" (click)="remove(p)">Delete</button></div>
      </article>
      <p *ngIf="!providers.length">No provider connections configured for this server.</p>
    </div>

    <div *ngIf="tab==='routes'">
      <div class="route-create"><select [(ngModel)]="newCapability"><option *ngFor="let c of capabilities" [value]="c">{{c}}</option></select>
        <button class="primary" (click)="createRoute()">Configure route</button></div>
      <article *ngFor="let r of routes" class="route card">
        <div class="row"><h3>{{r.capability}}</h3><label><input type="checkbox" [(ngModel)]="r.enabled"> Enabled</label></div>
        <div class="settings"><label>Max attempts<input type="number" [(ngModel)]="r.max_total_attempts"></label>
          <label>Failure threshold<input type="number" [(ngModel)]="r.failure_threshold"></label>
          <label>Cooldown, sec<input type="number" [(ngModel)]="r.cooldown_seconds"></label></div>
        <h4>Provider order</h4>
        <div *ngFor="let t of r.targets; let i=index" class="target">
          <b>{{i+1}}</b><select [(ngModel)]="t.provider_id"><option *ngFor="let p of providers" [value]="p.id">{{p.name}}</option></select>
          <input [(ngModel)]="t.model" placeholder="Model (optional)">
          <input type="number" [(ngModel)]="t.retries" min="0" placeholder="Retries">
          <button (click)="move(r,i,-1)">↑</button><button (click)="move(r,i,1)">↓</button><button class="danger" (click)="r.targets.splice(i,1)">×</button>
        </div>
        <div class="actions"><button (click)="addTarget(r)">+ Provider</button><button class="primary" (click)="saveRoute(r)">Save route</button></div>
      </article>
    </div>

    <div class="modal" *ngIf="editing"><form class="dialog" (ngSubmit)="saveProvider()">
      <h2>{{form.id ? 'Edit provider' : 'Add provider'}}</h2>
      <label>Name<input required [(ngModel)]="form.name" name="name"></label>
      <label>Provider<select [(ngModel)]="form.provider_type" name="type"><option *ngFor="let p of providerTypes" [value]="p">{{p}}</option></select></label>
      <label>API key<input [required]="!form.id" type="password" [(ngModel)]="form.api_key" name="key" placeholder="Leave empty to keep current key"></label>
      <label>API base URL<input [(ngModel)]="form.api_base_url" name="url"></label>
      <label>Default model<input [(ngModel)]="form.default_model" name="model"></label>
      <div class="settings"><label>Priority<input type="number" [(ngModel)]="form.priority" name="priority"></label>
        <label>Timeout<input type="number" [(ngModel)]="form.timeout_seconds" name="timeout"></label></div>
      <label><input type="checkbox" [(ngModel)]="form.enabled" name="enabled"> Enabled</label>
      <div class="actions"><button type="button" (click)="editing=false">Cancel</button><button class="primary" type="submit">Save</button></div>
    </form></div>
  </section>`,
  styles: [`
    .page{padding:24px;max-width:1200px;margin:auto}header,.row,.actions,.target,.settings,.route-create{display:flex;gap:12px;align-items:center}
    header,.row{justify-content:space-between}nav{display:flex;gap:8px;margin:20px 0}button,select,input{padding:9px 12px;border:1px solid #334155;border-radius:8px;background:#0f172a;color:#e2e8f0}
    button{cursor:pointer}.primary{background:#2563eb}.danger{border-color:#7f1d1d;color:#fca5a5}.active{background:#334155}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px}
    .card{background:#111827;border:1px solid #273449;border-radius:12px;padding:16px;margin-bottom:14px}.ok{color:#4ade80}.error{background:#7f1d1d;padding:12px;border-radius:8px;margin:12px 0}
    .settings{flex-wrap:wrap}.settings label{display:grid;gap:5px}.target{margin:8px 0;flex-wrap:wrap}.target select{min-width:220px}.modal{position:fixed;inset:0;background:#0009;display:grid;place-items:center;z-index:1000}
    .dialog{background:#111827;border:1px solid #334155;border-radius:14px;padding:22px;width:min(520px,92vw);display:grid;gap:12px}.dialog label{display:grid;gap:6px}
  `]
})
export class GuildAIComponent implements OnInit {
  guildId = ''; tab: 'providers'|'routes' = 'providers'; providers: Provider[] = []; routes: AiRoute[] = [];
  editing = false; error = ''; newCapability = 'translation';
  capabilities = ['translation','recognition','generation','analysis','moderation','embeddings'];
  providerTypes = ['openai','groq','gemini','anthropic','xai','openai_compatible','deepl','google_translate','libretranslate'];
  form: any = {};
  constructor(private http: HttpClient, private route: ActivatedRoute) {}
  ngOnInit(){ this.guildId=this.route.snapshot.paramMap.get('guildId')||''; this.reload(); }
  get api(){ return `/api/v1/discord/guilds/${this.guildId}/ai`; }
  reload(){ this.error=''; this.http.get<Provider[]>(`${this.api}/providers`).subscribe({next:x=>this.providers=x,error:e=>this.fail(e)});
    this.http.get<AiRoute[]>(`${this.api}/routes`).subscribe({next:x=>this.routes=x,error:e=>this.fail(e)}); }
  fail(e:any){ this.error=e?.error?.detail || e?.message || 'Request failed'; }
  openProvider(p?:Provider){ this.form=p?{...p,api_key:''}:{name:'',provider_type:'openai',api_key:'',enabled:true,priority:100,timeout_seconds:30,max_retries:1,capabilities:[],settings:{}}; this.editing=true; }
  saveProvider(){ const body={...this.form}; const id=body.id; delete body.id; delete body.guild_id; delete body.key_hint; delete body.last_health_status; delete body.last_health_latency_ms; delete body.last_error; delete body.created_at; delete body.updated_at; if(!body.api_key) delete body.api_key;
    const req=id?this.http.patch(`${this.api}/providers/${id}`,body):this.http.post(`${this.api}/providers`,body); req.subscribe({next:()=>{this.editing=false;this.reload()},error:e=>this.fail(e)}); }
  test(p:Provider){ this.http.post(`${this.api}/providers/${p.id}/test`,{}).subscribe({next:()=>this.reload(),error:e=>this.fail(e)}); }
  remove(p:Provider){ if(confirm(`Delete ${p.name}?`)) this.http.delete(`${this.api}/providers/${p.id}`).subscribe({next:()=>this.reload(),error:e=>this.fail(e)}); }
  createRoute(){ let r=this.routes.find(x=>x.capability===this.newCapability); if(!r){r={capability:this.newCapability,enabled:true,max_total_attempts:6,failure_threshold:3,cooldown_seconds:120,configuration:{},targets:[]};this.routes.push(r);} this.addTarget(r); }
  addTarget(r:AiRoute){ if(!this.providers.length)return; r.targets.push({provider_id:this.providers[0].id,position:r.targets.length+1,retries:0,enabled:true,configuration:{}}); }
  move(r:AiRoute,i:number,d:number){const j=i+d;if(j<0||j>=r.targets.length)return;[r.targets[i],r.targets[j]]=[r.targets[j],r.targets[i]];r.targets.forEach((x,k)=>x.position=k+1);}
  saveRoute(r:AiRoute){r.targets.forEach((x,k)=>x.position=k+1);this.http.put(`${this.api}/routes/${r.capability}`,r).subscribe({next:()=>this.reload(),error:e=>this.fail(e)});}
}
