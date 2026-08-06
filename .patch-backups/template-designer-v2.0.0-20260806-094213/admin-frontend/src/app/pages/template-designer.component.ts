import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ShellComponent } from '../shared/shell.component';
import { TemplateDesignerService } from '../core/template-designer.service';
import { MediaVariablesService } from '../core/media-variables.service';

type LayerType = 'text'|'image'|'qr'|'progress'|'rectangle';

interface DesignerLayer {
  id:string;
  type:LayerType;
  name:string;
  x:number;
  y:number;
  width:number;
  height:number;
  rotation:number;
  opacity:number;
  zIndex:number;
  visible:boolean;
  locked:boolean;
  variable?:string;
  text?:string;
  fontSize?:number;
  fontWeight?:string;
  color?:string;
  align?:string;
  background?:string;
  borderColor?:string;
  borderWidth?:number;
  borderRadius?:number;
  assetId?:string|null;
}

@Component({
 selector:'sn-template-designer',
 standalone:true,
 imports:[CommonModule,FormsModule,ShellComponent],
 template:`
 <sn-shell title="Template Designer">
  <main class="page">
   <section class="toolbar panel">
    <div class="title">
      <small>MEDIA PLATFORM</small>
      <h2>Template Designer</h2>
      <p>Drag layers, bind variables and save the layout into the template manifest.</p>
    </div>

    <div class="template-picker">
      <label>Template
        <select [(ngModel)]="selectedTemplateId" (ngModelChange)="selectTemplate($event)">
          <option value="">Select template</option>
          @for(t of templates();track t.id){
            <option [value]="t.id">{{t.name}} · {{t.category}}</option>
          }
        </select>
      </label>
      <button (click)="undo()" [disabled]="!history.length">Undo</button>
      <button class="primary" (click)="save()" [disabled]="!selectedTemplateId">Save layout</button>
    </div>
   </section>

   @if(error()){<div class="notice error">{{error()}}</div>}
   @if(success()){<div class="notice success">{{success()}}</div>}

   <section class="designer">
    <aside class="left panel">
      <div class="section-title"><small>LAYERS</small><button (click)="addLayer('text')">＋</button></div>

      <div class="add-grid">
        <button (click)="addLayer('text')">T Text</button>
        <button (click)="addLayer('image')">▧ Image</button>
        <button (click)="addLayer('qr')">▦ QR</button>
        <button (click)="addLayer('progress')">▰ Progress</button>
        <button (click)="addLayer('rectangle')">□ Shape</button>
      </div>

      <div class="layers">
        @for(layer of sortedLayers();track layer.id){
          <article
            [class.active]="selectedLayerId===layer.id"
            (click)="selectLayer(layer.id)"
          >
            <span class="drag">⋮⋮</span>
            <div>
              <b>{{layer.name}}</b>
              <small>{{layer.type}} · z{{layer.zIndex}}</small>
            </div>
            <button (click)="toggleVisible(layer);$event.stopPropagation()">
              {{layer.visible?'◉':'○'}}
            </button>
          </article>
        }
      </div>
    </aside>

    <section class="workspace panel">
      <div class="workspace-head">
        <div>
          <small>CANVAS</small>
          <b>{{canvas.width}} × {{canvas.height}}</b>
        </div>
        <div class="zoom">
          <button (click)="setZoom(zoom-0.1)">−</button>
          <span>{{(zoom*100).toFixed(0)}}%</span>
          <button (click)="setZoom(zoom+0.1)">＋</button>
        </div>
      </div>

      <div class="canvas-scroll">
        <div
          class="canvas-frame"
          [style.width.px]="canvas.width*zoom"
          [style.height.px]="canvas.height*zoom"
        >
          <div
            class="canvas"
            [style.width.px]="canvas.width"
            [style.height.px]="canvas.height"
            [style.transform]="'scale('+zoom+')'"
            [style.background-image]="backgroundUrl ? 'url('+backgroundUrl+')' : ''"
            (mousedown)="clearSelection($event)"
          >
            @for(layer of layers;track layer.id){
              @if(layer.visible){
                <div
                  class="canvas-layer"
                  [class.selected]="selectedLayerId===layer.id"
                  [class.locked]="layer.locked"
                  [style.left.px]="layer.x"
                  [style.top.px]="layer.y"
                  [style.width.px]="layer.width"
                  [style.height.px]="layer.height"
                  [style.opacity]="layer.opacity"
                  [style.transform]="'rotate('+layer.rotation+'deg)'"
                  [style.z-index]="layer.zIndex"
                  (mousedown)="startDrag($event,layer)"
                >
                  @switch(layer.type){
                    @case('text'){
                      <div class="text-layer"
                        [style.font-size.px]="layer.fontSize"
                        [style.font-weight]="layer.fontWeight"
                        [style.color]="layer.color"
                        [style.text-align]="layer.align">
                        {{previewText(layer)}}
                      </div>
                    }
                    @case('image'){
                      @if(assetUrl(layer.assetId)){
                        <img [src]="assetUrl(layer.assetId)" draggable="false">
                      } @else {
                        <div class="placeholder">IMAGE</div>
                      }
                    }
                    @case('qr'){
                      <div class="qr-placeholder">▦<small>{{layer.variable||'{{QR_URL}}'}}</small></div>
                    }
                    @case('progress'){
                      <div class="progress">
                        <div [style.width.%]="72"></div>
                      </div>
                    }
                    @case('rectangle'){
                      <div class="shape"
                        [style.background]="layer.background"
                        [style.border-color]="layer.borderColor"
                        [style.border-width.px]="layer.borderWidth"
                        [style.border-radius.px]="layer.borderRadius">
                      </div>
                    }
                  }
                  @if(selectedLayerId===layer.id&&!layer.locked){
                    <button class="resize" (mousedown)="startResize($event,layer)">↘</button>
                  }
                </div>
              }
            }
          </div>
        </div>
      </div>
    </section>

    <aside class="right panel">
      @if(selectedLayer();as layer){
        <div class="section-title">
          <div><small>PROPERTIES</small><h3>{{layer.name}}</h3></div>
          <button class="danger" (click)="deleteLayer(layer)">×</button>
        </div>

        <div class="properties">
          <label>Name<input [(ngModel)]="layer.name" (change)="snapshot()"></label>

          <div class="two">
            <label>X<input type="number" [(ngModel)]="layer.x" (change)="snapshot()"></label>
            <label>Y<input type="number" [(ngModel)]="layer.y" (change)="snapshot()"></label>
          </div>

          <div class="two">
            <label>Width<input type="number" min="1" [(ngModel)]="layer.width" (change)="snapshot()"></label>
            <label>Height<input type="number" min="1" [(ngModel)]="layer.height" (change)="snapshot()"></label>
          </div>

          <div class="two">
            <label>Rotation<input type="number" [(ngModel)]="layer.rotation" (change)="snapshot()"></label>
            <label>Opacity<input type="number" min="0" max="1" step=".05" [(ngModel)]="layer.opacity" (change)="snapshot()"></label>
          </div>

          <label>Variable schema
            <select [(ngModel)]="variableSchema" (ngModelChange)="loadVariables($event)">
              <option value="common">Common</option>
              <option value="voting">Voting</option>
              <option value="ranks">Ranks</option>
            </select>
          </label>

          <label>Variable
            <select [(ngModel)]="layer.variable" (change)="snapshot()">
              <option value="">None</option>
              @for(v of variableItems;track v.key){<option [value]="v.token">{{v.group}} · {{v.label}} · {{v.token}}</option>}
            </select>
          </label>

          @if(layer.type==='text'){
            <label>Fallback text<input [(ngModel)]="layer.text" (change)="snapshot()"></label>
            <div class="two">
              <label>Font size<input type="number" min="8" [(ngModel)]="layer.fontSize" (change)="snapshot()"></label>
              <label>Weight<select [(ngModel)]="layer.fontWeight" (change)="snapshot()">
                <option value="400">Regular</option>
                <option value="600">Semi Bold</option>
                <option value="700">Bold</option>
                <option value="900">Black</option>
              </select></label>
            </div>
            <div class="two">
              <label>Color<input type="color" [(ngModel)]="layer.color" (change)="snapshot()"></label>
              <label>Align<select [(ngModel)]="layer.align" (change)="snapshot()">
                <option value="left">Left</option><option value="center">Center</option><option value="right">Right</option>
              </select></label>
            </div>
          }

          @if(layer.type==='image'){
            <label>Asset
              <select [(ngModel)]="layer.assetId" (change)="snapshot()">
                <option [ngValue]="null">Select asset</option>
                @for(a of imageAssets();track a.id){
                  <option [ngValue]="a.id">{{a.name}} · {{a.asset_type}}</option>
                }
              </select>
            </label>
          }

          @if(layer.type==='rectangle'){
            <div class="two">
              <label>Fill<input type="color" [(ngModel)]="layer.background" (change)="snapshot()"></label>
              <label>Border<input type="color" [(ngModel)]="layer.borderColor" (change)="snapshot()"></label>
            </div>
            <div class="two">
              <label>Border width<input type="number" min="0" [(ngModel)]="layer.borderWidth" (change)="snapshot()"></label>
              <label>Radius<input type="number" min="0" [(ngModel)]="layer.borderRadius" (change)="snapshot()"></label>
            </div>
          }

          <div class="checks">
            <label><input type="checkbox" [(ngModel)]="layer.visible" (change)="snapshot()"> Visible</label>
            <label><input type="checkbox" [(ngModel)]="layer.locked" (change)="snapshot()"> Locked</label>
          </div>

          <div class="z-actions">
            <button (click)="moveLayer(layer,1)">Bring forward</button>
            <button (click)="moveLayer(layer,-1)">Send backward</button>
          </div>
        </div>
      } @else {
        <div class="empty-properties">
          <b>Select a layer</b>
          <p>Click a canvas element or choose a layer from the list.</p>
        </div>
      }
    </aside>
   </section>
  </main>
 </sn-shell>`,
 styles:[`
 :host{display:block;min-width:0}.page{display:grid;gap:1rem}.panel{background:var(--surface-1);border:1px solid var(--line);border-radius:16px}
 .toolbar{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:1rem}.title small,.section-title small,.workspace-head small{color:var(--primary);font-size:.56rem;letter-spacing:.14em;font-weight:900}.title h2,.section-title h3{margin:.2rem 0}.title p{margin:.2rem 0;color:var(--muted)}
 .template-picker{display:flex;align-items:end;gap:.5rem}.template-picker label{min-width:260px}
 button,input,select{font:inherit;border:1px solid var(--line);border-radius:8px;background:var(--surface-2);color:var(--text);padding:.6rem}.primary{background:var(--primary);color:#03130e;font-weight:850}.danger{color:#ff9aa8;border-color:rgba(255,92,114,.3)}button{cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}
 label{display:grid;gap:.3rem;color:var(--muted);font-size:.62rem}.notice{padding:.7rem 1rem;border-radius:10px}.error{color:#ff9aa8}.success{color:var(--success)}
 .designer{display:grid;grid-template-columns:250px minmax(0,1fr) 290px;gap:.8rem;min-height:720px}.left,.right{padding:.8rem;min-width:0}.section-title{display:flex;justify-content:space-between;align-items:center;gap:.5rem}.add-grid{display:grid;grid-template-columns:1fr 1fr;gap:.4rem;margin:.8rem 0}.add-grid button{text-align:left}
 .layers{display:grid;gap:.35rem}.layers article{display:grid;grid-template-columns:20px 1fr 34px;align-items:center;gap:.45rem;padding:.55rem;border:1px solid transparent;border-radius:9px;cursor:pointer}.layers article:hover,.layers article.active{background:var(--primary-soft);border-color:var(--line-strong)}.layers article div{display:grid;gap:.1rem}.layers small{color:var(--muted);font-size:.54rem}.drag{color:var(--muted)}
 .workspace{display:grid;grid-template-rows:auto 1fr;min-width:0;overflow:hidden}.workspace-head{display:flex;justify-content:space-between;align-items:center;padding:.7rem .9rem;border-bottom:1px solid var(--line)}.workspace-head>div:first-child{display:grid;gap:.15rem}.zoom{display:flex;align-items:center;gap:.4rem}.zoom span{min-width:52px;text-align:center;color:var(--muted);font-size:.62rem}
 .canvas-scroll{overflow:auto;display:grid;place-items:start center;padding:2rem;background:radial-gradient(circle at center,rgba(53,226,178,.035),transparent 55%),#03070b}.canvas-frame{position:relative}.canvas{position:absolute;left:0;top:0;transform-origin:top left;background-color:#08131c;background-size:cover;background-position:center;box-shadow:0 18px 70px #000;overflow:hidden}
 .canvas-layer{position:absolute;user-select:none;cursor:move}.canvas-layer.selected{outline:2px solid var(--primary);outline-offset:2px}.canvas-layer.locked{cursor:not-allowed}.canvas-layer img,.shape,.text-layer{width:100%;height:100%}.canvas-layer img{object-fit:contain;pointer-events:none}.text-layer{display:flex;align-items:center;white-space:pre-wrap;overflow:hidden}.placeholder,.qr-placeholder{width:100%;height:100%;display:grid;place-items:center;background:rgba(53,226,178,.08);border:2px dashed rgba(53,226,178,.3);color:var(--primary)}.qr-placeholder{font-size:3rem}.qr-placeholder small{font-size:.55rem}.progress{width:100%;height:100%;display:flex;align-items:center}.progress:before{content:'';position:absolute;inset:30% 0;background:#17323c;border-radius:999px}.progress div{position:relative;height:40%;background:var(--primary);border-radius:999px}.shape{border-style:solid}.resize{position:absolute;right:-12px;bottom:-12px;width:24px;height:24px;padding:0;display:grid;place-items:center;background:var(--primary);color:#03130e;border:0}
 .properties{display:grid;gap:.65rem;margin-top:.8rem}.two{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}.checks{display:flex;gap:.8rem}.checks label{display:flex;align-items:center;gap:.4rem}.z-actions{display:grid;grid-template-columns:1fr 1fr;gap:.4rem}.empty-properties{height:100%;display:grid;place-content:center;text-align:center;color:var(--muted)}.empty-properties p{max-width:220px;font-size:.65rem}
 @media(max-width:1150px){.designer{grid-template-columns:220px minmax(0,1fr)}.right{grid-column:1/-1}.toolbar{align-items:flex-start;flex-direction:column}.template-picker{width:100%;flex-wrap:wrap}}
 @media(max-width:760px){.designer{grid-template-columns:1fr}.left,.right{grid-column:auto}.template-picker label{min-width:100%;width:100%}.canvas-scroll{padding:1rem}}
 `]
})
export class TemplateDesignerComponent implements OnInit {
 private api=inject(TemplateDesignerService);
 private variableApi=inject(MediaVariablesService);

