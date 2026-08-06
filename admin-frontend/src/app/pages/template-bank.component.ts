import {CommonModule} from '@angular/common';
import {Component,OnInit,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {ShellComponent} from '../shared/shell.component';
import {TemplateBankService} from '../core/template-bank.service';

@Component({
 selector:'sn-template-bank',standalone:true,imports:[CommonModule,FormsModule,ShellComponent],
 template:`
 <sn-shell title="Template Bank"><main class="page">
  <section class="hero panel"><div><small>PLATFORM MEDIA</small><h2>Template Bank</h2><p>Global library and game-specific template catalogs.</p></div>
   <div><button (click)="openGame()">＋ Add game</button><button class="primary">＋ Upload template</button></div></section>
  @if(error()){<div class="error">{{error()}}</div>}
  <section class="settings panel"><div><small>GLOBAL QR SETTINGS</small><h3>Default QR destination</h3></div>
   <div class="grid"><label>Default QR URL<input [(ngModel)]="settings.default_qr_url"></label>
   <label>QR caption<input [(ngModel)]="settings.default_qr_caption"></label>
   <label><input type="checkbox" [(ngModel)]="settings.allow_guild_qr_override"> Allow guild override</label>
   <button class="primary" (click)="saveSettings()">Save settings</button></div></section>

  <section class="library panel">
   <nav class="libraries">
    <button [class.active]="selectedGame==='general'" (click)="selectedGame='general'">🌐 General library</button>
    @for(g of games();track g.id){<button [class.active]="selectedGame===g.id" (click)="selectedGame=g.id">🎮 {{g.name}}</button>}
   </nav>
   <div class="catalog">
    <header><div><small>CATALOG</small><h3>{{libraryTitle()}}</h3></div></header>
    <nav class="categories"><button [class.active]="category==='all'" (click)="category='all'">All</button>
      <button [class.active]="category==='voting'" (click)="category='voting'">Voting</button>
      <button [class.active]="category==='ranks'" (click)="category='ranks'">Ranks</button></nav>
    <div class="gallery">
     @for(t of filtered();track t.id){<article class="card"><img [src]="t.preview_url+'?v='+t.version"><div><h4>{{t.name}}</h4><span>{{t.category}}</span></div></article>}
     @if(!filtered().length){<div class="empty">No templates in this catalog.</div>}
    </div>
   </div>
  </section>

  @if(gameDialog()){<div class="modal"><form class="dialog panel" (ngSubmit)="createGame()">
   <h3>Add game library</h3><label>Name<input required [(ngModel)]="gameForm.name" name="name"></label>
   <label>Key<input required [(ngModel)]="gameForm.key" name="key"></label>
   <label>Description<textarea [(ngModel)]="gameForm.description" name="description"></textarea></label>
   <footer><button type="button" (click)="gameDialog.set(false)">Cancel</button><button class="primary">Create</button></footer>
  </form></div>}
 </main></sn-shell>`,
 styles:[`
 .page{display:grid;gap:1rem}.panel{background:var(--surface-1);border:1px solid var(--line);border-radius:16px;padding:1rem}.hero,.settings,.hero>div:last-child,footer{display:flex;justify-content:space-between;align-items:center;gap:.7rem}
 h2,h3,h4,p{margin:0}small{color:var(--primary);letter-spacing:.14em}.hero p{color:var(--muted);margin-top:.3rem}
 button,input,textarea{font:inherit;border:1px solid var(--line);border-radius:9px;background:var(--surface-2);color:var(--text);padding:.7rem}.primary{background:var(--primary);color:#03130e;font-weight:800}
 .grid{display:grid;grid-template-columns:1.4fr 1fr;gap:.6rem;min-width:620px}label{display:grid;gap:.3rem;color:var(--muted);font-size:.65rem}
 .library{display:grid;grid-template-columns:260px 1fr;padding:0;overflow:hidden}.libraries{padding:.7rem;border-right:1px solid var(--line);display:grid;align-content:start;gap:.4rem}.libraries button{text-align:left}.libraries button.active,.categories button.active{background:var(--primary-soft);border-color:var(--line-strong);color:var(--primary)}
 .catalog{padding:1rem;display:grid;gap:1rem}.categories{display:flex;gap:.4rem}.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:.7rem}.card{border:1px solid var(--line);border-radius:12px;overflow:hidden}.card img{width:100%;height:160px;object-fit:cover}.card div{padding:.7rem}.card span{color:var(--muted);font-size:.6rem}.empty{padding:3rem;text-align:center;color:var(--muted)}
 .error{color:#ff9aa8}.modal{position:fixed;inset:0;background:#000b;display:grid;place-items:center;z-index:1000}.dialog{width:min(520px,94vw);display:grid;gap:.7rem}
 @media(max-width:850px){.settings{align-items:flex-start;flex-direction:column}.grid{grid-template-columns:1fr;min-width:0;width:100%}.library{grid-template-columns:1fr}.libraries{border-right:0;border-bottom:1px solid var(--line);grid-auto-flow:column;overflow:auto}}
 `]
})
export class TemplateBankComponent implements OnInit{
 private api=inject(TemplateBankService);games=signal<any[]>([]);templates=signal<any[]>([]);error=signal('');
 gameDialog=signal(false);selectedGame='general';category='all';settings:any={default_qr_url:'https://discord.lrm-it.com',default_qr_caption:'Visit our website',allow_guild_qr_override:false};gameForm:any={};
 ngOnInit(){this.reload();this.api.settings().subscribe({next:x=>this.settings=x,error:e=>this.fail(e)})}
 reload(){this.api.games().subscribe({next:x=>this.games.set(x.items||[]),error:e=>this.fail(e)});this.api.templates().subscribe({next:x=>this.templates.set(x.items||[]),error:e=>this.fail(e)})}
 fail(e:any){this.error.set(e?.error?.detail||e?.message||'Request failed')}
 filtered(){return this.templates().filter(t=>(this.selectedGame==='general'?!t.game_library_id:t.game_library_id===this.selectedGame)&&(this.category==='all'||t.category===this.category))}
 libraryTitle(){if(this.selectedGame==='general')return 'General library';return this.games().find(x=>x.id===this.selectedGame)?.name||'Game library'}
 saveSettings(){this.api.saveSettings(this.settings).subscribe({next:x=>this.settings=x,error:e=>this.fail(e)})}
 openGame(){this.gameForm={name:'',key:'',description:'',sort_order:100,is_active:true};this.gameDialog.set(true)}
 createGame(){this.api.createGame(this.gameForm).subscribe({next:()=>{this.gameDialog.set(false);this.reload()},error:e=>this.fail(e)})}
}
