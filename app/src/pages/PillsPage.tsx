import { useState, useMemo } from 'react';
import { useGameData } from '../hooks/useGameData';
import {
  PageLayout,
  LoadingState,
  ErrorState,
  DataTable,
  SubTabs,
  FilterBar,
  RankBadge,
  SearchBar,
} from '../components/DataComponents';

/** 突破丹（pills.json） */
interface BreakthroughPill {
  id: string;
  name: string;
  type: string;
  subtype: string;
  required_level_index: number;
  min_level_index: number;
  price: number;
  effect_type: string;
  max_uses: number;
  effect: { breakthrough_bonus?: number };
  target_level_index: number | null;
}

/** 功能丹（utility_pills.json） */
interface UtilityPill {
  id: string;
  name: string;
  rank: string;
  description?: string;
  subtype: string;
  required_level_index: number;
  price: number;
  effect_type: string;
  effect: {
    heal_hp_pct?: number;
    atk_bonus?: number;
    death_protection?: boolean;
  };
  shop_weight?: number;
  _source?: string;
  _source_id?: string;
}

/** 等级配置（用于映射 target_level_index → 名称） */
interface LevelConfig {
  name: string;
  exp_needed: number;
  success_rate: number;
  spend: number;
}

/** 功能丹 subtype → 中文标签 */
const SUBTYPE_LABELS: Record<string, string> = {
  healing: '回血丹',
  combat_boost: '永久攻击丹',
  death_protection: '死亡保护丹',
};

/** 格式化价格 */
function formatPrice(v: number): string {
  if (v >= 100000000) return (v / 100000000).toFixed(1) + '亿';
  if (v >= 10000) return (v / 10000).toFixed(v % 10000 === 0 ? 0 : 1) + '万';
  return v.toLocaleString();
}

