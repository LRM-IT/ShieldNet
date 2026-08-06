import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({providedIn:'root'})
export class TemplateBankService {
  constructor(private http:HttpClient){}
  settings(){return this.http.get<any>('/api/v1/platform/template-bank/settings')}
  saveSettings(payload:any){return this.http.put<any>('/api/v1/platform/template-bank/settings',payload)}
  list(){return this.http.get<any>('/api/v1/platform/template-bank/templates')}
  create(data:FormData){return this.http.post<any>('/api/v1/platform/template-bank/templates',data)}
  update(id:string,payload:any){return this.http.patch<any>(`/api/v1/platform/template-bank/templates/${id}`,payload)}
  remove(id:string){return this.http.delete<void>(`/api/v1/platform/template-bank/templates/${id}`)}
}
