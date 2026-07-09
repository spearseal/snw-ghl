export function normalizePath(pathname: string): string {
  const trimmed = pathname.replace(/\/$/, '');
  return trimmed || '/';
}

/** Default landing page after sign-in welcome */
export const DEFAULT_APP_ROUTE = '/query';

/** Post-login welcome screen */
export const WELCOME_ROUTE = '/welcome';

export function isLoginPath(pathname: string): boolean {
  return normalizePath(pathname) === '/login';
}

export function isWelcomePath(pathname: string): boolean {
  return normalizePath(pathname) === '/welcome';
}

/** Routes rendered without the app chrome (sidebar, taskbar) */
export function isAuthFlowPath(pathname: string): boolean {
  return isLoginPath(pathname) || isWelcomePath(pathname);
}

export function isActiveNavPath(pathname: string, href: string): boolean {
  return normalizePath(pathname) === normalizePath(href);
}
