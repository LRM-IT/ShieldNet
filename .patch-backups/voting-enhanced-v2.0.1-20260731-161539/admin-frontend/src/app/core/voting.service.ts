import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({providedIn:'root'})
export class VotingService {
  constructor(private http:HttpClient){}
  list(guildId:string){return this.http.get<any>(`/api/v1/discord/guilds/${guildId}/plugins/voting/polls`)}
  get(guildId:string,pollId:string){return this.http.get<any>(`/api/v1/discord/guilds/${guildId}/plugins/voting/polls/${pollId}`)}
  create(guildId:string,payload:any){return this.http.post<any>(`/api/v1/discord/guilds/${guildId}/plugins/voting/polls`,payload)}
  update(guildId:string,pollId:string,payload:any){return this.http.put<any>(`/api/v1/discord/guilds/${guildId}/plugins/voting/polls/${pollId}`,payload)}
  remove(guildId:string,pollId:string){return this.http.delete<void>(`/api/v1/discord/guilds/${guildId}/plugins/voting/polls/${pollId}`)}
  publish(guildId:string,pollId:string){return this.http.post<any>(`/api/v1/discord/guilds/${guildId}/plugins/voting/polls/${pollId}/publish`,{})}
  close(guildId:string,pollId:string){return this.http.post<any>(`/api/v1/discord/guilds/${guildId}/plugins/voting/polls/${pollId}/close`,{})}
  generate(guildId:string,pollId:string,language:string,payload:any){
    return this.http.post<any>(`/api/v1/discord/guilds/${guildId}/plugins/voting/polls/${pollId}/translations/${language}/generate`,payload)
  }
}
