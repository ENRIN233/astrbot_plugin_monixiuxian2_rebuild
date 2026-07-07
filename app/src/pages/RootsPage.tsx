
import { PageLayout, LoadingState, ErrorState } from '../components/DataComponents';
import { useState, useMemo } from "react";
import { useGameData } from '../hooks/useGameData';

// ================== Types ==================
interface SpiritualRootEntry {
  rarity: string;
  roots: string[];
  speed: number;
  speed_display: string;
  weight: number;
  total_weight: number;
  probability: string;
  description: string;
}

const RARITY_COLORS: Record<string, { bg: string; border: string; text: string; accent: string }> = {
  '凡品': { bg: 'from-gray-900/50 to-gray-950/50', border: 'border-gray-700/40', text: '#9ca3af', accent: '#6b7280' },
  '下品': { bg: 'from-green-950/30 to-green-900/20', border: 'border-green-700/30', text: '#4ade80', accent: '#22c55e' },
  '中品': { bg: 'from-blue-950/30 to-blue-900/20', border: 'border-blue-700/30', text: '#60a5fa', accent: '#3b82f6' },
  '上品': { bg: 'from-purple-950/30 to-purple-900/20', border: 'border-purple-700/30', text: '#c084fc', accent: '#a855f7' },
  '极品': { bg: 'from-yellow-950/30 to-yellow-900/20', border: 'border-yellow-700/30', text: '#fbbf24', accent: '#eab308' },
  '仙品': { bg: 'from-cyan-950/30 to-cyan-900/20', border: 'border-cyan-700/30', text: '#22d3ee', accent: '#06b6d4' },
  '神品': { bg: 'from-orange-950/30 to-orange-900/20', border: 'border-orange-700/30', text: '#fb923c', accent: '#f97316' },
  '传说': { bg: 'from-red-950/30 to-red-900/20', border: 'border-red-700/30', text: '#f87171', accent: '#ef4444' },
  '神话': { bg: 'from-fuchsia-950/30 to-fuchsia-900/20', border: 'border-fuchsia-700/30', text: '#e879f9', accent: '#d946ef' },
  '禁忌': { bg: 'from-slate-950/50 to-slate-900/40', border: 'border-slate-600/40', text: '#94a3b8', accent: '#64748b' },
  '超越': { bg: 'from-white/5 to-white/[0.02]', border: 'border-white/20', text: '#ffffff', accent: '#e2e8f0' },
};

function RarityDetailCard({ entry, index }: { entry: SpiritualRootEntry; index: number }) {
  const colors = RARITY_COLORS[entry.rarity] || RARITY_COLORS['凡品'];
  const [expanded, setExpanded] = useState(false);
  const MAX_VISIBLE_ROOTS = 6;

  return (
    <div
      className={`bg-gradient-to-br ${colors.bg} rounded-xl border ${colors.border} p-5 md:p-6 transition-all duration-300 hover:border-white/20`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: colors.accent }}
          />
          <h3 className="text-base font-semibold" style={{ color: colors.text }}>
            {entry.rarity}
          </h3>
        </div>
        <div className="text-xs font-mono tabular-nums" style={{ color: 'rgba(222,219,200,0.4)' }}>
          {entry.probability}
        </div>
      </div>

      {/* Speed & probability row */}
      <div className="flex gap-4 mb-3 text-xs">
        <span className="inline-flex items-center gap-1.5 rounded-md px-2 py-1" style={{ background: 'rgba(222,219,200,0.05)', color: colors.accent }}>
          修炼速度 <strong>{entry.speed_display}</strong>
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-md px-2 py-1" style={{ background: 'rgba(222,219,200,0.05)', color: 'rgba(222,219,200,0.6)' }}>
          权重 <strong>{entry.weight}</strong>
        </span>
      </div>

      {/* Roots */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {(expanded ? entry.roots : entry.roots.slice(0, MAX_VISIBLE_ROOTS)).map((root, ri) => (
          <span
            key={ri}
            className="inline-block text-xs px-2.5 py-1 rounded-md"
            style={{
              background: `rgba(${index * 20}, ${100 + index * 10}, ${200 - index * 15}, 0.08)`,
              color: colors.text,
              border: `1px solid rgba(${index * 20}, ${100 + index * 10}, ${200 - index * 15}, 0.15)`,
            }}
          >
            {root}
          </span>
        ))}
        {entry.roots.length > MAX_VISIBLE_ROOTS && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs px-2 py-1 rounded-md cursor-pointer bg-transparent border-none"
            style={{ color: 'rgba(222,219,200,0.4)' }}
          >
            {expanded ? '收起' : `+${entry.roots.length - MAX_VISIBLE_ROOTS}`}
          </button>
        )}
      </div>

      {/* Description */}
      <p className="text-xs leading-relaxed m-0" style={{ color: 'rgba(222,219,200,0.5)' }}>
        {entry.description}
      </p>
    </div>
  );
}