 templates=signal<any[]>([]);
 assets=signal<any[]>([]);
 error=signal('');
 success=signal('');
 previewOpen=signal(false);
 previewLoading=signal(false);
 previewUrl=signal('');

 selectedTemplateId='';
 selectedLayerId='';
 layers:DesignerLayer[]=[];
 canvas={width:1536,height:2048};
 backgroundUrl='';
 zoom=.42;
 history: string[] = [];

 variables:string[]=[];
 variableItems:any[]=[];
 variableSchema='common';

 private dragState:any=null;
 private resizeState:any=null;

 ngOnInit(){
  this.loadVariables('common');
  this.api.templates().subscribe({next:x=>this.templates.set(x.items||[]),error:e=>this.fail(e)});
  this.api.assets().subscribe({next:x=>this.assets.set(x.items||[]),error:e=>this.fail(e)});
  window.addEventListener('mousemove',this.onMove);
  window.addEventListener('mouseup',this.onUp);
 }

 loadVariables(schema:string){
  this.variableSchema=schema;
  this.variableApi.list(schema).subscribe({
    next:x=>{this.variableItems=x.items||[];this.variables=this.variableItems.map((item:any)=>item.token)},
    error:e=>this.fail(e)
  });
 }

 fail(e:any){this.error.set(e?.error?.detail||e?.message||'Request failed')}

