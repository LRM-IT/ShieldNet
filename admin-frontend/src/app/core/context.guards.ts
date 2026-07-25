import { inject } from '@angular/core';
import { ActivatedRouteSnapshot, CanActivateFn, Router, UrlTree } from '@angular/router';
import { UserProfile } from './api.models';

import { AuthService } from './auth.service';
import { GuildService } from './guild.service';

async function ensureProfile(auth: AuthService, router: Router): Promise<UserProfile | UrlTree> {
  if (!auth.accessToken) {
    const refreshed = await auth.refreshAccessToken();
    if (!refreshed) return router.parseUrl('/login');
  }
  try {
    return auth.profile() || await auth.loadProfile();
  } catch {
    auth.logout();
    return router.parseUrl('/login');
  }
}

export const platformGuard: CanActivateFn = async () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const profile = await ensureProfile(auth, router);
  if (!('platform_context' in profile) || !profile.platform_context) return router.parseUrl('/access-denied');
  return true;
};

export const guildGuard: CanActivateFn = async (route: ActivatedRouteSnapshot) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const guilds = inject(GuildService);
  const profile = await ensureProfile(auth, router);
  if (!('id' in profile)) return profile;
  if (profile.platform_context) return true;

  const guildId = route.paramMap.get('guildId');
  if (!guildId) return router.parseUrl('/servers');
  try {
    const allowed = await guilds.list();
    return allowed.some(item => String(item.guild_id) === String(guildId))
      ? true
      : router.parseUrl('/access-denied');
  } catch {
    return router.parseUrl('/access-denied');
  }
};
