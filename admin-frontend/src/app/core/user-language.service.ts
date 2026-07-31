import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {firstValueFrom} from 'rxjs';
import {GlobalLanguage} from './global-language.service';
export interface WorkspaceLanguage extends GlobalLanguage{selected:boolean;enabled:boolean;is_primary:boolean;is_fallback:boolean}
@Injectable({providedIn:'root'})
export class UserLanguageService{
 constructor(private http:HttpClient){}
 listMine(){return firstValueFrom(this.http.get<WorkspaceLanguage[]>('/api/v1/me/languages'))}
 saveMine(items:any[]){return firstValueFrom(this.http.put<WorkspaceLanguage[]>('/api/v1/me/languages',{items}))}
 listForGuild(guildId:string){return firstValueFrom(this.http.get<WorkspaceLanguage[]>(`/api/v1/discord/guilds/${guildId}/available-languages`))}
}
