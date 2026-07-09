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

interface WeaponItem {
  id: string;
  name: string;
  type: 'weapon' | 'armor';
  rank: string;
  required_level_index: number;
  price: number;
  description?: string;
  atk_bonus?: number;
  crit_rate?: number;
  crit_damage?: number;
  damage_reduction?: number;
  def_buff?: number;
}

interface TechniqueItem {
  id: number;
  name: string;
  type: string;
  rank: string;
  required_level_index: number;
  price: number;
  description?: string;
  exp_multiplier: number;
  breakthrough_bonus?: number;
  atk_bonus?: number;
  hp_bonus?: number;
  mp_bonus?: number;
  crit_rate?: number;
  crit_damage?: number;
  closing_exp_bonus?: number;
  closing_recovery_bonus?: number;
  harvest_bonus?: number;
  alchemy_exp_bonus?: number;
  alchemy_count_bonus?: number;
  dual_cultivation_bonus?: number;
  damage_reduction?: number;
  breakthrough_number?: number;
}

interface StorageRing {
  name: string;
  type: string;
  rank: string;
  description: string;
  capacity: number;
  required_level_index: number;
  price: number;
}

interface LevelConfig {
  name: string;
  exp_needed: number;
  success_rate: number;
  spend: number;
}

function formatPrice(v: number): string {
  if (v >= 100000000) return (v / 100000000).toFixed(1) + '亿';
  if (v >= 10000) return (v / 10000).toFixed(v % 10000 === 0 ? 0 : 1) + '万';
  return v.toLocaleString();
}

/** 渲染百分比值（乘以 100 显示） */
function pct(v: number | undefined | null, decimals = 1): string {
  if (v === undefined || v === null) return '-';
  return (v * 100).toFixed(decimals) + '%';
}

/** 渲染数值（显示原始值） */
function val(v: number | undefined | null): string {
  if (v === undefined || v === null) return '-';
  return String(v);
}

