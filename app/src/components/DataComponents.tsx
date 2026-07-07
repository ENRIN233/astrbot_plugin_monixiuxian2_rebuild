import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export function PageLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-black">
      <div className="max-w-7xl mx-auto px-4 py-8 md:py-12">
        {/* Back button */}
        <button
          onClick={() => navigate('/')}
          className="group inline-flex items-center gap-2 text-xs tracking-wider mb-8 cursor-pointer bg-transparent border-none"
          style={{ color: 'rgba(222,219,200,0.5)' }}
        >
          <ArrowLeft className="w-3.5 h-3.5 transition-transform duration-300 group-hover:-translate-x-1" />
          返回首页
        </button>

        {/* Title */}
        <h1 className="text-3xl md:text-4xl font-medium mb-2" style={{ color: '#E1E0CC' }}>
          {title}
        </h1>
        {subtitle && <p className="text-sm text-gray-500 mb-8">{subtitle}</p>}

        {/* Content */}
        {children}
      </div>
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="flex items-center justify-center py-24">
      <div className="w-8 h-8 border-2 border-white/10 border-t-primary rounded-full animate-spin" />
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="text-center py-16">
      <p className="text-sm text-gray-500">加载失败: {message}</p>
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
    return <div className="text-center py-12 text-sm text-gray-500">暂无数据</div>;
  }

  const handleSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };

  return (
    <div className="overflow-x-auto rounded-xl border border-white/5 bg-[#0a0a0a]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/5">
            {columns.map(col => (
              <th
                key={col.key}
                className={`px-4 py-3 text-left text-xs font-medium tracking-wider ${col.sortable !== false ? 'cursor-pointer hover:opacity-80' : ''}`}
                style={{ color: 'rgba(222,219,200,0.5)' }}
                onClick={() => col.sortable !== false && handleSort(col.key)}
              >
                {col.label}
                {col.sortable !== false && sortKey === col.key && (
                  <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02] transition-colors">
              {columns.map(col => (
                <td key={col.key} className="px-4 py-3 text-sm" style={{ color: '#d3d7d4' }}>
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
