import { useState, useMemo } from 'react';
import { useGameData } from '../hooks/useGameData';
import {
  PageLayout,
  LoadingState,
  ErrorState,
  DataTable,
  SubTabs,
  RankBadge,
  SearchBar,
} from '../components/DataComponents';

interface SkillBase {
  name: string;
  skill_type: number;
  hpcost: number;
  mpcost: number;
  turncost: number;
  rate: number;
  rank: string;
  required_level_index: number;
  desc: string;
  price: number;
  shop_weight: number;
}

interface AttackSkill extends SkillBase {
  skill_type: 1;
  atkvalue: number[];
}

interface ContinuousSkill extends SkillBase {
  skill_type: 2;
  atkvalue: number;
  dot_turns: number;
}

interface BuffSkill extends SkillBase {
  skill_type: 3;
  bufftype: number;
  buffvalue: number;
}

interface ControlSkill extends SkillBase {
  skill_type: 4;
  success: number;
}

type Skill = AttackSkill | ContinuousSkill | BuffSkill | ControlSkill;

interface LevelConfig {
  name: string;
  exp_needed: number;
  success_rate: number;
  spend: number;
}

/** 返回 MP消耗 百分比格式 */
function mpcostStr(v: number): string {
  return (v * 100).toFixed(0) + '%';
}

/** 触发率 */
function rateStr(v: number): string {
  return v + '%';
}

