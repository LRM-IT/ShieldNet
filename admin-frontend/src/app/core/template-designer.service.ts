import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({providedIn:'root'})
export class TemplateDesignerService {
  constructor(private http:HttpClient){}

  templates(){
    return this.http.get<any>('/api/v1/platform/template-bank/templates');
  }

  assets(){
    return this.http.get<any>('/api/v1/platform/media-assets');
  }

  renderPreview(templateId:string,data:any={}){
    return this.http.post(
      `/api/v1/platform/template-bank/templates/${templateId}/render-preview`,
      {data},
      {responseType:'blob'}
    );
  }

  saveTemplate(templateId:string, manifest:any){
    return this.http.patch<any>(
      `/api/v1/platform/template-bank/templates/${templateId}`,
      {manifest},
    );
  }
}
