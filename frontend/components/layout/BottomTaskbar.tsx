'use client';

import { Cable, Mail, ShieldCheck, X } from 'lucide-react';
import { useState } from 'react';
import ConnectorsPanel from '@/components/panels/ConnectorsPanel';
import CompliancePanel from '@/components/panels/CompliancePanel';
import EmailPanel from '@/components/panels/EmailPanel';

export type TaskbarPanel = 'connectors' | 'email' | 'compliance' | null;

interface BottomTaskbarProps {
  activePanel: TaskbarPanel;
  onPanelChange: (panel: TaskbarPanel) => void;
}

const ITEMS = [
  { id: 'connectors' as const, label: 'DB Connectors', icon: Cable },
  { id: 'email' as const, label: 'Email Follow-up', icon: Mail },
  { id: 'compliance' as const, label: 'Compliance', icon: ShieldCheck },
];

const PANEL_TITLES: Record<Exclude<TaskbarPanel, null>, string> = {
  connectors: 'DB Connectors',
  email: 'Email Follow-up Campaign',
  compliance: 'Compliance & Service Evaluation',
};

export default function BottomTaskbar({
  activePanel,
  onPanelChange,
}: BottomTaskbarProps) {
  const [hovered, setHovered] = useState(false);
  const expanded = hovered || activePanel !== null;

  const toggle = (id: TaskbarPanel) => {
    onPanelChange(activePanel === id ? null : id);
  };

  return (
    <>
      {activePanel && (
        <div
          className="fixed inset-0 z-40 bg-black/40"
          onClick={() => onPanelChange(null)}
          aria-hidden
        />
      )}

      <div
        className="fixed bottom-0 left-60 right-0 z-50"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {activePanel && (
          <div className="flex max-h-[min(70vh,640px)] flex-col border-t border-slate-600 bg-slate-950 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
              <h2 className="text-sm font-semibold text-slate-200">
                {PANEL_TITLES[activePanel]}
              </h2>
              <button
                type="button"
                onClick={() => onPanelChange(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {activePanel === 'connectors' && <ConnectorsPanel />}
              {activePanel === 'email' && <EmailPanel />}
              {activePanel === 'compliance' && <CompliancePanel />}
            </div>
          </div>
        )}

        <div
          className={`flex items-center justify-center border-t border-slate-600 bg-slate-900/95 backdrop-blur transition-all duration-200 ${
            expanded ? 'h-12' : 'h-2'
          }`}
        >
          <div
            className={`flex items-center gap-2 px-4 transition-opacity duration-200 ${
              expanded ? 'opacity-100' : 'opacity-0'
            }`}
          >
            {ITEMS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => toggle(id)}
                title={label}
                className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition ${
                  activePanel === id
                    ? 'bg-indigo-600 text-white shadow-inner'
                    : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
