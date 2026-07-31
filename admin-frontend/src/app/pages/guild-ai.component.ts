import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ShellComponent } from '../shared/shell.component';

type Provider = {
  id: string; name: string; provider_type: string; api_base_url?: string;
  key_hint?: string; default_model?: string; enabled: boolean; priority: number;
  timeout_seconds: number; max_retries: number; capabilities: string[];
  last_health_status?: string; last_health_latency_ms?: number; last_error?: string;
};
type RouteTarget = {
  id?: string; provider_id: string; position: number; model?: string;
  timeout_seconds?: number; retries: number; enabled: boolean; configuration: any;
};
type AiRoute = {
  id?: string; guild_id?: string; capability: string; enabled: boolean;
  max_total_attempts: number; failure_threshold: number; cooldown_seconds: number;
  configuration: any; targets: RouteTarget[];
};

@Component({
  selector: 'app-guild-ai',
  standalone: true,
  imports: [CommonModule, FormsModule, ShellComponent],
  template: `
  <sn-shell title="AI Center">
    <div class="ai-center">
      <section class="hero panel">
        <div>
          <span class="eyebrow">SERVER AI CONTROL PLANE</span>
          <h2>AI Center</h2>
          <p>Provider credentials, capability routes and automatic failover for this Discord server.</p>
        </div>
        <button class="btn primary" (click)="openProvider()">＋ Add provider</button>
      </section>

      <div *ngIf="error" class="notice error">{{ error }}</div>

      <section class="stats">
        <article class="panel stat"><span>Providers</span><strong>{{ providers.length }}</strong></article>
        <article class="panel stat"><span>Healthy</span><strong>{{ healthyCount }}</strong></article>
        <article class="panel stat"><span>Routes</span><strong>{{ routes.length }}</strong></article>
        <article class="panel stat"><span>Enabled routes</span><strong>{{ enabledRouteCount }}</strong></article>
      </section>

      <nav class="tabs panel">
        <button [class.active]="tab==='providers'" (click)="tab='providers'">
          <span>◈</span><b>Providers</b><small>API keys and models</small>
        </button>
        <button [class.active]="tab==='routes'" (click)="tab='routes'">
          <span>⇄</span><b>Fault-tolerance routes</b><small>Drag providers into priority order</small>
        </button>
      </nav>

      <section *ngIf="tab==='providers'" class="providers-grid">
        <article *ngFor="let p of providers" class="provider-card panel" [class.disabled]="!p.enabled">
          <header>
            <div class="provider-title">
              <span class="provider-logo">{{ initials(p.name) }}</span>
              <div><h3>{{ p.name }}</h3><p>{{ p.provider_type }} · {{ p.default_model || 'No default model' }}</p></div>
            </div>
            <span class="health" [class.ok]="p.last_health_status==='connected'" [class.bad]="p.last_health_status==='error'">
              {{ p.last_health_status || 'not tested' }}
            </span>
          </header>
          <div class="provider-meta">
            <span>Key {{ p.key_hint || '—' }}</span>
            <span>Priority {{ p.priority }}</span>
            <span>Timeout {{ p.timeout_seconds }}s</span>
          </div>
          <div *ngIf="p.last_error" class="provider-error">{{ p.last_error }}</div>
          <footer>
            <button class="btn secondary" (click)="test(p)">Test</button>
            <button class="btn secondary" (click)="openProvider(p)">Edit</button>
            <button class="btn danger" (click)="remove(p)">Delete</button>
          </footer>
        </article>

        <article *ngIf="!providers.length" class="empty panel">
          <div class="empty-icon">AI</div>
          <h3>No provider connections</h3>
          <p>Add OpenAI, Groq, Gemini, Anthropic, DeepL or another compatible provider.</p>
          <button class="btn primary" (click)="openProvider()">Add first provider</button>
        </article>
      </section>

      <section *ngIf="tab==='routes'" class="routes-layout">
        <aside class="route-sidebar panel">
          <span class="eyebrow">CAPABILITY ROUTES</span>
          <h3>AI operations</h3>
          <button *ngFor="let c of capabilities"
                  [class.active]="selectedCapability===c"
                  (click)="selectCapability(c)">
            <span>{{ capabilityIcon(c) }}</span>
            <div><b>{{ capabilityLabel(c) }}</b><small>{{ routeFor(c)?.targets?.length || 0 }} providers</small></div>
          </button>
        </aside>

        <main class="route-workspace panel" *ngIf="activeRoute as r">
          <header class="route-header">
            <div>
              <span class="eyebrow">{{ r.capability.toUpperCase() }}</span>
              <h3>{{ capabilityLabel(r.capability) }} route</h3>
              <p>Drag cards to change provider priority. The gateway moves downward automatically when a provider fails.</p>
            </div>
            <label class="switch"><input type="checkbox" [(ngModel)]="r.enabled"><i></i><span>Enabled</span></label>
          </header>

          <section class="route-settings">
            <label><span>Maximum attempts</span><input type="number" min="1" [(ngModel)]="r.max_total_attempts"></label>
            <label><span>Open circuit after</span><input type="number" min="1" [(ngModel)]="r.failure_threshold"></label>
            <label><span>Cooldown seconds</span><input type="number" min="10" [(ngModel)]="r.cooldown_seconds"></label>
          </section>

          <div class="flow-head">
            <div><span class="eyebrow">FAILOVER CHAIN</span><h4>Provider priority</h4></div>
            <button class="btn secondary" (click)="addTarget(r)" [disabled]="!providers.length">＋ Add provider</button>
          </div>

          <div class="flow">
            <article *ngFor="let t of r.targets; let i=index"
                     class="target-card"
                     draggable="true"
                     [class.dragging]="dragIndex===i"
                     (dragstart)="dragStart(i)"
                     (dragover)="dragOver($event, i)"
                     (drop)="dropTarget(r, i)"
                     (dragend)="dragIndex=null">
              <div class="drag-handle" title="Drag to reorder">⋮⋮</div>
              <div class="step"><small>{{ i===0 ? 'PRIMARY' : 'FALLBACK' }}</small><strong>{{ i+1 }}</strong></div>
              <div class="target-body">
                <label><span>Provider</span>
                  <select [(ngModel)]="t.provider_id">
                    <option *ngFor="let p of providers" [value]="p.id">{{ p.name }} · {{ p.provider_type }}</option>
                  </select>
                </label>
                <label><span>Model override</span><input [(ngModel)]="t.model" placeholder="Use provider default"></label>
                <label><span>Timeout</span><input type="number" [(ngModel)]="t.timeout_seconds" placeholder="Default"></label>
                <label><span>Retries</span><input type="number" min="0" [(ngModel)]="t.retries"></label>
              </div>
              <label class="mini-switch"><input type="checkbox" [(ngModel)]="t.enabled"><i></i></label>
              <button class="remove" (click)="r.targets.splice(i,1)" title="Remove">×</button>
            </article>

            <div *ngIf="!r.targets.length" class="drop-empty">
              <span>⇣</span><h4>No providers in this route</h4>
              <p>Add a provider to create the primary node. Additional providers become fallbacks.</p>
              <button class="btn primary" (click)="addTarget(r)" [disabled]="!providers.length">Add provider</button>
            </div>
          </div>

          <footer class="route-footer">
            <div class="flow-summary">
              <span *ngFor="let t of r.targets; let i=index">
                <b>{{ providerName(t.provider_id) }}</b><i *ngIf="i<r.targets.length-1">→</i>
              </span>
            </div>
            <button class="btn primary" (click)="saveRoute(r)">Save route</button>
          </footer>
        </main>
      </section>

      <div class="modal" *ngIf="editing">
        <form class="dialog panel" (ngSubmit)="saveProvider()">
          <header><div><span class="eyebrow">PROVIDER CONNECTION</span><h2>{{ form.id ? 'Edit provider' : 'Add provider' }}</h2></div><button type="button" class="close" (click)="editing=false">×</button></header>
          <div class="form-grid">
            <label><span>Name</span><input required [(ngModel)]="form.name" name="name"></label>
            <label><span>Provider</span><select [(ngModel)]="form.provider_type" name="type"><option *ngFor="let p of providerTypes" [value]="p">{{p}}</option></select></label>
            <label class="full"><span>API key</span><input [required]="!form.id" type="password" [(ngModel)]="form.api_key" name="key" placeholder="Leave empty to keep current key"></label>
            <label class="full"><span>API base URL</span><input [(ngModel)]="form.api_base_url" name="url"></label>
            <label><span>Default model</span><input [(ngModel)]="form.default_model" name="model"></label>
            <label><span>Priority</span><input type="number" [(ngModel)]="form.priority" name="priority"></label>
            <label><span>Timeout seconds</span><input type="number" [(ngModel)]="form.timeout_seconds" name="timeout"></label>
            <label><span>Retries</span><input type="number" [(ngModel)]="form.max_retries" name="retries"></label>
          </div>
          <label class="switch"><input type="checkbox" [(ngModel)]="form.enabled" name="enabled"><i></i><span>Enabled</span></label>
          <footer><button class="btn secondary" type="button" (click)="editing=false">Cancel</button><button class="btn primary" type="submit">Save provider</button></footer>
        </form>
      </div>
    </div>
  </sn-shell>`,
  styles: [`
    :host{display:block;min-width:0}.ai-center{display:grid;gap:1rem;min-width:0}.panel{background:linear-gradient(145deg,var(--panel-glow),transparent 35%),var(--surface-1);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}
    .hero{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:1.2rem}.hero h2{margin:.3rem 0;font-size:1.8rem}.hero p,.route-header p,.empty p,.drop-empty p{margin:.25rem 0;color:var(--muted);font-size:.72rem;line-height:1.5}.eyebrow{color:var(--primary);font-size:.56rem;font-weight:900;letter-spacing:.16em}
    .btn{min-height:40px;padding:.62rem .9rem;border-radius:10px;border:1px solid var(--line);font-size:.68rem;font-weight:850;cursor:pointer}.btn.primary{background:var(--primary);border-color:var(--primary);color:#041611}.btn.secondary{background:var(--surface-2);color:var(--text)}.btn.danger{background:rgba(255,92,114,.08);border-color:rgba(255,92,114,.25);color:#ff9aa8}.btn:disabled{opacity:.45;cursor:not-allowed}
    .notice{padding:.8rem 1rem;border-radius:12px}.notice.error{color:#ff9aa8;background:rgba(255,92,114,.08);border:1px solid rgba(255,92,114,.25)}
    .stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem}.stat{display:flex;justify-content:space-between;align-items:center;padding:1rem}.stat span{color:var(--muted);font-size:.65rem}.stat strong{font-size:1.35rem}
    .tabs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.55rem;padding:.5rem}.tabs button{display:grid;grid-template-columns:42px 1fr;grid-template-rows:auto auto;gap:.1rem .65rem;align-items:center;padding:.75rem;border:1px solid transparent;border-radius:12px;background:transparent;color:var(--muted);text-align:left;cursor:pointer}.tabs button>span{grid-row:1/3;width:42px;height:42px;display:grid;place-items:center;border:1px solid var(--line);border-radius:10px}.tabs button b{color:var(--text)}.tabs button small{font-size:.6rem}.tabs button.active{background:var(--primary-soft);border-color:var(--line-strong)}.tabs button.active>span{color:var(--primary)}
    .providers-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:.8rem}.provider-card{padding:1rem;display:grid;gap:1rem}.provider-card.disabled{opacity:.6}.provider-card header,.provider-card footer,.provider-title,.provider-meta,.route-header,.route-footer,.flow-head{display:flex;align-items:center;gap:.7rem}.provider-card header,.route-header,.route-footer,.flow-head{justify-content:space-between}.provider-logo{width:42px;height:42px;display:grid;place-items:center;border-radius:11px;color:var(--primary);background:var(--primary-soft);border:1px solid var(--line-strong);font-weight:900}.provider-title h3{margin:0}.provider-title p{margin:.2rem 0 0;color:var(--muted);font-size:.62rem}.health{padding:.3rem .55rem;border-radius:999px;background:var(--surface-2);font-size:.58rem}.health.ok{color:var(--success)}.health.bad{color:#ff9aa8}.provider-meta{flex-wrap:wrap}.provider-meta span{padding:.35rem .5rem;border-radius:8px;background:var(--surface-2);color:var(--muted);font-size:.58rem}.provider-error{color:#ff9aa8;font-size:.62rem}.empty{grid-column:1/-1;padding:3rem;text-align:center}.empty-icon{width:64px;height:64px;margin:auto;display:grid;place-items:center;border-radius:18px;color:var(--primary);background:var(--primary-soft);font-weight:900}
    .routes-layout{display:grid;grid-template-columns:260px minmax(0,1fr);gap:1rem;align-items:start}.route-sidebar{display:grid;gap:.45rem;padding:1rem;position:sticky;top:100px}.route-sidebar h3{margin:.25rem 0 .8rem}.route-sidebar button{display:grid;grid-template-columns:36px 1fr;gap:.65rem;align-items:center;padding:.7rem;border:1px solid transparent;border-radius:10px;background:transparent;color:var(--muted);text-align:left;cursor:pointer}.route-sidebar button>span{width:36px;height:36px;display:grid;place-items:center;border:1px solid var(--line);border-radius:9px}.route-sidebar button div{display:grid;gap:.12rem}.route-sidebar button b{color:var(--text);font-size:.7rem}.route-sidebar button small{font-size:.56rem}.route-sidebar button.active{background:var(--primary-soft);border-color:var(--line-strong)}.route-sidebar button.active>span{color:var(--primary)}
    .route-workspace{padding:1rem;display:grid;gap:1rem;min-width:0}.route-header h3{margin:.25rem 0}.route-settings{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem;padding:1rem;border:1px solid var(--line);border-radius:12px;background:rgba(0,0,0,.12)}label{display:grid;gap:.35rem;color:var(--muted);font-size:.61rem;font-weight:750}input,select{width:100%;min-width:0;height:42px;padding:.65rem .7rem;border:1px solid var(--line);border-radius:10px;background:var(--surface-2);color:var(--text);outline:none}input:focus,select:focus{border-color:var(--primary);box-shadow:0 0 0 3px var(--primary-soft)}
    .flow-head h4{margin:.2rem 0}.flow{display:grid;gap:.65rem}.target-card{display:grid;grid-template-columns:28px 70px minmax(0,1fr) auto auto;gap:.7rem;align-items:center;padding:.75rem;border:1px solid var(--line);border-radius:14px;background:linear-gradient(90deg,rgba(53,226,178,.035),transparent),var(--surface-2);transition:.15s}.target-card:hover{border-color:var(--line-strong);transform:translateY(-1px)}.target-card.dragging{opacity:.4;border-style:dashed}.drag-handle{color:var(--muted);font-size:1.1rem;cursor:grab;user-select:none}.step{display:grid;justify-items:center;gap:.2rem;padding:.45rem;border-right:1px solid var(--line)}.step small{font-size:.48rem;color:var(--primary);letter-spacing:.1em}.step strong{font-size:1.15rem}.target-body{display:grid;grid-template-columns:1.3fr 1fr 110px 85px;gap:.6rem;min-width:0}.remove,.close{width:34px;height:34px;border-radius:9px;border:1px solid rgba(255,92,114,.22);background:rgba(255,92,114,.08);color:#ff9aa8;cursor:pointer}.drop-empty{padding:2.5rem;border:1px dashed var(--line-strong);border-radius:14px;text-align:center}.drop-empty>span{font-size:2rem;color:var(--primary)}.flow-summary{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap}.flow-summary span{display:flex;align-items:center;gap:.45rem}.flow-summary b{padding:.35rem .5rem;border-radius:8px;background:var(--surface-2);font-size:.58rem}.flow-summary i{color:var(--primary)}
    .switch,.mini-switch{display:flex;grid-auto-flow:column;align-items:center;justify-content:start;gap:.5rem;cursor:pointer}.switch input,.mini-switch input{position:absolute;opacity:0;width:1px;height:1px}.switch i,.mini-switch i{position:relative;width:40px;height:22px;border-radius:99px;background:var(--surface-3);border:1px solid var(--line)}.switch i:after,.mini-switch i:after{content:'';position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:var(--muted);transition:.16s}.switch input:checked+i,.mini-switch input:checked+i{background:var(--primary-soft);border-color:var(--line-strong)}.switch input:checked+i:after,.mini-switch input:checked+i:after{left:21px;background:var(--primary)}
    .modal{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:1rem;background:rgba(1,4,8,.76);backdrop-filter:blur(10px)}.dialog{width:min(680px,96vw);padding:1rem;display:grid;gap:1rem}.dialog header,.dialog footer{display:flex;align-items:center;justify-content:space-between}.dialog h2{margin:.25rem 0}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem}.form-grid .full{grid-column:1/-1}
    @media(max-width:1000px){.routes-layout{grid-template-columns:1fr}.route-sidebar{position:static;grid-template-columns:repeat(3,minmax(0,1fr))}.route-sidebar>.eyebrow,.route-sidebar>h3{grid-column:1/-1}.target-body{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:700px){.hero,.route-header,.route-footer,.flow-head{align-items:flex-start;flex-direction:column}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.tabs{grid-template-columns:1fr}.route-sidebar{grid-template-columns:repeat(2,minmax(0,1fr))}.route-settings,.form-grid{grid-template-columns:1fr}.form-grid .full{grid-column:auto}.target-card{grid-template-columns:24px 50px minmax(0,1fr) auto}.target-body{grid-template-columns:1fr}.mini-switch{display:none}.remove{grid-column:4}}
  `]
})
export class GuildAIComponent implements OnInit {
  guildId=''; tab:'providers'|'routes'='providers'; providers:Provider[]=[]; routes:AiRoute[]=[];
  editing=false; error=''; selectedCapability='translation'; dragIndex:number|null=null;
  capabilities=['translation','recognition','generation','analysis','moderation','embeddings'];
  providerTypes=['openai','groq','gemini','anthropic','xai','openai_compatible','deepl','google_translate','libretranslate'];
  form:any={};

