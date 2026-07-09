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
  quality_rates: Record<string, number>;
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

export default function ForgingPage() {
  const { data, loading, error } = useGameData<Record<string, ForgingRecipe>>('forging_recipes');
  const [typeFilter, setTypeFilter] = useState<'全部' | 'weapon' | 'armor'>('全部');

  // 计算不同的品质配置档位
  const qualityProfiles = useMemo(() => {
    if (!data) return [];
    const seen = new Set<string>();
    const profiles: Array<{ label: string; rates: Record<string, number>; examples: string[] }> = [];
    for (const recipe of Object.values(data)) {
      const key = JSON.stringify(Object.entries(recipe.quality_rates).sort());
      if (!seen.has(key)) {
        seen.add(key);
        const ranks = Object.values(data)
          .filter(r => JSON.stringify(Object.entries(r.quality_rates).sort()) === key)
          .map(r => `${r.name}(需求${r.rank_required}级)`);
        profiles.push({
          label: Object.entries(recipe.quality_rates)
            .map(([k, v]) => `${k}${pct(v)}`)
            .join(' / '),
          rates: recipe.quality_rates,
          examples: ranks.slice(0, 3),
        });
      }
    }
    return profiles.sort((a, b) => {
      const aLow = a.rates['下品'] ?? 0;
      const bLow = b.rates['下品'] ?? 0;
      return bLow - aLow;
    });
  }, [data]);

  // 表格列定义
  const columns = [
    { key: 'recipeName', label: '配方名称' },
    { key: 'typeLabel', label: '类型' },
    { key: 'rankRequired', label: '需求等级' },
    { key: 'ingredients', label: '材料' },
    { key: 'output', label: '产出' },
    { key: 'forgeExp', label: '锻造经验' },
    { key: 'qualityRates', label: '品质概率', render: (_v: unknown, row: Record<string, unknown>) => {
      const rates = row._rates as Record<string, number>;
      if (!rates) return '-';
      return (
        <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {Object.entries(rates).map(([q, r]) => (
            <span key={q} style={{ color: QUALITY_COLORS[q] ?? '#aaa', fontSize: 12 }}>
              {q}{pct(r)}
            </span>
          ))}
        </span>
      );
    }},
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
        _rates: r.quality_rates,
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
        低阶配方基础概率为下品40%/中品35%/上品20%/极品5%，高阶配方极品率最高可达40%。
        锻造经验用于提升锻造等级，解锁更高级配方。
      </p>

      {/* 品质概率概况 */}
      <div className="section-title">
        <span className="jade-dot" />品质概率配置
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12, marginBottom: 32 }}>
        {qualityProfiles.map((profile, i) => (
          <div
            key={i}
            className="bg-[#0a0a0a] rounded-xl border border-white/5 p-4 hover:border-[rgba(212,175,55,0.15)] transition-all duration-300"
          >
            <div style={{ fontSize: 13, color: '#E1E0CC', fontWeight: 600, marginBottom: 8 }}>
              {profile.label}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {Object.entries(profile.rates).map(([q, r]) => {
                const gradePct = r * 100;
                return (
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
                );
              })}
            </div>
            <div style={{ fontSize: 11, color: 'rgba(222,219,200,0.3)', marginTop: 8 }}>
              {profile.examples.join('、')}
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
