import type { PaginatedMeta, SortDirection } from '@/lib/types/common';

export function clampPage(page: number, totalPages: number): number {
  if (totalPages <= 0) return 1;
  return Math.min(Math.max(1, page), totalPages);
}

export function buildPaginatedMeta(
  total: number,
  page: number,
  pageSize: number,
): PaginatedMeta {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = clampPage(page, totalPages);
  return {
    page: safePage,
    page_size: pageSize,
    total,
    total_pages: totalPages,
    has_next: safePage < totalPages,
    has_prev: safePage > 1,
  };
}

export function paginateArray<T>(items: T[], page: number, pageSize: number): T[] {
  const start = (clampPage(page, Math.ceil(items.length / pageSize) || 1) - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

export function parseSortParam(
  sort: string | undefined,
  allowed: string[],
  defaultField: string,
): { field: string; direction: SortDirection } {
  if (!sort) return { field: defaultField, direction: 'desc' };
  const desc = sort.startsWith('-');
  const field = desc ? sort.slice(1) : sort;
  if (!allowed.includes(field)) return { field: defaultField, direction: 'desc' };
  return { field, direction: desc ? 'desc' : 'asc' };
}

export function sortByField<T extends Record<string, unknown>>(
  items: T[],
  field: string,
  direction: SortDirection,
): T[] {
  const sorted = [...items].sort((a, b) => {
    const av = a[field];
    const bv = b[field];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'number' && typeof bv === 'number') return av - bv;
    return String(av).localeCompare(String(bv), undefined, { sensitivity: 'base' });
  });
  return direction === 'desc' ? sorted.reverse() : sorted;
}

export function filterByQuery<T extends Record<string, unknown>>(
  items: T[],
  query: string,
  fields: string[],
): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter((item) =>
    fields.some((f) => String(item[f] ?? '').toLowerCase().includes(q)),
  );
}
