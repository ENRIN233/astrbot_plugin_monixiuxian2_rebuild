import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Search, ChevronUp, X, Menu, X as XIcon, Moon, Sun } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

// ================== ThemeToggle ==================
function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      className="nav-link"
      onClick={toggle}
      aria-label={theme === 'dark' ? '切换浅色模式' : '切换深色模式'}
      style={{ fontSize: 13, gap: 6 }}
    >
      {theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
      <span className="hidden sm:inline">{theme === 'dark' ? '浅色' : '深色'}</span>
    </button>
  );
}

// ================== NavBar ==================
const NAV_ITEMS = [
  { path: '/levels', label: '境界' },
  { path: '/pills', label: '丹药' },
  { path: '/equipment', label: '装备' },
  { path: '/skills', label: '神通' },
  { path: '/boss', label: 'Boss' },
  { path: '/bounty', label: '悬赏' },
  { path: '/forging', label: '锻造' },
  { path: '/alchemy', label: '炼丹' },
  { path: '/roots', label: '灵根' },
  { path: '/combat', label: '战斗' },
  { path: '/sect', label: '宗门' },
  { path: '/changelog', label: '更新' },
];

function NavBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const currentPath = location.pathname;

  const handleNav = (path: string) => {
    navigate(path);
    setMobileOpen(false);
  };

  return (
    <>
      {/* Desktop: horizontal scrollable */}
      <div className="navbar desktop">
        {NAV_ITEMS.map((item, i) => (
          <span key={item.path} style={{ display: 'inline-flex', alignItems: 'center' }}>
            {i > 0 && <span className="nav-sep" />}
            <button
              className={`nav-link ${currentPath === item.path ? 'active' : ''}`}
              onClick={() => handleNav(item.path)}
            >
              {item.label}
            </button>
          </span>
        ))}
        <span className="nav-sep" />
        <ThemeToggle />
      </div>

      {/* Mobile: toggle + dropdown */}
      <div className="flex items-center gap-2 mb-3" style={{ display: 'none' }} /* controlled by CSS */>
        <button
          className="nav-mobile-toggle"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="导航菜单"
        >
          {mobileOpen ? <XIcon className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          <span className="text-xs tracking-wider">{mobileOpen ? '关闭' : '导航'}</span>
        </button>
        <span style={{ flex: 1 }} />
        <ThemeToggle />
      </div>
      <div className={`nav-mobile-panel ${mobileOpen ? 'open' : ''}`}>
        {NAV_ITEMS.map(item => (
          <button
            key={item.path}
            className={`nav-link ${currentPath === item.path ? 'active' : ''}`}
            onClick={() => handleNav(item.path)}
          >
            {item.label}
          </button>
        ))}
      </div>
    </>
  );
}

// ================== PageLayout ==================
export function PageLayout({ title, subtitle, children, pageId }: { title: string; subtitle?: string; children: React.ReactNode; pageId?: string }) {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-black page-enter">
      {pageId && <div className={`page-texture ${pageId}`} />}
      <div className="max-w-7xl mx-auto px-4 py-8 md:py-12">
        <NavBar />
        {/* Back button */}
        <button
          onClick={() => navigate('/', { state: { scrollTo: 'data' } })}
          className="group inline-flex items-center gap-2 text-xs tracking-wider mb-8 cursor-pointer bg-transparent border-none rounded-lg px-3 py-2 -ml-3 transition-all duration-300 hover:bg-[rgba(212,175,55,0.05)]"
          className="tc-med"
        >
          <ArrowLeft className="w-3.5 h-3.5 transition-all duration-300 group-hover:-translate-x-1" />
          <span className="transition-colors duration-300 group-hover:text-[#d4af37]">返回首页</span>
        </button>

        {/* Title with jade-dot */}
        <h1 className="text-3xl md:text-4xl font-medium mb-2 flex items-center tc-primary">
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
      <BackToTop />
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
      <span className="text-xs tracking-widest animate-pulse tc-dim">
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
      <p className="text-sm tc-dim">{message}</p>
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
    <div className="bg-card rounded-xl p-4 border border-white/5 text-center hover:border-[rgba(212,175,55,0.15)] transition-all duration-300">
      {icon && (
        <div className="flex justify-center mb-2" style={{ color: 'rgba(212,175,55,0.4)' }}>
          {icon}
        </div>
      )}
      <div className="text-xl font-bold" style={{ color }}>
        {value}
      </div>
      <div className="text-xs mt-1 tc-dim">{label}</div>
    </div>
  );
}

