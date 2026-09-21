import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, retry, switchMap, throwError, timer } from 'rxjs';

import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const isAuthRequest =
    request.url.includes('/auth/login') ||
    request.url.includes('/auth/refresh') ||
    request.url.includes('/auth/discord/start');

  const token = auth.accessToken;
  const authorized = token && !isAuthRequest
    ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : request;

  const transientStatuses = new Set([0, 502, 503, 504, 520, 521, 522, 523, 524]);

  return next(authorized).pipe(
    retry({
      count: 2,
      delay: (error: HttpErrorResponse, retryCount) => {
        if (authorized.method !== 'GET' || !transientStatuses.has(error.status)) {
          return throwError(() => error);
        }
        return timer(350 * retryCount);
      },
    }),
    catchError((error: HttpErrorResponse) => {
      if (error.status !== 401 || isAuthRequest || !auth.refreshToken) {
        return throwError(() => error);
      }

      return from(auth.refreshAccessToken()).pipe(
        switchMap((newToken) => {
          if (!newToken) return throwError(() => error);
          return next(
            request.clone({
              setHeaders: { Authorization: `Bearer ${newToken}` },
            }),
          );
        }),
      );
    }),
  );
};
