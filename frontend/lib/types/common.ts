/** Shared API / UI types */

export interface PaginatedMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PaginatedMeta;
}

export interface ApiErrorBody {
  detail?: string | Record<string, unknown>;
  message?: string;
}

export type SortDirection = 'asc' | 'desc';

export interface ListQueryParams {
  page?: number;
  page_size?: number;
  q?: string;
  sort?: string;
}

export interface SearchResult {
  id: string;
  type: 'contact' | 'opportunity' | 'page';
  title: string;
  subtitle?: string;
  source?: string;
  href?: string;
}

export type ToastVariant = 'success' | 'error' | 'info' | 'warning';

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
  duration?: number;
}

export interface ConfirmOptions {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'default';
}
