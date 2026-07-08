export function normalizePath(pathname: string): string {
  const trimmed = pathname.replace(/\/$/, '');
  return trimmed || '/';
}

/** Default landing page after sign-in */
export const DEFAULT_APP_ROUTE = '/query';

export function isLoginPath(pathname: string): boolean {
  return normalizePath(pathname) === '/login';
}

export function isActiveNavPath(pathname: string, href: string): boolean {
  return normalizePath(pathname) === normalizePath(href);
}
