export function normalizePath(pathname: string): string {
  const trimmed = pathname.replace(/\/$/, '');
  return trimmed || '/';
}

export function isLoginPath(pathname: string): boolean {
  return normalizePath(pathname) === '/login';
}