export default function EquipmentPage() {
  const [activeTab, setActiveTab] = useState('weapons');
  const [weaponFilterRank, setWeaponFilterRank] = useState('全部');
  const [techniqueFilterRank, setTechniqueFilterRank] = useState('全部');
  const [searchText, setSearchText] = useState('');

  const { data: rawWeapons, loading: weaponsLoading, error: weaponsError } =
    useGameData<WeaponItem[]>('weapons');
  const { data: rawItems, loading: itemsLoading, error: itemsError } =
    useGameData<Record<string, TechniqueItem>>('items');
  const { data: rawRings, loading: ringsLoading, error: ringsError } =
    useGameData<Record<string, StorageRing>>('storage_rings');
  const { data: levelData } = useGameData<LevelConfig[]>('level_config');

  const levelNames = useMemo(() => {
    if (!levelData) return [];
    return levelData.map((l) => l.name);
  }, [levelData]);

  const getLevelName = (idx: number): string => {
    if (idx < 0 || idx >= levelNames.length) return `Lv.${idx}`;
    return levelNames[idx];
  };

  const weapons = rawWeapons || [];
  const itemsObj = rawItems || {};
  const ringsObj = rawRings || {};

  // === Derived data ===
  const weaponList = useMemo(() => weapons.filter((w) => w.type === 'weapon'), [weapons]);
  const armorList = useMemo(() => weapons.filter((w) => w.type === 'armor'), [weapons]);

  const techniqueList = useMemo(() => {
    return Object.values(itemsObj).filter((i) => i.type === 'main_technique');
  }, [itemsObj]);

  const ringList = useMemo(() => Object.values(ringsObj), [ringsObj]);

  // === Rank filters ===
  const weaponRanks = useMemo(() => {
    const s = new Set(weaponList.map((w) => w.rank));
    return [...s] as string[];
  }, [weaponList]);

  const armorRanks = useMemo(() => {
    const s = new Set(armorList.map((a) => a.rank));
    return [...s] as string[];
  }, [armorList]);

  const techniqueRanks = useMemo(() => {
    const s = new Set(techniqueList.map((t) => t.rank));
    return [...s] as string[];
  }, [techniqueList]);

  const filteredWeapons = useMemo(() => {
    let list = weaponFilterRank === '全部' ? weaponList : weaponList.filter((w) => w.rank === weaponFilterRank);
    if (searchText) list = list.filter(w => w.name.includes(searchText));
    return list;
  }, [weaponList, weaponFilterRank, searchText]);

  const filteredArmor = useMemo(() => {
    let list = weaponFilterRank === '全部' ? armorList : armorList.filter((a) => a.rank === weaponFilterRank);
    if (searchText) list = list.filter(a => a.name.includes(searchText));
    return list;
  }, [armorList, weaponFilterRank, searchText]);

  const filteredTechniques = useMemo(() => {
    let list = techniqueFilterRank === '全部' ? techniqueList : techniqueList.filter((t) => t.rank === techniqueFilterRank);
    if (searchText) list = list.filter(t => t.name.includes(searchText));
    return list;
  }, [techniqueList, techniqueFilterRank, searchText]);

  // === Columns ===
  const weaponColumns = [
    { key: 'name', label: '名称' },
    {
      key: 'rank',
      label: '品阶',
      render: (v: unknown) => <RankBadge rank={v as string} />,
    },
    {
      key: 'required_level_index',
      label: '需求境界',
      render: (v: unknown) => getLevelName(v as number),
    },
    {
      key: 'price',
      label: '价格',
      render: (_v: unknown, row: Record<string, unknown>) => formatPrice(row['price'] as number),
    },
    {
      key: 'atk_bonus',
      label: '攻击%',
      render: (v: unknown) => pct(v as number),
    },
    {
      key: 'crit_rate',
      label: '暴击率',
      render: (v: unknown) => `${val(v as number)}%`,
    },
    {
      key: 'crit_damage',
      label: '暴击伤害',
      render: (v: unknown) => {
        const n = v as number;
        if (n === undefined || n === null) return '-';
        return n >= 0 ? `+${n.toFixed(2)}` : n.toFixed(2);
      },
    },
    {
      key: 'damage_reduction',
      label: '减伤',
      render: (v: unknown) => pct(v as number),
    },
  ];

  const armorColumns = [
    { key: 'name', label: '名称' },
    {
      key: 'rank',
      label: '品阶',
      render: (v: unknown) => <RankBadge rank={v as string} />,
    },
    {
      key: 'required_level_index',
      label: '需求境界',
      render: (v: unknown) => getLevelName(v as number),
    },
    {
      key: 'price',
      label: '价格',
      render: (_v: unknown, row: Record<string, unknown>) => formatPrice(row['price'] as number),
    },
    {
      key: 'def_buff',
      label: '防御%',
      render: (v: unknown) => pct(v as number),
    },
    {
      key: 'atk_bonus',
      label: '攻击%',
      render: (v: unknown) => pct(v as number),
    },
    {
      key: 'crit_rate',
      label: '暴击率',
      render: (v: unknown) => {
        const n = v as number;
        if (n === undefined || n === null) return '-';
        return `${n}%`;
      },
    },
  ];

  const techniqueColumns = [
    { key: 'name', label: '名称' },
    {
      key: 'rank',
      label: '品阶',
      render: (v: unknown) => <RankBadge rank={v as string} />,
    },
    {
      key: 'required_level_index',
      label: '需求境界',
      render: (v: unknown) => getLevelName(v as number),
    },
    { key: 'exp_multiplier', label: '经验倍率', render: (v: unknown) => `${val(v as number)}x` },
    {
      key: 'atk_bonus',
      label: '攻击力%',
      render: (v: unknown) => pct(v as number),
    },
    {
      key: 'hp_bonus',
      label: '生命值%',
      render: (v: unknown) => pct(v as number),
    },
    {
      key: 'mp_bonus',
      label: '真元%',
      render: (v: unknown) => pct(v as number),
    },
    {
      key: 'breakthrough_bonus',
      label: '突破概率',
      render: (v: unknown) => pct(v as number),
    },
    {
      key: 'crit_rate',
      label: '暴击率',
      render: (v: unknown) => {
        const n = v as number;
        if (n === undefined || n === null) return '-';
        return `${n}%`;
      },
    },
    {
      key: 'crit_damage',
      label: '暴伤',
      render: (v: unknown) => {
        const n = v as number;
        if (n === undefined || n === null) return '-';
        return n >= 0 ? `+${n.toFixed(2)}` : n.toFixed(2);
      },
    },
    {
      key: 'price',
      label: '价格',
      render: (_v: unknown, row: Record<string, unknown>) => formatPrice(row['price'] as number),
    },
  ];

  const ringColumns = [
    { key: 'name', label: '名称' },
    {
      key: 'rank',
      label: '品阶',
      render: (v: unknown) => <RankBadge rank={v as string} />,
    },
    {
      key: 'capacity',
      label: '容量',
      sortable: true,
      render: (v: unknown) => <span style={{ color: '#99c794' }}>{val(v as number)}</span>,
    },
    {
      key: 'required_level_index',
      label: '需求境界',
      render: (v: unknown) => getLevelName(v as number),
    },
    {
      key: 'price',
      label: '价格',
      render: (_v: unknown, row: Record<string, unknown>) => formatPrice(row['price'] as number),
    },
  ];

  const isLoading = weaponsLoading || itemsLoading || ringsLoading;
  const hasError = weaponsError || itemsError || ringsError;

  if (isLoading) {
    return (
      <PageLayout title="装备大全">
        <LoadingState />
      </PageLayout>
    );
  }

  if (hasError) {
    return (
      <PageLayout title="装备大全">
        <ErrorState message={hasError} />
      </PageLayout>
    );
  }

  return (
    <PageLayout title="装备大全" pageId="equipment" subtitle="武器、防具、心法与储物戒完整数据">
      <SubTabs
        tabs={[
          { key: 'weapons', label: '武器防具', count: weaponList.length + armorList.length },
          { key: 'techniques', label: '主修心法', count: techniqueList.length },
          { key: 'rings', label: '储物戒', count: ringList.length },
        ]}
        active={activeTab}
        onChange={setActiveTab}
      />

      {/* ===== 武器防具 ===== */}
      {activeTab === 'weapons' && (
        <>
          <p className="info-box">
            武器提供攻击加成、暴击等属性；防具提供防御减伤。部分高级装备附带减伤或攻击加成效果。
          </p>
          <div className="flex flex-col sm:flex-row gap-3 mb-6 items-start sm:items-center">
            <FilterBar
              ranks={[...new Set([...weaponRanks, ...armorRanks])]}
              activeRank={weaponFilterRank}
              onChange={setWeaponFilterRank}
            />
            <SearchBar value={searchText} onChange={setSearchText} placeholder="搜索装备名称..." />
          </div>

          {/* Weapon table */}
          {filteredWeapons.length > 0 && (
            <div className="mb-8">
              <h3 className="section-title">
                武器
                <span className="text-xs font-normal ml-2" style={{ color: 'rgba(222,219,200,0.4)' }}>
                  {filteredWeapons.length} 件
                </span>
              </h3>
              <DataTable columns={weaponColumns} data={filteredWeapons as unknown as Record<string, unknown>[]} />
            </div>
          )}

          {/* Armor table */}
          {filteredArmor.length > 0 && (
            <div>
              <h3 className="section-title">
                防具
                <span className="text-xs font-normal ml-2" style={{ color: 'rgba(222,219,200,0.4)' }}>
                  {filteredArmor.length} 件
                </span>
              </h3>
              <DataTable columns={armorColumns} data={filteredArmor as unknown as Record<string, unknown>[]} />
            </div>
          )}

          {filteredWeapons.length === 0 && filteredArmor.length === 0 && (
            <div className="text-center py-12">
              <p className="text-sm" style={{ color: 'rgba(222,219,200,0.4)' }}>暂无数据</p>
            </div>
          )}
        </>
      )}

      {/* ===== 主修心法 ===== */}
      {activeTab === 'techniques' && (
        <>
          <p className="info-box">
            心法（功法）是修炼的核心，提供修炼速度、战斗属性和各种功能加成。品质从人阶下品到无上仙法共14个品阶。
            79种心法各有侧重，包括修炼型、战斗型、炼丹型和综合型。
          </p>
          <div className="flex flex-col sm:flex-row gap-3 mb-6 items-start sm:items-center">
            <FilterBar
              ranks={techniqueRanks}
              activeRank={techniqueFilterRank}
              onChange={setTechniqueFilterRank}
            />
            <SearchBar value={searchText} onChange={setSearchText} placeholder="搜索心法名称..." />
          </div>
          <DataTable columns={techniqueColumns} data={filteredTechniques as unknown as Record<string, unknown>[]} />
        </>
      )}

      {/* ===== 储物戒 ===== */}
      {activeTab === 'rings' && (
        <>
          <p className="info-box">
            储物戒提供物品存储空间，容量从20到999不等。高品阶储物戒需求更高境界才能使用。
          </p>
          <DataTable columns={ringColumns} data={ringList as unknown as Record<string, unknown>[]} />
        </>
      )}
    </PageLayout>
  );
}
