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

function hasPlatformAccess(profile: UserProfile): boolean {
  const roles = (profile.roles || []).map(role => String(role).toLowerCase());
  return Boolean(
    profile.platform_context ||
    profile.is_superadmin ||
    roles.includes('superadmin') ||
    roles.includes('super_admin') ||
    roles.includes('platform_admin')
  );
}

export const platformGuard: CanActivateFn = async () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const profile = await ensureProfile(auth, router);
  if (!('id' in profile) || !hasPlatformAccess(profile)) return router.parseUrl('/access-denied');
  return true;
};

export const guildGuard: CanActivateFn = async (route: ActivatedRouteSnapshot) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const guilds = inject(GuildService);
  const profile = await ensureProfile(auth, router);
  if (!('id' in profile)) return profile;
  if (hasPlatformAccess(profile)) return true;

  const guildId = route.paramMap.get('guildId');
  if (!guildId) return router.parseUrl('/servers');

  try {
    const allowed = await guilds.list();
    const access = allowed.find(item => String(item.guild_id) === String(guildId));
    if (!access) return router.parseUrl('/access-denied');

    const requiredModule = route.data?.['guildModule'] as string | undefined;
    if (!requiredModule || access.is_owner || access.permissions?.includes('*')) return true;

    return access.permissions?.includes(requiredModule)
      ? true
      : router.createUrlTree(['/access-denied'], {
          queryParams: { guildId, module: requiredModule, reason: 'missing_permission' },
        });
  } catch {
    return router.parseUrl('/access-denied');
  }
};