export default function RootsPage() {
  const { data, loading, error } = useGameData<SpiritualRootEntry[]>('spiritual_roots');

  const sorted = useMemo(() => {
    if (!data) return [];
    const rarityOrder = ['凡品', '下品', '中品', '上品', '极品', '仙品', '神品', '传说', '神话', '禁忌', '超越'];
    return [...data].sort(
      (a, b) => rarityOrder.indexOf(a.rarity) - rarityOrder.indexOf(b.rarity)
    );
  }, [data]);

  if (loading) return <PageLayout title="灵根系统"><LoadingState /></PageLayout>;
  if (error) return <PageLayout title="灵根系统"><ErrorState message={error} /></PageLayout>;

  return (
    <PageLayout title="灵根系统" subtitle="灵根决定修炼速率，共11个品阶">
      {/* Overview stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <div className="bg-[#101010] rounded-xl p-4 border border-white/5 text-center">
          <div className="text-xl font-bold" style={{ color: '#E1E0CC' }}>{sorted.length}</div>
          <div className="text-xs text-gray-500 mt-1">品阶等级</div>
        </div>
        <div className="bg-[#101010] rounded-xl p-4 border border-white/5 text-center">
          <div className="text-xl font-bold" style={{ color: '#E1E0CC' }}>
            {sorted.reduce((sum, r) => sum + r.roots.length, 0)}
          </div>
          <div className="text-xs text-gray-500 mt-1">灵根种类</div>
        </div>
        <div className="bg-[#101010] rounded-xl p-4 border border-white/5 text-center">
          <div className="text-xl font-bold" style={{ color: '#E1E0CC' }}>
            {sorted.reduce((sum, r) => sum + r.total_weight, 0)}
          </div>
          <div className="text-xs text-gray-500 mt-1">总权重</div>
        </div>
        <div className="bg-[#101010] rounded-xl p-4 border border-white/5 text-center">
          <div className="text-xl font-bold" style={{ color: '#99c794' }}>×{Math.max(...sorted.map(r => r.speed))}</div>
          <div className="text-xs text-gray-500 mt-1">最高倍率</div>
        </div>
      </div>

      {/* Summary table */}
      <div className="overflow-x-auto rounded-xl border border-white/5 bg-[#0a0a0a] mb-8">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5">
              <th className="px-4 py-3 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>品阶</th>
              <th className="px-4 py-3 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>灵根数</th>
              <th className="px-4 py-3 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>速度倍率</th>
              <th className="px-4 py-3 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>权重</th>
              <th className="px-4 py-3 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>概率</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((entry) => (
              <tr key={entry.rarity} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02] transition-colors">
                <td className="px-4 py-3 text-sm font-medium" style={{ color: (RARITY_COLORS[entry.rarity] || {}).text || '#E1E0CC' }}>
                  {entry.rarity}
                </td>
                <td className="px-4 py-3 text-sm" style={{ color: '#d3d7d4' }}>{entry.roots.length}</td>
                <td className="px-4 py-3 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{entry.speed_display}</td>
                <td className="px-4 py-3 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{entry.weight}</td>
                <td className="px-4 py-3 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{entry.probability}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Detail cards */}
      <h2 className="section-title">品阶详情</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sorted.map((entry, i) => (
          <RarityDetailCard key={entry.rarity} entry={entry} index={i} />
        ))}
      </div>

      {/* Distribution section */}
      <div className="mt-8 bg-[#0a0a0a] rounded-xl border border-white/5 p-6">
        <h3 className="text-sm font-semibold mb-4" style={{ color: '#E1E0CC' }}>权重分布</h3>
        <div className="space-y-3">
          {sorted.map((entry) => {
            const totalWeight = sorted.reduce((s, r) => s + r.total_weight, 0);
            const pct = ((entry.total_weight / totalWeight) * 100).toFixed(2);
            const colors = RARITY_COLORS[entry.rarity] || RARITY_COLORS['凡品'];
            return (
              <div key={entry.rarity} className="flex items-center gap-3">
                <span className="text-xs w-10 shrink-0" style={{ color: colors.text }}>{entry.rarity}</span>
                <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${pct}%`,
                      background: `linear-gradient(90deg, ${colors.accent}44, ${colors.accent})`,
                    }}
                  />
                </div>
                <span className="text-xs tabular-nums w-16 text-right" style={{ color: 'rgba(222,219,200,0.5)' }}>
                  {pct}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </PageLayout>
  );
}