 selectTemplate(id:string){
  const t=this.templates().find(x=>x.id===id);
  if(!t){this.layers=[];this.backgroundUrl='';return}
  this.variableSchema=t.category==='voting'?'voting':t.category==='ranks'?'ranks':'common';
  this.loadVariables(this.variableSchema);
  this.canvas={width:t.canvas_width||1536,height:t.canvas_height||2048};
  this.backgroundUrl=t.background_url||t.preview_url||'';
  const manifest=t.manifest||{};
  this.layers=Array.isArray(manifest.layers)?structuredClone(manifest.layers):[];
  this.selectedLayerId=this.layers[0]?.id||'';
  this.history=[];
 }

 sortedLayers(){return [...this.layers].sort((a,b)=>b.zIndex-a.zIndex)}
 selectedLayer(){return this.layers.find(x=>x.id===this.selectedLayerId)}
 imageAssets(){return this.assets().filter(x=>x.mime_type?.startsWith('image/'))}
 assetUrl(id?:string|null){return this.assets().find(x=>x.id===id)?.url||''}

 previewText(layer:DesignerLayer){
  const samples:any={
   '{{TITLE}}':'NAP POLICY VOTING RESULTS',
   '{{DESCRIPTION}}':'Thank you for participating!',
   '{{TOTAL_VOTES}}':'128 votes',
   '{{WINNER_LABEL}}':'NAP 15',
   '{{WINNER_VOTES}}':'72 votes',
   '{{WINNER_PERCENTAGE}}':'56.3%',
   '{{SERVER_NAME}}':'Server 2279',
   '{{RANK_TITLE}}':'POWER RANKING',
   '{{ENTRY_NAME}}':'Player name',
   '{{ENTRY_VALUE}}':'245.8M',
   '{{QR_CAPTION}}':'Visit our website'
  };
  return layer.variable ? (samples[layer.variable]||layer.variable) : (layer.text||'Text');
 }

