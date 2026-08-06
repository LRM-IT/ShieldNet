import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
@Injectable({providedIn:'root'})
export class TemplateBankService{
 constructor(private http:HttpClient){}
 settings(){return this.http.get<any>('/api/v1/platform/template-bank/settings')}
 saveSettings(x:any){return this.http.put<any>('/api/v1/platform/template-bank/settings',x)}
 games(){return this.http.get<any>('/api/v1/platform/template-bank/games')}
 createGame(x:any){return this.http.post<any>('/api/v1/platform/template-bank/games',x)}
 updateGame(id:string,x:any){return this.http.patch<any>(`/api/v1/platform/template-bank/games/${id}`,x)}
 deleteGame(id:string){return this.http.delete<void>(`/api/v1/platform/template-bank/games/${id}`)}
 templates(){return this.http.get<any>('/api/v1/platform/template-bank/templates')}
 updateTemplate(id:string,x:any){return this.http.patch<any>(`/api/v1/platform/template-bank/templates/${id}`,x)}
}
