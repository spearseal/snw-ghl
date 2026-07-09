import { memo } from 'react';
import { TrendingUp, AlertTriangle, Database, Snowflake } from 'lucide-react';
import Badge from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { cn } from '@/lib/cn';

export interface KpiData {
  key: string;
  label: string;
  value: string | number;
  source: string;
  detail?: string;
  trend?: string | null;
  format?: string;
}

const SOURCE_VARIANT: Record<string, 'primary' | 'info' | 'success'> = {
  GoHighLevel: 'primary',
  Snowflake: 'info',
  'GoHighLevel + Snowflake': 'success',
};

const SOURCE_ICON: Record<string, typeof Database> = {
  GoHighLevel: Database,
  Snowflake: Snowflake,
  'GoHighLevel + Snowflake': TrendingUp,
};

function KpiCard({ kpi }: { kpi: KpiData }) {
  const variant = SOURCE_VARIANT[kpi.source] ?? 'success';
  const Icon = SOURCE_ICON[kpi.source] ?? TrendingUp;
  const isAttention = kpi.trend === 'attention';

  return (
    <Card
      hover
      accent={isAttention ? 'warning' : 'none'}
      className={cn(
        'relative',
        isAttention && 'border-warning/40 bg-warning-subtle/30',
      )}
    >
      {isAttention && (
        <AlertTriangle
          className="absolute right-4 top-4 h-4 w-4 text-warning"
          aria-label="Needs attention"
        />
      )}
      <div className="relative mb-4 flex items-center gap-2">
        <Icon className={cn('h-4 w-4', isAttention ? 'text-warning' : 'text-primary')} aria-hidden />
        <Badge variant={isAttention ? 'warning' : variant}>{kpi.source}</Badge>
      </div>
      <p className="text-3xl font-semibold tracking-tight text-fg">{kpi.value}</p>
      <p className="mt-1 text-card-title">{kpi.label}</p>
      {kpi.detail && <p className="mt-2 text-caption leading-relaxed">{kpi.detail}</p>}
    </Card>
  );
}

export default memo(KpiCard);
