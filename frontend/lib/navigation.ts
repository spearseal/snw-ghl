import type { LucideIcon } from 'lucide-react';
import {
  BarChart3,
  ClipboardList,
  DollarSign,
  FileText,
  HeartPulse,
  Sparkles,
  UserCheck,
} from 'lucide-react';

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  description?: string;
  keywords?: string[];
}

export const APP_NAV: NavItem[] = [
  {
    href: '/ceo-tasks',
    label: 'CEO Top 5 Tasks',
    icon: ClipboardList,
    description: 'Prioritized CEO actions from patient data',
    keywords: ['ceo', 'tasks', 'priorities'],
  },
  {
    href: '/treatment-plans',
    label: 'Treatment Plans',
    icon: HeartPulse,
    description: 'Per-patient treatment plans and health intake',
    keywords: ['treatment', 'intake', 'health', 'patient'],
  },
  {
    href: '/reactivate-campaign',
    label: 'Reactivate Campaign',
    icon: UserCheck,
    description: 'Win back 90+ day no-show patients with discounts',
    keywords: ['reactivate', 'win-back', 'email', 'discount'],
  },
  {
    href: '/revenue-growth',
    label: 'Revenue Growth',
    icon: DollarSign,
    description: 'Monthly revenue factors and pipeline decisions',
    keywords: ['revenue', 'growth', 'pipeline', 'monthly'],
  },
  {
    href: '/reports',
    label: 'Reports',
    icon: FileText,
    description: 'Executive, revenue, retention, compliance, and CEO reports',
    keywords: ['reports', 'export', 'analytics', 'summary', 'print'],
  },
  {
    href: '/',
    label: 'Marketing Insights',
    icon: BarChart3,
    description: 'KPI dashboard and source breakdown',
    keywords: ['dashboard', 'kpi', 'insights', 'marketing'],
  },
  {
    href: '/query',
    label: 'Spagent AI',
    icon: Sparkles,
    description: 'Natural language queries across data sources',
    keywords: ['query', 'ai', 'spagent', 'search', 'sql'],
  },
];

export const KEYBOARD_SHORTCUTS = [
  { keys: '⌘ K', label: 'Global search' },
  { keys: '⌘ B', label: 'Toggle sidebar' },
  { keys: '⌘ P', label: 'Print page' },
  { keys: '?', label: 'Keyboard shortcuts' },
  { keys: 'Esc', label: 'Close dialogs' },
] as const;