 addLayer(type:LayerType){
  this.pushHistory();
  const z=Math.max(0,...this.layers.map(x=>x.zIndex))+1;
  const layer:DesignerLayer={
   id:crypto.randomUUID(),type,name:type[0].toUpperCase()+type.slice(1),
   x:100,y:100,width:type==='text'?700:300,height:type==='text'?110:300,
   rotation:0,opacity:1,zIndex:z,visible:true,locked:false,
   variable:type==='qr'?'{{QR_URL}}':'',text:type==='text'?'New text':'',
   fontSize:56,fontWeight:'700',color:'#ffffff',align:'left',
   background:'#15313c',borderColor:'#35e2b2',borderWidth:2,borderRadius:18,
   assetId:null
  };
  this.layers.push(layer);this.selectedLayerId=layer.id;
 }

 selectLayer(id:string){this.selectedLayerId=id}
 clearSelection(e:MouseEvent){if(e.target===e.currentTarget)this.selectedLayerId=''}

 toggleVisible(layer:DesignerLayer){this.pushHistory();layer.visible=!layer.visible}
 deleteLayer(layer:DesignerLayer){this.pushHistory();this.layers=this.layers.filter(x=>x.id!==layer.id);this.selectedLayerId=''}
 moveLayer(layer:DesignerLayer,d:number){this.pushHistory();layer.zIndex=Math.max(0,layer.zIndex+d)}
 setZoom(v:number){this.zoom=Math.min(1,Math.max(.15,v))}

