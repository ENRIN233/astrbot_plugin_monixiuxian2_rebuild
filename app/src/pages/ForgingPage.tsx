import { useState, useMemo } from 'react';
import { useGameData } from '../hooks/useGameData';
import { PageLayout, LoadingState, ErrorState, DataTable } from '../components/DataComponents';

/** 锻造配方 */
interface ForgingRecipe {
  name: string;
  rank_required: number;
  ingredients: Record<string, number>;
  output_template: string;
  output_type: string;
  forge_exp: number;
}

/** 将百分数格式化 */
function pct(v: number): string {
  return (v * 100).toFixed(0) + '%';
}

/** 渲染材料列表 */
function renderIngredients(ing: Record<string, number>): string {
  return Object.entries(ing)
    .map(([name, qty]) => `${name}x${qty}`)
    .join(', ');
}

/** 品质颜色映射 */
const QUALITY_COLORS: Record<string, string> = {
  '下品': 'rgba(138,140,142,0.8)',
  '中品': 'rgba(22,169,81,0.8)',
  '上品': 'rgba(240,75,34,0.8)',
  '极品': 'rgba(234,203,44,0.9)',
};

/** 品质概率档位：按玩家锻造等级分段，与 core/forging_manager.py 的 QUALITY_RATES_TIERS 保持一致 */
const QUALITY_TIERS: Array<{ level: string; rates: Record<string, number> }> = [
  { level: '锻造等级 Lv.1-10', rates: { 下品: 0.40, 中品: 0.35, 上品: 0.20, 极品: 0.05 } },
  { level: '锻造等级 Lv.11-20', rates: { 下品: 0.30, 中品: 0.35, 上品: 0.25, 极品: 0.10 } },
  { level: '锻造等级 Lv.21-30', rates: { 下品: 0.25, 中品: 0.30, 上品: 0.30, 极品: 0.15 } },
  { level: '锻造等级 Lv.31-40', rates: { 下品: 0.20, 中品: 0.30, 上品: 0.30, 极品: 0.20 } },
  { level: '锻造等级 Lv.41-50', rates: { 下品: 0.15, 中品: 0.25, 上品: 0.30, 极品: 0.30 } },
  { level: '锻造等级 Lv.51+', rates: { 下品: 0.10, 中品: 0.20, 上品: 0.30, 极品: 0.40 } },
];

export default function ForgingPage() {
  const { data, loading, error } = useGameData<Record<string, ForgingRecipe>>('forging_recipes');
  const [typeFilter, setTypeFilter] = useState<'全部' | 'weapon' | 'armor'>('全部');

  // 表格列定义
  const columns = [
    { key: 'recipeName', label: '配方名称' },
    { key: 'typeLabel', label: '类型' },
    { key: 'rankRequired', label: '需求等级' },
    { key: 'ingredients', label: '材料' },
    { key: 'output', label: '产出' },
    { key: 'forgeExp', label: '锻造经验' },
  ];

  // 过滤 + 排序后的数据行
  const rows = useMemo(() => {
    if (!data) return [];
    const entries = Object.values(data);
    const filtered = typeFilter === '全部' ? entries : entries.filter(r => r.output_type === typeFilter);
    return filtered
      .sort((a, b) => a.rank_required - b.rank_required)
      .map(r => ({
        recipeName: r.name,
        typeLabel: r.output_type === 'weapon' ? '武器' : '防具',
        rankRequired: r.rank_required,
        ingredients: renderIngredients(r.ingredients),
        output: r.output_template,
        forgeExp: r.forge_exp,
      }));
  }, [data, typeFilter]);

  if (loading) {
    return (
      <PageLayout title="装备锻造">
        <LoadingState />
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout title="装备锻造">
        <ErrorState message={error} />
      </PageLayout>
    );
  }

  return (
    <PageLayout title="装备锻造" pageId="forging" subtitle={`共 ${data ? Object.keys(data).length : 0} 个锻造配方`}>
      <p className="info-box">
        锻造系统通过收集材料打造装备，产出随机品质（下品/中品/上品/极品）。
        品质概率由玩家锻造等级决定（各配方共用同一档表）：Lv.1 时为下品40%/中品35%/上品20%/极品5%，Lv.51 起极品率可达 40%。
        锻造经验用于提升锻造等级，解锁更高级配方。
      </p>

      {/* 品质概率概况（按锻造等级档表，与 core/forging_manager.py QUALITY_RATES_TIERS 一致） */}
      <div className="section-title">
        <span className="jade-dot" />品质概率（按锻造等级）
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12, marginBottom: 32 }}>
        {QUALITY_TIERS.map((profile) => (
          <div
            key={profile.level}
            className="bg-surface rounded-xl border border-white/5 p-4 hover:border-[rgba(212,175,55,0.15)] transition-all duration-300"
          >
            <div style={{ fontSize: 13, color: '#E1E0CC', fontWeight: 600, marginBottom: 8 }}>
              {profile.level}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {Object.entries(profile.rates).map(([q, r]) => (
                <div
                  key={q}
                  className="flex-1 rounded-lg text-center p-2"
                  style={{
                    background: `linear-gradient(180deg, ${QUALITY_COLORS[q] ?? '#aaa'}22 0%, transparent 100%)`,
                    border: `1px solid ${QUALITY_COLORS[q] ?? '#aaa'}22`,
                  }}
                >
                  <div style={{ fontSize: 16, fontWeight: 700, color: QUALITY_COLORS[q] ?? '#aaa' }}>{pct(r)}</div>
                  <div style={{ fontSize: 11, color: 'rgba(222,219,200,0.4)', marginTop: 2 }}>{q}</div>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 11, color: 'rgba(222,219,200,0.3)', marginTop: 8 }}>
              对全部配方生效
            </div>
          </div>
        ))}
      </div>

      {/* 锻造配方表 */}
      <h3 className="section-title">锻造配方</h3>

      {/* 类型筛选 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['全部', 'weapon', 'armor'] as const).map(t => (
          <button
            key={t}
            className={`sub-tab ${typeFilter === t ? 'active' : ''}`}
            onClick={() => setTypeFilter(t)}
            style={{ padding: '6px 16px', fontSize: 13 }}
          >
            {t === '全部' ? '全部' : t === 'weapon' ? '武器' : '防具'}
            <span style={{ color: 'rgba(222,219,200,0.3)', marginLeft: 4 }}>
              ({t === '全部' ? (data ? Object.keys(data).length : 0) : data ? Object.values(data).filter(r => r.output_type === t).length : 0})
            </span>
          </button>
        ))}
      </div>

      <DataTable columns={columns} data={rows as unknown as Record<string, unknown>[]} />
    </PageLayout>
  );
}
