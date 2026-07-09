import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertTriangle } from 'lucide-react';

// ================== PageLayout ==================
export function PageLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-black">
      <div className="max-w-7xl mx-auto px-4 py-8 md:py-12">
        {/* Back button */}
        <button
          onClick={() => navigate('/', { state: { scrollTo: 'data' } })}
          className="group inline-flex items-center gap-2 text-xs tracking-wider mb-8 cursor-pointer bg-transparent border-none rounded-lg px-3 py-2 -ml-3 transition-all duration-300 hover:bg-[rgba(212,175,55,0.05)]"
          style={{ color: 'rgba(222,219,200,0.5)' }}
        >
          <ArrowLeft className="w-3.5 h-3.5 transition-all duration-300 group-hover:-translate-x-1" />
          <span className="transition-colors duration-300 group-hover:text-[#d4af37]">返回首页</span>
        </button>

        {/* Title with jade-dot */}
        <h1 className="text-3xl md:text-4xl font-medium mb-2 flex items-center" style={{ color: '#E1E0CC' }}>
          <span className="jade-dot" />
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm mb-8" style={{ color: 'rgba(212,175,55,0.5)' }}>
            {subtitle}
          </p>
        )}

        {/* Content */}
        {children}

        {/* Decorative footer */}
        <div className="decorative-line" />
      </div>
    </div>
  );
}

// ================== SectionTitle with jade-dot ==================
export function SectionTitle({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <h3 className={`section-title ${className}`}>
      <span className="jade-dot" />
      {children}
    </h3>
  );
}

// ================== LoadingState (Taichi spinner) ==================
export function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <div className="loading-taichi" />
      <span
        className="text-xs tracking-widest animate-pulse"
        style={{ color: 'rgba(222,219,200,0.4)' }}
      >
        加载中...
      </span>
    </div>
  );
}

// ================== ErrorState ==================
export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <AlertTriangle className="w-6 h-6" style={{ color: 'rgba(236,95,103,0.6)' }} />
      <p className="text-sm" style={{ color: 'rgba(236,95,103,0.7)' }}>
        加载失败: {message}
      </p>
    </div>
  );
}

// ================== EmptyState ==================
export function EmptyState({ message = '暂无数据' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center text-lg"
        style={{ background: 'rgba(212,175,55,0.05)', color: 'rgba(212,175,55,0.3)' }}
      >
        —
      </div>
      <p className="text-sm" style={{ color: 'rgba(222,219,200,0.4)' }}>
        {message}
      </p>
    </div>
  );
}

// ================== StatsCard ==================
export function StatsCard({ value, label, icon, color = '#E1E0CC' }: {
  value: string | number;
  label: string;
  icon?: React.ReactNode;
  color?: string;
}) {
  return (
    <div className="bg-[#101010] rounded-xl p-4 border border-white/5 text-center hover:border-[rgba(212,175,55,0.15)] transition-all duration-300">
      {icon && (
        <div className="flex justify-center mb-2" style={{ color: 'rgba(212,175,55,0.4)' }}>
          {icon}
        </div>
      )}
      <div className="text-xl font-bold" style={{ color }}>
        {value}
      </div>
      <div className="text-xs mt-1" style={{ color: 'rgba(222,219,200,0.4)' }}>
        {label}
      </div>
    </div>
  );
}

// ================== DataTable ==================
interface Column {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (val: unknown, row: Record<string, unknown>) => React.ReactNode;
}

export function DataTable({ columns, data }: { columns: Column[]; data: Record<string, unknown>[] }) {
  const [sortKey, setSortKey] = React.useState<string | null>(null);
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('asc');
  const [filteredData, setFilteredData] = React.useState(data);

  React.useEffect(() => { setFilteredData(data); }, [data]);

  const sorted = React.useMemo(() => {
    if (!sortKey) return filteredData;
    return [...filteredData].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'asc' ? av - bv : bv - av;
      return sortDir === 'asc'
        ? String(av).localeCompare(String(bv), 'zh')
        : String(bv).localeCompare(String(av), 'zh');
    });
  }, [filteredData, sortKey, sortDir]);

  if (!sorted.length) {
    return <EmptyState />;
  }

  const handleSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };

  return (
    <div className="overflow-x-auto rounded-xl border border-white/5 bg-[#0a0a0a] gold-glow">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
            {columns.map(col => (
              <th
                key={col.key}
                className={`px-4 py-3 text-left text-xs font-medium tracking-wider ${
                  col.sortable !== false ? 'cursor-pointer hover:opacity-80' : ''
                }`}
                style={{ color: 'rgba(222,219,200,0.65)' }}
                onClick={() => col.sortable !== false && handleSort(col.key)}
              >
                {col.label}
                {col.sortable !== false && sortKey === col.key && (
                  <span className="ml-1" style={{ color: '#d4af37' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={i}
              className="border-b border-white/5 last:border-0 transition-colors duration-150"
              style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}
            >
              {columns.map(col => (
                <td
                  key={col.key}
                  className="px-4 py-3 text-sm tabular-nums"
                  style={{ color: '#d3d7d4' }}
                >
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

// ================== RankBadge ==================
const RANK_CLASSES: Record<string, string> = {
  '人阶下品': 'rank-人阶', '人阶上品': 'rank-人阶',
  '黄阶下品': 'rank-黄阶', '黄阶上品': 'rank-黄阶',
  '玄阶下品': 'rank-玄阶', '玄阶上品': 'rank-玄阶',
  '地阶下品': 'rank-地阶', '地阶上品': 'rank-地阶',
  '天阶下品': 'rank-天阶', '天阶上品': 'rank-天阶',
  '仙阶下品': 'rank-仙阶', '仙阶上品': 'rank-仙阶',
  '仙阶极品': 'rank-仙阶', '无上': 'rank-无上',
  '无上仙法': 'rank-无上', '无上神通': 'rank-无上',
};

export function RankBadge({ rank }: { rank?: string }) {
  if (!rank) return null;
  const cls = Object.entries(RANK_CLASSES).find(([k]) => rank.startsWith(k))?.[1] || '';
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
      <span className="text-xs mr-1" style={{ color: 'rgba(222,219,200,0.4)' }}>品阶筛选：</span>
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
