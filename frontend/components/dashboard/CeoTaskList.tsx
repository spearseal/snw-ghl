import {
  ClipboardList,
  DollarSign,
  HeartPulse,
  MessageSquare,
  Shield,
} from 'lucide-react';

export interface CeoTask {
  rank: number;
  priority: 'high' | 'medium' | 'low' | string;
  title: string;
  description: string;
  metric: string | number;
  metric_label: string;
  category: string;
  action: string;
  source: string;
}

const CATEGORY_ICONS: Record<string, typeof HeartPulse> = {
  retention: HeartPulse,
  customer_service: MessageSquare,
  revenue: DollarSign,
  acquisition: ClipboardList,
  compliance: Shield,
};

const PRIORITY_RING: Record<string, string> = {
  high: 'border-red-500/60 bg-red-950/20',
  medium: 'border-amber-500/50 bg-amber-950/15',
  low: 'border-slate-600 bg-slate-900/40',
};

export default function CeoTaskList({ tasks }: { tasks: CeoTask[] }) {
  if (!tasks.length) {
    return (
      <p className="text-sm text-slate-500">
        Connect data sources and refresh insights to generate CEO priorities.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {tasks.map((task) => {
        const Icon = CATEGORY_ICONS[task.category] || ClipboardList;
        const ring = PRIORITY_RING[task.priority] || PRIORITY_RING.low;
        return (
          <div
            key={task.rank}
            className={`flex gap-4 rounded-xl border p-4 ${ring}`}
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-950 text-lg font-bold text-indigo-300">
              {task.rank}
            </div>
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <Icon className="h-4 w-4 text-indigo-400" />
                <h3 className="font-semibold text-slate-100">{task.title}</h3>
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                  {task.priority}
                </span>
              </div>
              <p className="text-sm leading-relaxed text-slate-400">{task.description}</p>
              <div className="mt-2 flex flex-wrap items-baseline gap-2">
                <span className="text-xl font-bold text-slate-50">{task.metric}</span>
                <span className="text-xs text-slate-500">{task.metric_label}</span>
                <span className="text-xs text-slate-600">· {task.source}</span>
              </div>
              <p className="mt-2 text-xs text-indigo-300/90">→ {task.action}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
