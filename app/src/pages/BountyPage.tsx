import { useMemo } from 'react';
import { useGameData } from '../hooks/useGameData';
import { PageLayout, LoadingState, ErrorState, DataTable, RankBadge } from '../components/DataComponents';

/** 悬赏令难度配置 */
interface DifficultyConfig {
  name: string;
  stone_scale: number;
  exp_scale: number;
  min_level: number;
}

/** 悬赏任务模板 */
interface BountyTemplate {
  id: number;
  name: string;
  difficulty: string;
  category: string;
  min_target: number;
  max_target: number;
  time_limit: number;
  reward: { stone: number; exp: number };
  item_table: string;
  weight: number;
}

/** 掉落配置条目 */
interface DropRankConfig {
  type_rate: number;
  gf_list: string[];
  st_list: string[];
  fx_list: string[];
}

/** 格式化秒数为可读时间 */
function formatTime(seconds: number): string {
  if (seconds >= 3600) return `${seconds / 3600}h`;
  if (seconds >= 60) return `${seconds / 60}min`;
  return `${seconds}s`;
}

/** 格式化灵石 */
function formatStone(v: number): string {
  if (v >= 100000000) return (v / 100000000).toFixed(1) + '亿';
  if (v >= 10000) return (v / 10000).toFixed(v % 10000 === 0 ? 0 : 1) + '万';
  return v.toLocaleString();
}

const DIFFICULTY_ORDER = ['easy', 'normal', 'hard', 'elite'];

export default function BountyPage() {
  const { data: templatesData, loading: tl, error: te } = useGameData<{
    difficulties: Record<string, DifficultyConfig>;
    templates: BountyTemplate[];
  }>('bounty_templates');

  const { data: dropData, loading: dl, error: de } = useGameData<Record<string, DropRankConfig>>('bounty_drop_config');

  // 难度等级列
  const diffColumns = [
    { key: 'key', label: '难度' },
    { key: 'name', label: '等级名称' },
    { key: 'minLevel', label: '最低等级' },
    { key: 'stoneScale', label: '灵石倍率' },
    { key: 'expScale', label: '修为倍率' },
  ];

  const diffRows = useMemo(() => {
    if (!templatesData?.difficulties) return [];
    return DIFFICULTY_ORDER.map(k => {
      const d = templatesData.difficulties[k];
      return {
        key: k.toUpperCase(),
        name: d.name,
        minLevel: d.min_level,
        stoneScale: `x${d.stone_scale}`,
        expScale: `x${d.exp_scale}`,
      };
    });
  }, [templatesData]);

  // 任务模板列
  const templateColumns = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: '任务名称' },
    { key: 'difficulty', label: '难度' },
    { key: 'category', label: '类型' },
    { key: 'targetRange', label: '目标数量' },
    { key: 'timeLimit', label: '时限' },
    { key: 'reward', label: '奖励', render: (_v: unknown, row: Record<string, unknown>) => {
      const s = row._stone as number;
      const e = row._exp as number;
      return (
        <span>
          <span style={{ color: '#eacb2c' }}>{formatStone(s)}灵石</span>
          <span style={{ color: 'rgba(222,219,200,0.3)', margin: '0 4px' }}>|</span>
          <span style={{ color: '#5fb3b3' }}>{e.toLocaleString()}修为</span>
        </span>
      );
    }},
    { key: 'weight', label: '权重' },
  ];

  const templateRows = useMemo(() => {
    if (!templatesData?.templates) return [];
    return templatesData.templates.map(t => {
      const diff = templatesData.difficulties[t.difficulty];
      return {
        id: t.id,
        name: t.name,
        difficulty: diff?.name ?? t.difficulty,
        category: t.category,
        targetRange: `${t.min_target}-${t.max_target}`,
        timeLimit: formatTime(t.time_limit),
        _stone: t.reward.stone,
        _exp: t.reward.exp,
        weight: t.weight,
      };
    });
  }, [templatesData]);

  // 功法掉落配置列
  const dropColumns = [
    { key: 'rank', label: '品阶', render: (v: unknown) => <RankBadge rank={v as string} /> },
    { key: 'typeRate', label: '权重' },
    { key: 'gf', label: '功法列表', render: (_v: unknown, row: Record<string, unknown>) => {
      const items = row._gfItems as string[];
      return <span style={{ fontSize: 12, color: '#d3d7d4' }}>{items.length ? items.join(', ') : '-'}</span>;
    }},
    { key: 'st', label: '神通列表', render: (_v: unknown, row: Record<string, unknown>) => {
      const items = row._stItems as string[];
      return <span style={{ fontSize: 12, color: '#d3d7d4' }}>{items.length ? items.join(', ') : '-'}</span>;
    }},
    { key: 'fx', label: '辅修列表', render: (_v: unknown, row: Record<string, unknown>) => {
      const items = row._fxItems as string[];
      return <span style={{ fontSize: 12, color: '#d3d7d4' }}>{items.length ? items.join(', ') : '-'}</span>;
    }},
  ];

  const RANK_ORDER = [
    '人阶下品', '人阶上品', '黄阶下品', '黄阶上品',
    '玄阶下品', '玄阶上品', '地阶下品', '地阶上品',
    '天阶下品', '天阶上品', '仙阶下品', '仙阶上品', '仙阶极品', '无上',
  ];

  const dropRows = useMemo(() => {
    if (!dropData) return [];
    return RANK_ORDER.map(rank => {
      const cfg = dropData[rank];
      if (!cfg) return null;
      return {
        rank,
        typeRate: cfg.type_rate,
        _gfItems: cfg.gf_list ?? [],
        _stItems: cfg.st_list ?? [],
        _fxItems: cfg.fx_list ?? [],
      };
    }).filter(Boolean);
  }, [dropData]);

  if (tl || dl) {
    return (
      <PageLayout title="悬赏令">
        <LoadingState />
      </PageLayout>
    );
  }

  if (te || de) {
    return (
      <PageLayout title="悬赏令">
        <ErrorState message={te || de || '未知错误'} />
      </PageLayout>
    );
  }

  return (
    <PageLayout title="悬赏令" subtitle="每日3次 · 100%掉落功法/神通/辅修功法">
      <p className="info-box">
        悬赏令系统每日刷新3个随机任务，完成后100%掉落功法、神通或辅修功法。
        任务奖励受境界等级缩放影响（bounty_rift_coefficient = 0.045）。
        共有4种难度等级、6种任务类型（巡山/采集/猎杀/探索/护送/镇压）。
      </p>

      {/* 难度等级 */}
      <h3 className="section-title">难度等级</h3>
      <DataTable columns={diffColumns} data={diffRows as unknown as Record<string, unknown>[]} />

      {/* 任务模板 */}
      <h3 className="section-title" style={{ marginTop: 40 }}>任务模板</h3>
      <DataTable columns={templateColumns} data={templateRows as unknown as Record<string, unknown>[]} />

      {/* 功法掉落配置 */}
      <h3 className="section-title" style={{ marginTop: 40 }}>功法掉落配置</h3>
      <p style={{ fontSize: 13, color: 'rgba(222,219,200,0.5)', marginBottom: 16 }}>
        共14品阶，按权重随机抽取。任务完成时从对应品阶的功法/神通/辅修功法池中随机选择一件。
      </p>
      <DataTable columns={dropColumns} data={dropRows as unknown as Record<string, unknown>[]} />
    </PageLayout>
  );
}
