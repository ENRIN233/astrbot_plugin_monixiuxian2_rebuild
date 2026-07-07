import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export function PageLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  const navigate = useNavigate();
  return (
    <div style={{ background: '#050810', minHeight: '100vh' }}>
      <div className="max-w-7xl mx-auto px-4 py-8 md:py-12">
        <button
          onClick={() => navigate('/')}
          className="group inline-flex items-center gap-2 text-xs tracking-wider mb-8 cursor-pointer bg-transparent border-none"
          style={{ color: 'rgba(0,240,255,0.4)' }}
        >
          <ArrowLeft className="w-3.5 h-3.5 transition-transform duration-300 group-hover:-translate-x-1" />
          返回首页
        </button>

        <h1 className="text-3xl md:text-4xl font-medium mb-2 neon-title">
          {title}
        </h1>
        {subtitle && <p className="text-sm mb-8" style={{ color: 'rgba(200,208,224,0.4)' }}>{subtitle}</p>}

        {children}
      </div>
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="flex items-center justify-center py-24">
      <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(0,240,255,0.1)', borderTopColor: '#00F0FF' }} />
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="text-center py-16">
      <p className="text-sm" style={{ color: 'rgba(200,208,224,0.4)' }}>加载失败: {message}</p>
    </div>
  );
}

// ================== DataTable (Tech theme) ==================
interface Column {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (val: unknown, row: Record<string, unknown>) => React.ReactNode;
}

export function DataTable({ columns, data, rowClass }: { columns: Column[]; data: Record<string, unknown>[]; rowClass?: string }) {
  const [sortKey, setSortKey] = React.useState<string | null>(null);
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('asc');

  const sorted = React.useMemo(() => {
    if (!sortKey) return data;
    return [...data].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'asc' ? av - bv : bv - av;
      return sortDir === 'asc'
        ? String(av).localeCompare(String(bv), 'zh')
        : String(bv).localeCompare(String(av), 'zh');
    });
  }, [data, sortKey, sortDir]);

  if (!sorted.length) {
    return <div className="text-center py-12 text-sm" style={{ color: 'rgba(200,208,224,0.3)' }}>暂无数据</div>;
  }

  return (
    <div className="overflow-x-auto tech-container">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map(col => (
              <th
                key={col.key}
                className={col.sortable !== false ? 'cursor-pointer' : ''}
                onClick={() => {
                  if (col.sortable === false) return;
                  if (sortKey === col.key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
                  else { setSortKey(col.key); setSortDir('asc'); }
                }}
              >
                {col.label}
                {col.sortable !== false && sortKey === col.key && (
                  <span className="ml-1" style={{ color: '#00F0FF' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i} className={rowClass || ''} style={{ animationDelay: `${i * 0.04}s` }}>
              {columns.map(col => (
                <td key={col.key}>
                  {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '-')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ================== ListView (Tech vertical list alternative) ==================
interface ListItem {
  key: string;
  content: React.ReactNode;
}

export function ListView({ items }: { items: ListItem[] }) {
  return (
    <div className="tech-container">
      {items.map((item, i) => (
        <div
          key={item.key}
          className="tech-item stagger-fade"
          style={{ animationDelay: `${i * 0.05}s`, padding: '36px 28px' }}
        >
          {item.content}
        </div>
      ))}
    </div>
  );
}

// ================== RankBadge ==================
const RANK_MAP: [string, string][] = [
  ['人阶下品', 'rank-人阶'], ['人阶上品', 'rank-人阶'],
  ['黄阶下品', 'rank-黄阶'], ['黄阶上品', 'rank-黄阶'],
  ['玄阶下品', 'rank-玄阶'], ['玄阶上品', 'rank-玄阶'],
  ['地阶下品', 'rank-地阶'], ['地阶上品', 'rank-地阶'],
  ['天阶下品', 'rank-天阶'], ['天阶上品', 'rank-天阶'],
  ['仙阶下品', 'rank-仙阶'], ['仙阶上品', 'rank-仙阶'],
  ['仙阶极品', 'rank-仙阶'],
  ['无上', 'rank-无上'], ['无上仙法', 'rank-无上'], ['无上神通', 'rank-无上'],
];

export function RankBadge({ rank }: { rank?: string }) {
  if (!rank) return null;
  const cls = RANK_MAP.find(([k]) => rank.startsWith(k))?.[1] || '';
  return <span className={`rank-badge ${cls}`}>{rank}</span>;
}

// ================== SubTabs ==================
export function SubTabs({ tabs, active, onChange }: {
  tabs: { key: string; label: string; count?: number }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-2 flex-wrap mb-6">
      {tabs.map(t => (
        <button
          key={t.key}
          className={`sub-tab ${active === t.key ? 'active' : ''}`}
          onClick={() => onChange(t.key)}
        >
          {t.label}{t.count !== undefined ? ` (${t.count})` : ''}
        </button>
      ))}
    </div>
  );
}

// ================== FilterBar ==================
export function FilterBar({ ranks, activeRank, onChange }: {
  ranks: string[];
  activeRank: string;
  onChange: (rank: string) => void;
}) {
  if (!ranks.length) return null;
  return (
    <div className="flex gap-2 flex-wrap mb-6 items-center">
      <span className="text-xs mr-1" style={{ color: 'rgba(0,240,255,0.3)' }}>品阶筛选：</span>
      {['全部', ...ranks].map(r => (
        <button
          key={r}
          className={`sub-tab text-xs px-3 py-1 ${activeRank === r ? 'active' : ''}`}
          onClick={() => onChange(r)}
        >
          {r}
        </button>
      ))}
    </div>
  );
}