export default function PillsPage() {
  const [activeTab, setActiveTab] = useState('breakthrough');
  const [utilityFilterRank, setUtilityFilterRank] = useState('全部');
  const [searchText, setSearchText] = useState('');

  const {
    data: rawPills,
    loading: pillsLoading,
    error: pillsError,
  } = useGameData<BreakthroughPill[]>('pills');

  const {
    data: rawUtils,
    loading: utilsLoading,
    error: utilsError,
  } = useGameData<UtilityPill[]>('utility_pills');

  const { data: levelData } = useGameData<LevelConfig[]>('level_config');

  /** 境界名称查找表 */
  const levelNames = useMemo(() => {
    if (!levelData) return [] as string[];
    return levelData.map((l) => l.name);
  }, [levelData]);

  const getLevelName = (idx: number | null): string => {
    if (idx === null) return '通用';
    if (idx < 0 || idx >= levelNames.length) return `Lv.${idx}`;
    return levelNames[idx];
  };

  const breakthroughPills = rawPills || [];
  const utilityPills = rawUtils || [];

  /** 突破丹 — 按名称搜索 */
  const filteredBreakthrough = useMemo(() => {
    if (!searchText) return breakthroughPills;
    return breakthroughPills.filter(p => p.name.includes(searchText));
  }, [breakthroughPills, searchText]);

  /** 功能丹可用品阶（目前只有"凡品"） */
  const availableRanks = useMemo(() => {
    const s = new Set(utilityPills.map((p) => p.rank).filter(Boolean));
    return [...s] as string[];
  }, [utilityPills]);

  /** 按品阶 + 名称过滤后的功能丹 */
  const filteredUtils = useMemo(() => {
    let list = utilityFilterRank === '全部' ? utilityPills : utilityPills.filter((p) => p.rank === utilityFilterRank);
    if (searchText) list = list.filter(p => p.name.includes(searchText));
    return list;
  }, [utilityPills, utilityFilterRank, searchText]);

  /** 按 subtype 分组 */
  const groupedUtils = useMemo(() => {
    const groups: Record<string, UtilityPill[]> = {};
    for (const p of filteredUtils) {
      if (!groups[p.subtype]) groups[p.subtype] = [];
      groups[p.subtype].push(p);
    }
    return groups;
  }, [filteredUtils]);

  /** 突破丹表头 */
  const breakthroughColumns = [
    { key: 'name', label: '名称' },
    { key: 'price', label: '价格', render: (_v: unknown, row: Record<string, unknown>) => formatPrice(row['price'] as number) },
    {
      key: 'target',
      label: '突破路径',
      sortable: true,
      render: (_v: unknown, row: Record<string, unknown>) =>
        getLevelName(row['target_level_index'] as number | null),
    },
    {
      key: 'bonus',
      label: '突破加成',
      sortable: true,
      render: (_v: unknown, row: Record<string, unknown>) => {
        const effect = row['effect'] as { breakthrough_bonus?: number } | undefined;
        if (!effect?.breakthrough_bonus) return '-';
        return `+${(effect.breakthrough_bonus * 100).toFixed(0)}%`;
      },
    },
    { key: 'max_uses', label: '最大使用次数', sortable: true },
  ];

  /** 功能丹表头 */
  const utilsColumns = [
    { key: 'name', label: '名称' },
    {
      key: 'effect_desc',
      label: '效果',
      sortable: false,
      render: (_v: unknown, row: Record<string, unknown>) => {
        const effect = row['effect'] as Record<string, unknown>;
        const subtype = row['subtype'] as string;
        if (subtype === 'healing') {
          const pct = (effect['heal_hp_pct'] as number) * 100;
          return `回复 ${pct.toFixed(0)}% 血量`;
        }
        if (subtype === 'combat_boost') {
          return `永久 +${effect['atk_bonus']} 攻击力`;
        }
        if (subtype === 'death_protection') {
          return '突破失败不扣修为';
        }
        return '-';
      },
    },
    {
      key: 'required_level_index',
      label: '需求境界',
      sortable: true,
      render: (v: unknown) => getLevelName(v as number | null),
    },
  ];

  if (pillsLoading || utilsLoading) {
    return (
      <PageLayout title="丹药大全">
        <LoadingState />
      </PageLayout>
    );
  }

  if (pillsError || utilsError) {
    return (
      <PageLayout title="丹药大全">
        <ErrorState message={pillsError || utilsError || '加载失败'} />
      </PageLayout>
    );
  }

  return (
    <PageLayout title="丹药大全" pageId="pills" subtitle="突破丹、修为丹、功能丹完整数据">
      <SubTabs
        tabs={[
          { key: 'breakthrough', label: '突破丹', count: breakthroughPills.length },
          { key: 'cultivation', label: '修为丹', count: 0 },
          { key: 'utility', label: '功能丹', count: utilityPills.length },
        ]}
        active={activeTab}
        onChange={setActiveTab}
      />

      <div className="flex flex-col sm:flex-row gap-3 mb-6 items-start sm:items-center">
        <SearchBar value={searchText} onChange={setSearchText} placeholder="搜索丹药名称..." />
      </div>

      {/* ===== 突破丹 ===== */}
      {activeTab === 'breakthrough' && (
        <>
          <p className="info-box">
            突破丹用于提升突破特定境界的成功率，有使用次数限制。
            部分丹药仅在大境界突破（如练气→化灵）时有效，通用丹药（太清玉液丹等）可用于合体境以上的任何突破。
          </p>
          <DataTable
            columns={breakthroughColumns}
            data={filteredBreakthrough as unknown as Record<string, unknown>[]}
          />
        </>
      )}

      {/* ===== 修为丹 ===== */}
      {activeTab === 'cultivation' && (
        <div className="text-center py-16">
          <p className="text-sm" style={{ color: 'rgba(222,219,200,0.4)' }}>
            暂无修为丹数据
          </p>
        </div>
      )}

      {/* ===== 功能丹 ===== */}
      {activeTab === 'utility' && (
        <>
          <p className="info-box">
            功能丹分为回血丹、永久攻击丹和死亡保护丹三类，可通过炼丹系统或直接购买获得。
          </p>
          <FilterBar
            ranks={availableRanks}
            activeRank={utilityFilterRank}
            onChange={setUtilityFilterRank}
          />
          {Object.entries(groupedUtils).length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm" style={{ color: 'rgba(222,219,200,0.4)' }}>
                暂无数据
              </p>
            </div>
          ) : (
            Object.entries(groupedUtils).map(([subtype, pills]) => (
              <div key={subtype} className="mb-10">
                <h3 className="section-title">
                  {SUBTYPE_LABELS[subtype] || subtype}
                  <span className="text-xs font-normal" style={{ color: 'rgba(222,219,200,0.4)' }}>
                    {pills.length} 种
                  </span>
                </h3>
                <DataTable
                  columns={utilsColumns}
                  data={pills as unknown as Record<string, unknown>[]}
                />
              </div>
            ))
          )}
        </>
      )}
    </PageLayout>
  );
}