  constructor(private http:HttpClient, private route:ActivatedRoute){}
  ngOnInit(){this.guildId=this.route.snapshot.paramMap.get('guildId')||'';this.reload();}
  get api(){return `/api/v1/discord/guilds/${this.guildId}/ai`;}
  get healthyCount(){return this.providers.filter(x=>x.last_health_status==='connected').length;}
  get enabledRouteCount(){return this.routes.filter(x=>x.enabled).length;}
  get activeRoute(){return this.ensureRoute(this.selectedCapability);}

  reload(){
    this.error='';
    this.http.get<Provider[]>(`${this.api}/providers`).subscribe({next:x=>this.providers=x,error:e=>this.fail(e)});
    this.http.get<AiRoute[]>(`${this.api}/routes`).subscribe({next:x=>this.routes=x,error:e=>this.fail(e)});
  }
  fail(e:any){this.error=e?.error?.detail||e?.message||'Request failed';}
  initials(name:string){return (name||'AI').slice(0,2).toUpperCase();}
  capabilityIcon(c:string){return ({translation:'文',recognition:'⌕',generation:'✦',analysis:'◉',moderation:'⚖',embeddings:'≋'} as any)[c]||'AI';}
  capabilityLabel(c:string){return ({translation:'Translation',recognition:'Recognition',generation:'Generation',analysis:'Analysis',moderation:'Moderation',embeddings:'Embeddings'} as any)[c]||c;}
  routeFor(c:string){return this.routes.find(x=>x.capability===c);}
  selectCapability(c:string){this.selectedCapability=c;this.ensureRoute(c);}
  ensureRoute(c:string){
    let r=this.routes.find(x=>x.capability===c);
    if(!r){r={capability:c,enabled:true,max_total_attempts:6,failure_threshold:3,cooldown_seconds:120,configuration:{},targets:[]};this.routes.push(r);}
    return r;
  }
  providerName(id:string){return this.providers.find(x=>x.id===id)?.name||'Unknown provider';}
  openProvider(p?:Provider){this.form=p?{...p,api_key:''}:{name:'',provider_type:'openai',api_key:'',enabled:true,priority:100,timeout_seconds:30,max_retries:1,capabilities:[],settings:{}};this.editing=true;}
  saveProvider(){
    const body={...this.form};const id=body.id;
    ['id','guild_id','key_hint','last_health_status','last_health_latency_ms','last_error','created_at','updated_at','consecutive_failures','circuit_open_until'].forEach(k=>delete body[k]);
    if(!body.api_key)delete body.api_key;
    const req=id?this.http.patch(`${this.api}/providers/${id}`,body):this.http.post(`${this.api}/providers`,body);
    req.subscribe({next:()=>{this.editing=false;this.reload()},error:e=>this.fail(e)});
  }
  test(p:Provider){this.http.post(`${this.api}/providers/${p.id}/test`,{}).subscribe({next:()=>this.reload(),error:e=>this.fail(e)});}
  remove(p:Provider){if(confirm(`Delete ${p.name}?`))this.http.delete(`${this.api}/providers/${p.id}`).subscribe({next:()=>this.reload(),error:e=>this.fail(e)});}
  addTarget(r:AiRoute){if(!this.providers.length)return;r.targets.push({provider_id:this.providers[0].id,position:r.targets.length+1,retries:0,enabled:true,configuration:{}});}
  dragStart(i:number){this.dragIndex=i;}
  dragOver(event:DragEvent,i:number){event.preventDefault();if(this.dragIndex===null||this.dragIndex===i)return;}
  dropTarget(r:AiRoute,i:number){
    if(this.dragIndex===null||this.dragIndex===i)return;
    const [item]=r.targets.splice(this.dragIndex,1);r.targets.splice(i,0,item);
    r.targets.forEach((x,k)=>x.position=k+1);this.dragIndex=null;
  }
  saveRoute(r:AiRoute){r.targets.forEach((x,k)=>x.position=k+1);this.http.put(`${this.api}/routes/${r.capability}`,r).subscribe({next:()=>this.reload(),error:e=>this.fail(e)});}
}