export default function SkillsPage() {
  const [activeTab, setActiveTab] = useState('1');
  const [searchText, setSearchText] = useState('');

  const { data: rawSkills, loading, error } = useGameData<Record<string, Skill>>('skills');
  const { data: levelData } = useGameData<LevelConfig[]>('level_config');

  const levelNames = useMemo(() => {
    if (!levelData) return [];
    return levelData.map((l) => l.name);
  }, [levelData]);

  const getLevelName = (idx: number): string => {
    if (idx < 0 || idx >= levelNames.length) return `Lv.${idx}`;
    return levelNames[idx];
  };

  const skillsList = useMemo(() => {
    if (!rawSkills) return [];
    return Object.values(rawSkills);
  }, [rawSkills]);

  /** 按 skill_type 分组（支持名称搜索） */
  const grouped = useMemo(() => {
    const groups: Record<string, Skill[]> = { '1': [], '2': [], '3': [], '4': [] };
    const filtered = skillsList.filter(s => !searchText || s.name.includes(searchText));
    for (const s of filtered) {
      const key = String(s.skill_type);
      if (groups[key]) groups[key].push(s);
    }
    return groups;
  }, [skillsList, searchText]);

  // === Attack columns (type 1) ===
  const attackColumns = [
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
      key: 'atkvalue',
      label: '伤害倍率',
      render: (v: unknown) => {
        const arr = v as number[];
        if (!arr || !arr.length) return '-';
        return arr.map((n) => n.toFixed(2) + 'x').join(' + ');
      },
    },
    {
      key: 'hits',
      label: '段数',
      render: (_v: unknown, row: Record<string, unknown>) => {
        const arr = row['atkvalue'] as number[] | undefined;
        return arr ? String(arr.length) : '-';
      },
    },
    {
      key: 'mpcost',
      label: 'MP消耗',
      render: (v: unknown) => mpcostStr(v as number),
    },
    {
      key: 'turncost',
      label: '冷却(回合)',
      render: (v: unknown) => String(v as number),
    },
    {
      key: 'rate',
      label: '触发率',
      render: (v: unknown) => rateStr(v as number),
    },
  ];

  // === Continuous columns (type 2) ===
  const continuousColumns = [
    { key: 'name', label: '名称' },
    {
      key: 'rank',
      label: '品阶',
      render: (v: unknown) => <RankBadge rank={v as string} />,
    },
    {
      key: 'required_level_index',
      label: '境界',
      render: (v: unknown) => getLevelName(v as number),
    },
    {
      key: 'atkvalue',
      label: '伤害倍率',
      render: (v: unknown) => {
        const n = v as number;
        return n != null ? n.toFixed(2) + 'x' : '-';
      },
    },
    {
      key: 'dot_turns',
      label: '持续回合',
      render: (v: unknown) => String(v as number),
    },
    {
      key: 'mpcost',
      label: 'MP消耗',
      render: (v: unknown) => mpcostStr(v as number),
    },
    {
      key: 'rate',
      label: '触发率',
      render: (v: unknown) => rateStr(v as number),
    },
  ];

  // === Buff columns (type 3) ===
  const buffColumns = [
    { key: 'name', label: '名称' },
    {
      key: 'rank',
      label: '品阶',
      render: (v: unknown) => <RankBadge rank={v as string} />,
    },
    {
      key: 'required_level_index',
      label: '境界',
      render: (v: unknown) => getLevelName(v as number),
    },
    {
      key: 'bufftype',
      label: '增益类型',
      render: (v: unknown) => {
        const bt = v as number;
          const BUFF_TYPE_NAMES: Record<number, string> = {1: '攻击', 2: '防御', 3: '治疗', 4: '特殊'};
          return BUFF_TYPE_NAMES[bt] || `类型${bt}`;
      },
    },
    {
      key: 'buffvalue',
      label: '增益幅度',
      render: (v: unknown) => {
        const n = v as number;
        return n != null ? (n * 100).toFixed(0) + '%' : '-';
      },
    },
    {
      key: 'turncost',
      label: '冷却(回合)',
      render: (v: unknown) => String(v as number),
    },
    {
      key: 'rate',
      label: '触发率',
      render: (v: unknown) => rateStr(v as number),
    },
  ];

  // === Control columns (type 4) ===
  const controlColumns = [
    { key: 'name', label: '名称' },
    {
      key: 'rank',
      label: '品阶',
      render: (v: unknown) => <RankBadge rank={v as string} />,
    },
    {
      key: 'required_level_index',
      label: '境界',
      render: (v: unknown) => getLevelName(v as number),
    },
    {
      key: 'turncost',
      label: '封禁回合',
      render: (v: unknown) => String(v as number),
    },
    {
      key: 'success',
      label: '成功率',
      render: (v: unknown) => {
        const n = v as number;
        return n != null ? `${n}%` : '-';
      },
    },
    {
      key: 'mpcost',
      label: 'MP消耗',
      render: (v: unknown) => mpcostStr(v as number),
    },
    {
      key: 'rate',
      label: '触发率',
      render: (v: unknown) => rateStr(v as number),
    },
  ];

  if (loading) {
    return (
      <PageLayout title="神通大全">
        <LoadingState />
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout title="神通大全">
        <ErrorState message={error} />
      </PageLayout>
    );
  }

  const TAB_CONFIG = [
    { key: '1', label: '攻击', count: grouped['1'].length },
    { key: '2', label: '持续', count: grouped['2'].length },
    { key: '3', label: '增益', count: grouped['3'].length },
    { key: '4', label: '控制', count: grouped['4'].length },
  ];

  return (
    <PageLayout title="神通大全" subtitle="53种神通技能完整数据，含伤害倍率、触发条件和效果说明">
      <SubTabs tabs={TAB_CONFIG} active={activeTab} onChange={setActiveTab} />

      <div className="flex flex-col sm:flex-row gap-3 mb-6 items-start sm:items-center">
        <SearchBar value={searchText} onChange={setSearchText} placeholder="搜索神通名称..." />
      </div>

      {/* 综合说明 */}
      <p className="info-box">
        神通技能在战斗中按概率自动触发。攻击技能有段数和伤害倍率；持续技能造成多回合DOT伤害；
        增益技能提供攻击力加成；控制技能可封禁对手行动。所有技能消耗法力值按最大MP百分比计算。
      </p>

      {/* ===== 攻击技能 ===== */}
      {activeTab === '1' && (
        <>
          {grouped['1'].length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm" style={{ color: 'rgba(222,219,200,0.4)' }}>暂无数据</p>
            </div>
          ) : (
            <DataTable columns={attackColumns} data={grouped['1'] as unknown as Record<string, unknown>[]} />
          )}
        </>
      )}

      {/* ===== 持续技能 ===== */}
      {activeTab === '2' && (
        <>
          {grouped['2'].length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm" style={{ color: 'rgba(222,219,200,0.4)' }}>暂无数据</p>
            </div>
          ) : (
            <DataTable columns={continuousColumns} data={grouped['2'] as unknown as Record<string, unknown>[]} />
          )}
        </>
      )}

      {/* ===== 增益技能 ===== */}
      {activeTab === '3' && (
        <>
          {grouped['3'].length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm" style={{ color: 'rgba(222,219,200,0.4)' }}>暂无数据</p>
            </div>
          ) : (
            <DataTable columns={buffColumns} data={grouped['3'] as unknown as Record<string, unknown>[]} />
          )}
        </>
      )}

      {/* ===== 控制技能 ===== */}
      {activeTab === '4' && (
        <>
          {grouped['4'].length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm" style={{ color: 'rgba(222,219,200,0.4)' }}>暂无数据</p>
            </div>
          ) : (
            <DataTable columns={controlColumns} data={grouped['4'] as unknown as Record<string, unknown>[]} />
          )}
        </>
      )}
    </PageLayout>
  );
}