// ================== AnimatedStatsCard ==================
export function AnimatedStatsCard({ value, label, icon, color = '#E1E0CC', duration = 800 }: {
  value: number | string;
  label: string;
  icon?: React.ReactNode;
  color?: string;
  duration?: number;
}) {
  const [displayValue, setDisplayValue] = React.useState<string | number>(typeof value === 'number' ? 0 : value);
  const ref = React.useRef<HTMLDivElement>(null);
  const hasAnimated = React.useRef(false);

  React.useEffect(() => {
    if (typeof value !== 'number') return;
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          const target = value;
          const startTime = performance.now();

          const step = (now: number) => {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // easeOutQuad
            const eased = 1 - (1 - progress) * (1 - progress);
            const current = Math.round(eased * target);
            setDisplayValue(current);

            if (progress < 1) {
              requestAnimationFrame(step);
            } else {
              setDisplayValue(target);
            }
          };

          requestAnimationFrame(step);
          observer.disconnect();
        }
      },
      { threshold: 0.2 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [value, duration]);

  // Reset animation when value changes
  React.useEffect(() => {
    hasAnimated.current = false;
  }, [value]);

  return (
    <div ref={ref} className="bg-card rounded-xl p-4 border border-white/5 text-center hover:border-[rgba(212,175,55,0.15)] transition-all duration-300">
      {icon && (
        <div className="flex justify-center mb-2" style={{ color: 'rgba(212,175,55,0.4)' }}>
          {icon}
        </div>
      )}
      <div className="text-xl font-bold tabular-nums" style={{ color }}>
        {displayValue}
      </div>
      <div className="text-xs mt-1 tc-dim">{label}</div>
    </div>
  );
}

// ================== SearchBar ==================
export function SearchBar({ value, onChange, placeholder = '搜索...' }: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="relative flex-1 min-w-[160px] max-w-[280px]">
      <Search
        className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 pointer-events-none tc-faintest"
      />
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-surface border border-white/5 rounded-lg py-2 pl-9 pr-8 text-sm outline-none transition-all duration-200 tc-secondary"
        onFocus={e => { e.target.style.borderColor = 'rgba(212,175,55,0.4)'; e.target.style.boxShadow = '0 0 12px rgba(212,175,55,0.04)'; }}
        onBlur={e => { e.target.style.borderColor = 'rgba(255,255,255,0.05)'; e.target.style.boxShadow = 'none'; }}
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-2 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer p-0.5 rounded tc-faintest"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}

// ================== BackToTop ==================
function BackToTop() {
  const [visible, setVisible] = React.useState(false);

  useEffect(() => {
    const onScroll = () => {
      setVisible(window.scrollY > window.innerHeight);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <button
      className={`back-to-top ${visible ? 'visible' : ''}`}
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      aria-label="返回顶部"
    >
      <ChevronUp className="w-4 h-4" />
    </button>
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
    <div className="overflow-x-auto rounded-xl border border-white/5 bg-surface gold-glow">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
            {columns.map(col => (
              <th
                key={col.key}
                className={`px-4 py-3 text-left text-xs font-medium tracking-wider tc-faint ${
                  col.sortable !== false ? 'cursor-pointer hover:opacity-80' : ''
                }`}
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
                  className="px-4 py-3 text-sm tabular-nums tc-secondary"
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
      <span className="text-xs mr-1 tc-dim">品阶筛选：</span>
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
