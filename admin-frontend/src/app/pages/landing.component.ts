import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../core/auth.service';
import { GuildService } from '../core/guild.service';

@Component({
  standalone: true,
  template: `<main class="landing"><div class="mark">SHIELDNET</div><h1>Opening control center…</h1><p>Resolving your access context.</p></main>`,
  styles: [`.landing{min-height:100vh;display:grid;place-content:center;text-align:center;background:#070b11;color:#eaf7f3}.mark{color:#35e2b2;font-weight:900;letter-spacing:.2em}.landing h1{margin:.7rem 0 .35rem}.landing p{margin:0;color:#82959e}`],
})
export class LandingComponent implements OnInit {
  constructor(private auth: AuthService, private guilds: GuildService, private router: Router) {}
  async ngOnInit(): Promise<void> {
    try {
      const profile = this.auth.profile() || await this.auth.loadProfile();
      if (profile.platform_context) {
        await this.router.navigateByUrl('/platform');
        return;
      }
      const guilds = await this.guilds.list();
      if (guilds.length === 1) {
        await this.router.navigate(['/guild', guilds[0].guild_id]);
      } else if (guilds.length > 1) {
        await this.router.navigateByUrl('/servers');
      } else {
        await this.router.navigateByUrl('/access-denied');
      }
    } catch {
      this.auth.logout();
    }
  }
}
