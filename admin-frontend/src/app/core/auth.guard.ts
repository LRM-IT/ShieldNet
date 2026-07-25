import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = async () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!auth.accessToken) {
    const refreshed = await auth.refreshAccessToken();
    if (!refreshed) return router.parseUrl('/login');
  }

  if (!auth.profile()) {
    try {
      await auth.loadProfile();
    } catch {
      auth.logout();
      return false;
    }
  }

  return true;
};
