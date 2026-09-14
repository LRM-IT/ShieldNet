import {CommonModule} from '@angular/common';
import {Component, OnInit, inject, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {HttpClient} from '@angular/common/http';
import {ShellComponent} from '../shared/shell.component';

type Marker={x:number;y:number;width:number;height:number;fontSize:number;color:string;align:string};

@Component({
 selector:'sn-voting-templates',standalone:true,imports:[CommonModule,FormsModule,ShellComponent],
 template:`<sn-shell title="Voting templates"><main class="page">
  <header><small>SUPERADMIN · VOTING</small><h2>Result template library</h2><p>Upload an image and mark where the poll topic and option scores appear.</p></header>
  @if(error()){<p class="error">{{error()}}</p>} @if(success()){<p class="success">{{success()}}</p>}
  <section class="panel">
   <div class="row"><h3>{{editingId?'Edit template':'Upload template'}}</h3><button *ngIf="editingId" (click)="reset()">New template</button></div>
   <div class="fields"><label>Name<input [(ngModel)]="name" maxlength="180"></label>
   <label *ngIf="!editingId">Image (PNG, JPEG, WebP)<input type="file" accept="image/png,image/jpeg,image/webp" (change)="chooseFile($event)"></label></div>
   <div class="editor" *ngIf="previewUrl">
    <div><div class="toolbar"><button [class.active]="active==='title'" (click)="active='title'">Mark topic</button><button [class.active]="active==='score'" (click)="active='score'">Mark scores</button></div>
     <div class="canvas" (click)="place($event)"><img [src]="previewUrl" alt="Template background">
      <div class="marker title" [ngStyle]="box(title)">TOPIC</div><div class="marker score" [ngStyle]="box(score)">SCORES</div></div>
     <small>Click the image to position the selected area. Adjust its size and text below.</small></div>
    <div class="marker-form" *ngIf="current() as marker">
     <h4>{{active==='title'?'Topic area':'Scores area'}}</h4>
     <label>Width (px)<input type="number" min="20" [max]="imageWidth" [(ngModel)]="marker.width"></label>
     <label>Height (px)<input type="number" min="20" [max]="imageHeight" [(ngModel)]="marker.height"></label>
     <label>Font size (px)<input type="number" min="12" max="160" [(ngModel)]="marker.fontSize"></label>
     <label>Text color<input type="color" [(ngModel)]="marker.color"></label>
     <label>Alignment<select [(ngModel)]="marker.align"><option value="left">Left</option><option value="center">Center</option><option value="right">Right</option></select></label>
    </div>
   </div>
   <button class="primary" (click)="save()" [disabled]="saving||!previewUrl||!name.trim()">{{saving?'Saving…':'Save template'}}</button>
  </section>
  <section class="panel"><h3>Available templates</h3><div class="templates">
   <article *ngFor="let item of items()"><img [src]="imageUrl(item)" [alt]="item.name">
    <div><strong>{{item.name}}</strong><small>{{item.canvas_width}} × {{item.canvas_height}} · {{item.is_active?'Active':'Inactive'}} {{item.is_default?'· Default':''}}</small></div>
    <div class="buttons"><button (click)="edit(item)">Edit markers</button><button (click)="setDefault(item)" [disabled]="item.is_default">Make default</button><button (click)="toggle(item)">{{item.is_active?'Disable':'Enable'}}</button></div>
   </article></div></section>
 </main></sn-shell>`,
 styles:[`.page{display:grid;gap:1rem}.panel{border:1px solid var(--line);background:var(--surface-1);border-radius:16px;padding:1rem;display:grid;gap:1rem}h2,h3,h4,p{margin:0}p,small{color:var(--muted)}small{display:block}.row,.toolbar,.buttons{display:flex;align-items:center;justify-content:space-between;gap:.5rem}.fields{display:grid;grid-template-columns:1fr 1fr;gap:1rem}label{display:grid;gap:.3rem;color:var(--muted)}input,select,button{font:inherit;color:var(--text);background:var(--surface-2);border:1px solid var(--line);border-radius:9px;padding:.6rem}button{cursor:pointer}.primary,.active{background:var(--primary);color:#03130e}.editor{display:grid;grid-template-columns:minmax(0,3fr) minmax(180px,1fr);gap:1rem}.canvas{position:relative;display:inline-block;max-width:100%;margin:.7rem 0;cursor:crosshair}.canvas img{display:block;max-width:100%;max-height:650px}.marker{position:absolute;border:2px solid;overflow:hidden;pointer-events:none;font-weight:bold}.title{border-color:#35e2b2;color:#35e2b2}.score{border-color:#ffcd70;color:#ffcd70}.marker-form{display:grid;gap:.6rem;align-content:start}.templates{display:grid;gap:.7rem}.templates article{display:flex;align-items:center;gap:1rem;border:1px solid var(--line);border-radius:10px;padding:.6rem}.templates img{width:110px;height:70px;object-fit:contain}.templates article div:nth-child(2){flex:1}.error{color:#ff8290}.success{color:var(--success)}@media(max-width:800px){.editor,.fields{grid-template-columns:1fr}.templates article{flex-wrap:wrap}}`]
})
export class VotingTemplatesComponent implements OnInit{
 private http=inject(HttpClient);items=signal<any[]>([]);error=signal('');success=signal('');imageUrls:Record<string,string>={};
 name='';file:File|null=null;previewUrl='';editingId='';saving=false;active:'title'|'score'='title';imageWidth=0;imageHeight=0;
 title:Marker={x:50,y:50,width:600,height:100,fontSize:52,color:'#ffffff',align:'left'};
 score:Marker={x:50,y:180,width:600,height:420,fontSize:30,color:'#ffffff',align:'left'};
 ngOnInit(){this.load()}
 load(){this.http.get<any>('/api/v1/platform/voting-templates').subscribe({next:r=>{this.items.set(r.items||[]);for(const item of r.items||[])this.loadImage(item.id)},error:e=>this.error.set(e?.error?.detail||'Unable to load templates.')})}
 loadImage(id:string){if(this.imageUrls[id])return;this.http.get(`/api/v1/platform/voting-templates/${id}/image`,{responseType:'blob'}).subscribe({next:blob=>this.imageUrls[id]=URL.createObjectURL(blob)})}
 imageUrl(item:any){return this.imageUrls[item.id]||''}
 chooseFile(event:Event){const file=(event.target as HTMLInputElement).files?.[0];if(!file)return;this.file=file;this.previewUrl=URL.createObjectURL(file);const img=new Image();img.onload=()=>{this.imageWidth=img.width;this.imageHeight=img.height;this.title={x:Math.round(img.width*.06),y:Math.round(img.height*.06),width:Math.round(img.width*.88),height:Math.round(img.height*.15),fontSize:Math.max(24,Math.round(img.width/25)),color:'#ffffff',align:'left'};this.score={x:Math.round(img.width*.06),y:Math.round(img.height*.28),width:Math.round(img.width*.88),height:Math.round(img.height*.62),fontSize:Math.max(18,Math.round(img.width/38)),color:'#ffffff',align:'left'}};img.src=this.previewUrl}
 current(){return this.active==='title'?this.title:this.score}
 box(marker:Marker){const w=this.imageWidth||1,h=this.imageHeight||1;return {left:`${marker.x/w*100}%`,top:`${marker.y/h*100}%`,width:`${marker.width/w*100}%`,height:`${marker.height/h*100}%`}}
 place(event:MouseEvent){const img=(event.currentTarget as HTMLElement).querySelector('img')!;const rect=img.getBoundingClientRect();const marker=this.current();marker.x=Math.max(0,Math.min(this.imageWidth-marker.width,Math.round((event.clientX-rect.left)/rect.width*this.imageWidth)));marker.y=Math.max(0,Math.min(this.imageHeight-marker.height,Math.round((event.clientY-rect.top)/rect.height*this.imageHeight)))}
 valid(){return [this.title,this.score].every(m=>m.x>=0&&m.y>=0&&m.width>=20&&m.height>=20&&m.x+m.width<=this.imageWidth&&m.y+m.height<=this.imageHeight)}
 save(){if(!this.valid()){this.error.set('Both text areas must fit inside the image.');return}this.saving=true;this.error.set('');let request;
  if(this.editingId){request=this.http.put<any>(`/api/v1/platform/voting-templates/${this.editingId}`,{name:this.name,title:this.title,score:this.score})}
  else{if(!this.file)return;const data=new FormData();data.append('name',this.name);data.append('title_json',JSON.stringify(this.title));data.append('score_json',JSON.stringify(this.score));data.append('file',this.file);request=this.http.post<any>('/api/v1/platform/voting-templates',data)}
  request.subscribe({next:()=>{this.saving=false;this.success.set('Template saved.');this.reset();this.load()},error:e=>{this.saving=false;this.error.set(e?.error?.detail||'Unable to save template.')}})}
 edit(item:any){this.editingId=item.id;this.name=item.name;this.file=null;this.previewUrl=this.imageUrl(item);this.imageWidth=item.canvas_width;this.imageHeight=item.canvas_height;this.title={...item.manifest.layers[0]};this.score={...item.manifest.layers[1]};window.scrollTo({top:0,behavior:'smooth'})}
 reset(){if(this.file&&this.previewUrl)URL.revokeObjectURL(this.previewUrl);this.editingId='';this.file=null;this.previewUrl='';this.name=''}
 setDefault(item:any){this.http.put(`/api/v1/platform/voting-templates/${item.id}`,{is_default:true,is_active:true}).subscribe({next:()=>this.load(),error:e=>this.error.set(e?.error?.detail||'Unable to set default.')})}
 toggle(item:any){this.http.put(`/api/v1/platform/voting-templates/${item.id}`,{is_active:!item.is_active}).subscribe({next:()=>this.load(),error:e=>this.error.set(e?.error?.detail||'Unable to update template.')})}
}
