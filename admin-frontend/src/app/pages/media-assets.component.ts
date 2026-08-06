import {CommonModule} from '@angular/common';
import {Component,OnInit,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {ShellComponent} from '../shared/shell.component';
import {MediaAssetsService} from '../core/media-assets.service';

@Component({
 selector:'sn-media-assets',standalone:true,imports:[CommonModule,FormsModule,ShellComponent],
 template:`
 <sn-shell title="Asset Library"><main class="page">
  <section class="hero panel"><div><small>PLATFORM MEDIA</small><h2>Asset Library</h2><p>Reusable backgrounds, characters, logos, frames, effects and fonts.</p></div>
   <button class="primary" (click)="open()">＋ Upload asset</button></section>
  @if(error()){<div class="error">{{error()}}</div>}
  <nav class="types panel">
   <button [class.active]="type==='all'" (click)="setType('all')">All</button>
   @for(t of types;track t){<button [class.active]="type===t" (click)="setType(t)">{{t}}</button>}
  </nav>
  <section class="gallery">
   @for(a of assets();track a.id){
    <article class="card panel">
     <div class="preview">
      @if(a.mime_type.startsWith('image/')){<img [src]="a.preview_url" [alt]="a.name">}
      @else{<div class="font-preview">Aa</div>}
      <span>{{a.asset_type}}</span>
     </div>
     <div class="body"><h3>{{a.name}}</h3><small>{{a.key}}</small>
      <p>{{a.description||'No description'}}</p>
      <div class="meta"><span>{{a.width||'—'}}×{{a.height||'—'}}</span><span>{{size(a.file_size)}}</span></div>
      <footer><button (click)="toggle(a)">{{a.is_active?'Disable':'Enable'}}</button><button class="danger" (click)="remove(a)">Delete</button></footer>
     </div>
    </article>
   }
   @if(!assets().length){<article class="empty panel">No assets in this category.</article>}
  </section>

  @if(dialog()){<div class="modal"><form class="dialog panel" (ngSubmit)="upload()">
   <header><div><small>NEW ASSET</small><h2>Upload media asset</h2></div><button type="button" (click)="dialog.set(false)">×</button></header>
   <div class="grid">
    <label>Name<input required [(ngModel)]="form.name" name="name"></label>
    <label>Key<input required [(ngModel)]="form.key" name="key"></label>
    <label>Type<select [(ngModel)]="form.asset_type" name="type">@for(t of types;track t){<option [value]="t">{{t}}</option>}</select></label>
    <label>Tags<input [(ngModel)]="form.tags" name="tags" placeholder="lastwar, blue, military"></label>
    <label class="full">Description<textarea [(ngModel)]="form.description" name="description"></textarea></label>
    <label>Asset file<input required type="file" (change)="pick($event,'file')"></label>
    <label>Preview<input type="file" accept="image/*" (change)="pick($event,'preview')"></label>
   </div>
   <footer><button type="button" (click)="dialog.set(false)">Cancel</button><button class="primary">Upload</button></footer>
  </form></div>}
 </main></sn-shell>`,
 styles:[`
 .page{display:grid;gap:1rem}.panel{background:var(--surface-1);border:1px solid var(--line);border-radius:16px}.hero{padding:1rem;display:flex;justify-content:space-between;align-items:center;gap:1rem}
 h2,h3,p{margin:0}small{color:var(--primary);letter-spacing:.12em}.hero p,.body p{color:var(--muted);margin-top:.3rem}
 button,input,textarea,select{font:inherit;border:1px solid var(--line);border-radius:9px;background:var(--surface-2);color:var(--text);padding:.7rem}.primary{background:var(--primary);color:#03130e;font-weight:850}.danger{color:#ff9aa8}
 .types{display:flex;gap:.4rem;padding:.5rem;flex-wrap:wrap}.types button{text-transform:capitalize}.types button.active{background:var(--primary-soft);border-color:var(--line-strong);color:var(--primary)}
 .gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.8rem}.card{overflow:hidden}.preview{height:200px;position:relative;background:#050b11}.preview img{width:100%;height:100%;object-fit:cover}.preview>span{position:absolute;top:.6rem;left:.6rem;background:#051019d9;border:1px solid var(--line);padding:.3rem .5rem;border-radius:99px;color:var(--primary);text-transform:uppercase;font-size:.55rem}.font-preview{height:100%;display:grid;place-items:center;font-size:4rem;color:var(--primary)}
 .body{padding:1rem;display:grid;gap:.7rem}.meta,footer,.dialog header,.dialog footer{display:flex;gap:.45rem;justify-content:space-between;align-items:center}.meta span{background:var(--surface-2);padding:.3rem .45rem;border-radius:7px;color:var(--muted);font-size:.58rem}.empty{padding:3rem;text-align:center;color:var(--muted)}
 .error{color:#ff9aa8}.modal{position:fixed;inset:0;z-index:1000;background:#000b;display:grid;place-items:center;padding:1rem}.dialog{width:min(700px,96vw);padding:1rem;display:grid;gap:1rem}.grid{display:grid;grid-template-columns:1fr 1fr;gap:.7rem}.full{grid-column:1/-1}label{display:grid;gap:.3rem;color:var(--muted);font-size:.65rem}
 @media(max-width:700px){.hero{align-items:flex-start;flex-direction:column}.grid{grid-template-columns:1fr}.full{grid-column:auto}}
 `]
})
export class MediaAssetsComponent implements OnInit{
 private api=inject(MediaAssetsService);assets=signal<any[]>([]);dialog=signal(false);error=signal('');
 type='all';types=['background','character','logo','icon','frame','effect','badge','sticker','font'];form:any={};files:any={};
 ngOnInit(){this.reload()}
 setType(t:string){this.type=t;this.reload()}
 reload(){this.api.list(this.type==='all'?undefined:this.type).subscribe({next:x=>this.assets.set(x.items||[]),error:e=>this.fail(e)})}
 fail(e:any){this.error.set(e?.error?.detail||e?.message||'Request failed')}
 open(){this.form={name:'',key:'',asset_type:'background',description:'',tags:''};this.files={};this.dialog.set(true)}
 pick(e:any,k:string){this.files[k]=e.target.files?.[0]}
 upload(){if(!this.files.file){this.error.set('Asset file is required.');return}const d=new FormData();d.append('name',this.form.name);d.append('key',this.form.key);d.append('asset_type',this.form.asset_type);d.append('description',this.form.description||'');d.append('tags_json',JSON.stringify((this.form.tags||'').split(',').map((x:string)=>x.trim()).filter(Boolean)));d.append('metadata_json','{}');d.append('file',this.files.file);if(this.files.preview)d.append('preview',this.files.preview);this.api.create(d).subscribe({next:()=>{this.dialog.set(false);this.reload()},error:e=>this.fail(e)})}
 toggle(a:any){this.api.update(a.id,{is_active:!a.is_active}).subscribe({next:()=>this.reload(),error:e=>this.fail(e)})}
 remove(a:any){if(confirm(`Delete "${a.name}"?`))this.api.remove(a.id).subscribe({next:()=>this.reload(),error:e=>this.fail(e)})}
 size(n:number){if(!n)return'0 B';if(n<1024)return`${n} B`;if(n<1048576)return`${(n/1024).toFixed(1)} KB`;return`${(n/1048576).toFixed(1)} MB`}
}