 pushHistory(){this.history.push(JSON.stringify(this.layers));if(this.history.length>40)this.history.shift()}
 snapshot(){this.pushHistory()}
 undo(){const raw=this.history.pop();if(raw)this.layers=JSON.parse(raw)}

 startDrag(e:MouseEvent,layer:DesignerLayer){
  e.stopPropagation();this.selectedLayerId=layer.id;
  if(layer.locked)return;
  this.pushHistory();
  this.dragState={layer,startX:e.clientX,startY:e.clientY,x:layer.x,y:layer.y};
 }

 startResize(e:MouseEvent,layer:DesignerLayer){
  e.stopPropagation();this.pushHistory();
  this.resizeState={layer,startX:e.clientX,startY:e.clientY,w:layer.width,h:layer.height};
 }

 onMove=(e:MouseEvent)=>{
  if(this.dragState){
   const d=this.dragState;
   d.layer.x=Math.round(d.x+(e.clientX-d.startX)/this.zoom);
   d.layer.y=Math.round(d.y+(e.clientY-d.startY)/this.zoom);
  }
  if(this.resizeState){
   const r=this.resizeState;
   r.layer.width=Math.max(20,Math.round(r.w+(e.clientX-r.startX)/this.zoom));
   r.layer.height=Math.max(20,Math.round(r.h+(e.clientY-r.startY)/this.zoom));
  }
 }

 onUp=()=>{this.dragState=null;this.resizeState=null}

 save(){
  const current=this.templates().find(x=>x.id===this.selectedTemplateId);
  if(!current)return;
  const manifest={
   ...(current.manifest||{}),
   schema_version:2,
   canvas:{width:this.canvas.width,height:this.canvas.height},
   layers:this.layers,
   variables:[...new Set(this.layers.map(x=>x.variable).filter(Boolean))],
   updated_by:'template-designer'
  };
  this.api.saveTemplate(this.selectedTemplateId,manifest).subscribe({
   next:x=>{
    const list=this.templates().map(t=>t.id===x.id?x:t);
    this.templates.set(list);
    this.success.set('Template layout saved.');
   },
   error:e=>this.fail(e)
  });
 }
}
