/** Derive two-letter initials from an email address. */
export function getEmailInitials(email: string): string {
  const local = (email.split('@')[0] || '').trim();
  if (!local) return '??';

  const parts = local.split(/[._+-]/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase();
  }
  return local.slice(0, 2).toUpperCase();
}
