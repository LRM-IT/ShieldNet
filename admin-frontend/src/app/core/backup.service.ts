import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
export interface GuildBackup { id:string; guild_id:string; name:string; description?:string; status:string; format_version:number; object_count:number; size_bytes:number; created_at:string; snapshot?:any }
@Injectable({providedIn:'root'})
export class BackupService {
 constructor(private http:HttpClient){}
 list(guildId:string):Observable<GuildBackup[]>{return this.http.get<GuildBackup[]>(`/api/v1/discord/guilds/${guildId}/backups`)}
 create(guildId:string,payload:{name:string;description?:string}):Observable<GuildBackup>{return this.http.post<GuildBackup>(`/api/v1/discord/guilds/${guildId}/backups`,payload)}
 get(guildId:string,id:string):Observable<GuildBackup>{return this.http.get<GuildBackup>(`/api/v1/discord/guilds/${guildId}/backups/${id}`)}
 plan(guildId:string,id:string):Observable<any>{return this.http.post(`/api/v1/discord/guilds/${guildId}/backups/${id}/restore-plan`,{})}
 restore(guildId:string,id:string):Observable<any>{return this.http.post(`/api/v1/discord/guilds/${guildId}/backups/${id}/restore`,{confirmation:'RESTORE'})}
 remove(guildId:string,id:string):Observable<void>{return this.http.delete<void>(`/api/v1/discord/guilds/${guildId}/backups/${id}`)}
 download(guildId:string,id:string):Observable<Blob>{return this.http.get(`/api/v1/discord/guilds/${guildId}/backups/${id}/download`,{responseType:'blob'})}
}
