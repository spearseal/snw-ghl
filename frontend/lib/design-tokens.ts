/** Design tokens — 8px spacing grid, semantic colors, typography scale */

export const spacing = {
  0: '0',
  1: '0.25rem', // 4px
  2: '0.5rem', // 8px
  3: '0.75rem', // 12px
  4: '1rem', // 16px
  5: '1.25rem', // 20px
  6: '1.5rem', // 24px
  8: '2rem', // 32px
  10: '2.5rem', // 40px
  12: '3rem', // 48px
  16: '4rem', // 64px
} as const;

export const breakpoints = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1440,
  '3xl': 1920,
} as const;

export const layout = {
  sidebarWidth: '15rem', // 240px
  sidebarCollapsed: '4rem', // 64px
  headerHeight: '3.5rem', // 56px
  contentMaxWidth: '90rem', // 1440px
  contentNarrow: '64rem', // 1024px
} as const;

export const motion = {
  fast: '150ms',
  base: '200ms',
  slow: '250ms',
  easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
} as const;

export const radii = {
  sm: '0.375rem',
  md: '0.5rem',
  lg: '0.75rem',
  xl: '1rem',
  '2xl': '1.25rem',
} as const;
