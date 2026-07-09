import { useState } from 'react';
import { PageLayout, LoadingState, ErrorState } from '../components/DataComponents';
import { useGameData } from '../hooks/useGameData';

// ================== Types ==================
interface SectConfig {
  create_cost: number;
  create_level_required: number;
  positions: Record<string, { name: string; permission: number }>;
  scale_ratio: number;
  practice: {
    base_cost: number;
    cost_growth: number;
    atk_per_level: number;
    max_level: number;
    construction_per_level: number;
  };
  elixir_room: {
    claim_contribution_required: number;
    levels: Record<string, {
      name: string;
      upgrade_cost_scale: number;
      upgrade_cost_stone: number;
      daily_pills: number;
      pill_rank_max: number;
      guaranteed_pill: string;
      maintenance_cost: number;
    }>;
  };
  material_distribution: {
    hours: number[];
    rate: number;
  };
  member_limits: Record<string, {
    total: number;
    elder: number;
    direct: number;
    inner: number;
  }>;
  auto_owner_change: {
    inactive_days: number;
  };
  rename: {
    cost_contribution: number;
  };
  tasks: Array<{
    name: string;
    type: string;
    cost_ratio?: number;
    cost?: number;
    exp_ratio: number;
    sect_stone: number;
    material_mult: number;
    scale_mult: number;
    desc: string;
  }>;
  task_exp_caps: Record<string, number>;
  attack_practice_costs: Array<{
    level: number;
    materials: number;
    stone: number;
  }>;
  task_refresh_cd: number;
  daily_task_limit: number;
  task_cooldown: number;
  [key: string]: unknown;
}

function formatNumber(n: number): string {
  if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿';
  if (n >= 10000) return (n / 10000).toFixed(1) + '万';
  return n.toLocaleString('zh-CN');
}

function ConfigCard({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="bg-[#101010] rounded-xl border border-white/5 p-5 hover:border-white/10 transition-all duration-300">
      <div className="text-xs tracking-wider mb-1.5" style={{ color: 'rgba(222,219,200,0.4)' }}>
        {label}
      </div>
      <div className="text-sm font-semibold" style={{ color: '#E1E0CC' }}>
        {value}
      </div>
      {hint && (
        <div className="text-xs mt-1" style={{ color: 'rgba(222,219,200,0.3)' }}>{hint}</div>
      )}
    </div>
  );
}

export default function SectPage() {
  const { data, loading, error } = useGameData<SectConfig>('sect_config');
  const [activeTab, setActiveTab] = useState('overview');

  if (loading) return <PageLayout title="宗门系统"><LoadingState /></PageLayout>;
  if (error) return <PageLayout title="宗门系统"><ErrorState message={error} /></PageLayout>;
  if (!data) return <PageLayout title="宗门系统"><ErrorState message="数据为空" /></PageLayout>;

  const tabs = [
    { key: 'overview', label: '总览配置', count: 5 },
    { key: 'positions', label: '职位体系', count: Object.keys(data.positions).length },
    { key: 'elixir', label: '丹房等级', count: Object.keys(data.elixir_room.levels).length },
    { key: 'tasks', label: '宗门任务', count: data.tasks.length },
    { key: 'practice', label: '修炼消耗', count: 50 },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="space-y-6">
            {/* Core config cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <ConfigCard
                label="创建所需灵石"
                value={formatNumber(data.create_cost)}
              />
              <ConfigCard
                label="创建最低境界"
                value={`Lv.${data.create_level_required}`}
              />
              <ConfigCard
                label="规模倍率"
                value={data.scale_ratio}
              />
              <ConfigCard
                label="自动转让掌门"
                value={`${data.auto_owner_change?.inactive_days ?? 7}天离线`}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <ConfigCard
                label="宗门改名贡献"
                value={`${formatNumber(data.rename?.cost_contribution ?? 500)} 贡献`}
              />
              <ConfigCard
                label="材料分配时间"
                value={`${(data.material_distribution?.hours ?? [11, 12]).join(':00, ')}:00`}
                hint="每日自动分配"
              />
              <ConfigCard
                label="分配倍率"
                value={`${(data.material_distribution?.rate ?? 1) * 100}%`}
                hint="1:1 等比例分配"
              />
            </div>

            {/* Task config cards */}
            <div className="section-title">
              <span className="jade-dot" />任务配置
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <ConfigCard
                label="每日任务上限"
                value={data.daily_task_limit}
                hint="次/天"
              />
              <ConfigCard
                label="任务刷新CD"
                value={`${data.task_refresh_cd}秒`}
                hint={data.task_refresh_cd >= 60 ? `${(data.task_refresh_cd / 60).toFixed(0)}分钟` : undefined}
              />
              <ConfigCard
                label="任务冷却"
                value={`${data.task_cooldown}秒`}
                hint={`${(data.task_cooldown / 60).toFixed(0)}分钟`}
              />
            </div>

            {/* Task exp caps */}
            <div className="overflow-x-auto rounded-xl border border-white/5 bg-[#0a0a0a]">
              <div className="px-4 py-2.5 text-xs font-semibold tracking-wider border-b border-white/5" style={{ color: '#5fb3b3' }}>
                任务经验上限
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: 'rgba(222,219,200,0.5)' }}>品阶</th>
                    <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: 'rgba(222,219,200,0.5)' }}>经验上限</th>
                  </tr>
                </thead>
                <tbody>
                  {data.task_exp_caps && Object.entries(data.task_exp_caps).map(([key, val]) => (
                    <tr key={key} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
                      <td className="px-4 py-2 text-sm" style={{ color: '#d3d7d4' }}>{key}</td>
                      <td className="px-4 py-2 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{formatNumber(val)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Attack practice costs summary */}
            <div className="section-title">
              <span className="jade-dot" />攻击修炼消耗
            </div>
            <div className="overflow-x-auto rounded-xl border border-white/5 bg-[#0a0a0a]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>等级</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>所需材料</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>所需灵石</th>
                  </tr>
                </thead>
                <tbody>
                  {data.attack_practice_costs?.slice(0, 15).map((cost) => (
                    <tr key={cost.level} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
                      <td className="px-4 py-2 text-sm" style={{ color: '#d3d7d4' }}>Lv.{cost.level}</td>
                      <td className="px-4 py-2 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{formatNumber(cost.materials)}</td>
                      <td className="px-4 py-2 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{formatNumber(cost.stone)}</td>
                    </tr>
                  ))}
                  {data.attack_practice_costs && data.attack_practice_costs.length > 15 && (
                    <tr>
                      <td
                        colSpan={3}
                        className="px-4 py-3 text-center text-xs"
                        style={{ color: 'rgba(222,219,200,0.3)' }}
                      >
                        ... 共 {data.attack_practice_costs.length} 级（点击"修炼消耗"标签查看完整列表）
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        );

      case 'positions':
        return (
          <div className="space-y-4">
            <p className="text-xs" style={{ color: 'rgba(222,219,200,0.5)' }}>
              宗门职位体系，权限值越高可执行的操作越多。共 {Object.keys(data.positions).length} 个职位等级。
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(data.positions)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([id, pos]) => (
                  <div
                    key={id}
                    className="bg-[#101010] rounded-xl border border-white/5 p-5 hover:border-white/10 transition-all"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-semibold" style={{ color: '#E1E0CC' }}>{pos.name}</h4>
                      <span
                        className="text-xs px-2 py-0.5 rounded"
                        style={{ background: 'rgba(95,179,179,0.1)', color: '#5fb3b3' }}
                      >
                        ID: {id}
                      </span>
                    </div>
                    <div className="text-xs" style={{ color: 'rgba(222,219,200,0.5)' }}>
                      权限值: <strong style={{ color: '#d3d7d4' }}>{pos.permission}</strong>
                    </div>
                  </div>
                ))}
            </div>

            {/* Member limits */}
            <h3 className="section-title mt-6"><span className="jade-dot" />成员上限</h3>
            <div className="overflow-x-auto rounded-xl border border-white/5 bg-[#0a0a0a]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-4 py-2.5 text-left text-xs font-medium" style={{ color: 'rgba(222,219,200,0.5)' }}>丹房等级</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium" style={{ color: 'rgba(222,219,200,0.5)' }}>总人数</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium" style={{ color: 'rgba(222,219,200,0.5)' }}>长老</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium" style={{ color: 'rgba(222,219,200,0.5)' }}>亲传弟子</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium" style={{ color: 'rgba(222,219,200,0.5)' }}>内门弟子</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.member_limits)
                    .sort(([a], [b]) => Number(a) - Number(b))
                    .map(([key, limit]) => (
                      <tr key={key} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
                        <td className="px-4 py-2 text-sm" style={{ color: '#d3d7d4' }}>Lv.{key}</td>
                        <td className="px-4 py-2 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{limit.total}</td>
                        <td className="px-4 py-2 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{limit.elder}</td>
                        <td className="px-4 py-2 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{limit.direct}</td>
                        <td className="px-4 py-2 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{limit.inner}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        );

      case 'elixir':
        return (
          <div className="space-y-4">
            <div className="info-box">
              丹房需要消耗贡献值领取：{formatNumber(data.elixir_room.claim_contribution_required)} 贡献/次。
              每日自动发放渡厄丹，品阶越高的丹房可获得更多且更高级的丹药。
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.entries(data.elixir_room.levels)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([key, level]) => (
                  <div
                    key={key}
                    className="bg-[#101010] rounded-xl border border-white/5 p-5 hover:border-white/10 transition-all"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-semibold" style={{ color: '#E1E0CC' }}>{level.name}</h4>
                      <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(234,203,44,0.1)', color: '#eacb2c' }}>
                        Lv.{key}
                      </span>
                    </div>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between" style={{ color: 'rgba(222,219,200,0.5)' }}>
                        <span>升级消耗灵石</span>
                        <span className="tabular-nums" style={{ color: '#d3d7d4' }}>{formatNumber(level.upgrade_cost_scale)}</span>
                      </div>
                      <div className="flex justify-between" style={{ color: 'rgba(222,219,200,0.5)' }}>
                        <span>每日丹药</span>
                        <span className="tabular-nums" style={{ color: '#d3d7d4' }}>{level.daily_pills} 颗</span>
                      </div>
                      <div className="flex justify-between" style={{ color: 'rgba(222,219,200,0.5)' }}>
                        <span>丹药品阶上限</span>
                        <span className="tabular-nums" style={{ color: '#d3d7d4' }}>{level.pill_rank_max}</span>
                      </div>
                      <div className="flex justify-between" style={{ color: 'rgba(222,219,200,0.5)' }}>
                        <span>维护费</span>
                        <span className="tabular-nums" style={{ color: '#d3d7d4' }}>{formatNumber(level.maintenance_cost)}</span>
                      </div>
                      <div className="flex justify-between" style={{ color: 'rgba(222,219,200,0.5)' }}>
                        <span>保底丹药</span>
                        <span style={{ color: '#d4af37' }}>{level.guaranteed_pill}</span>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        );

      case 'tasks':
        return (
          <div className="space-y-4">
            <div className="info-box">
              宗门任务共 {data.tasks.length} 种类型，每日上限 {data.daily_task_limit} 次。任务分为消耗气血(2种)和消耗灵石(3种)两类，
              完成后可获得修为经验和宗门灵石。
            </div>
            <div className="grid grid-cols-1 gap-4">
              {data.tasks.map((task, i) => (
                <div
                  key={i}
                  className="bg-[#101010] rounded-xl border border-white/5 p-5 hover:border-white/10 transition-all"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span
                        className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold"
                        style={{ background: task.type === 'hp' ? 'rgba(236,95,103,0.1)' : 'rgba(95,179,179,0.1)', color: task.type === 'hp' ? '#ec5f67' : '#5fb3b3' }}
                      >
                        {task.type === 'hp' ? '血' : '石'}
                      </span>
                      <h4 className="text-sm font-semibold" style={{ color: '#E1E0CC' }}>{task.name}</h4>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(222,219,200,0.05)', color: 'rgba(222,219,200,0.4)' }}>
                      ×{task.material_mult}
                    </span>
                  </div>

                  <p className="text-xs mb-3" style={{ color: 'rgba(222,219,200,0.5)' }}>{task.desc}</p>

                  <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs">
                    {task.type === 'hp' ? (
                      <>
                        <span style={{ color: 'rgba(222,219,200,0.4)' }}>
                          消耗气血: <strong style={{ color: '#ec5f67' }}>{(task.cost_ratio! * 100).toFixed(0)}%</strong>
                        </span>
                      </>
                    ) : (
                      <span style={{ color: 'rgba(222,219,200,0.4)' }}>
                        消耗灵石: <strong style={{ color: '#eacb2c' }}>{formatNumber(task.cost!)}</strong>
                      </span>
                    )}
                    <span style={{ color: 'rgba(222,219,200,0.4)' }}>
                      经验倍率: <strong style={{ color: '#99c794' }}>+{(task.exp_ratio * 100).toFixed(2)}%</strong>
                    </span>
                    <span style={{ color: 'rgba(222,219,200,0.4)' }}>
                      宗门灵石: <strong style={{ color: '#E1E0CC' }}>{formatNumber(task.sect_stone)}</strong>
                    </span>
                    <span style={{ color: 'rgba(222,219,200,0.4)' }}>
                      规模倍率: <strong style={{ color: '#d3d7d4' }}>{task.scale_mult}</strong>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case 'practice':
        return (
          <div className="space-y-4">
            <div className="info-box">
              攻击修炼共 {data.attack_practice_costs?.length ?? 0} 级，每级提供 {data.practice?.atk_per_level ?? 0.04 * 100}% 攻击力加成。
              基础消耗 {formatNumber(data.practice?.base_cost ?? 500000)}，每级增长 {(data.practice?.cost_growth ?? 1.22).toFixed(2)} 倍。
            </div>

            {/* Practice overview */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <ConfigCard label="最大等级" value={data.practice?.max_level ?? 50} />
              <ConfigCard label="基础消耗" value={formatNumber(data.practice?.base_cost ?? 500000)} />
              <ConfigCard label="消耗增长率" value={`×${(data.practice?.cost_growth ?? 1.22).toFixed(2)}/级`} />
              <ConfigCard label="每级 ATK" value={`+${(data.practice?.atk_per_level ?? 0.04) * 100}%`} />
            </div>

            {/* Full cost table */}
            <div className="overflow-x-auto rounded-xl border border-white/5 bg-[#0a0a0a]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>等级</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>材料消耗</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>灵石消耗</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>累计材料</th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>累计灵石</th>
                  </tr>
                </thead>
                <tbody>
                  {data.attack_practice_costs?.map((cost, i, arr) => {
                    const cumMat = arr.slice(0, i + 1).reduce((s, c) => s + c.materials, 0);
                    const cumStone = arr.slice(0, i + 1).reduce((s, c) => s + c.stone, 0);
                    return (
                      <tr key={cost.level} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
                        <td className="px-4 py-2 text-sm" style={{ color: '#d3d7d4' }}>Lv.{cost.level}</td>
                        <td className="px-4 py-2 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{formatNumber(cost.materials)}</td>
                        <td className="px-4 py-2 text-sm tabular-nums" style={{ color: '#d3d7d4' }}>{formatNumber(cost.stone)}</td>
                        <td className="px-4 py-2 text-sm tabular-nums" style={{ color: 'rgba(222,219,200,0.5)' }}>{formatNumber(cumMat)}</td>
                        <td className="px-4 py-2 text-sm tabular-nums" style={{ color: 'rgba(222,219,200,0.5)' }}>{formatNumber(cumStone)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <PageLayout title="宗门系统" subtitle="宗门创建、职位、丹房与任务配置">
      {/* Tabs */}
      <div className="flex gap-2 flex-wrap mb-6">
        {tabs.map(t => (
          <button
            key={t.key}
            className={`sub-tab ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
            {t.count !== undefined ? ` (${t.count})` : ''}
          </button>
        ))}
      </div>

      {renderContent()}
    </PageLayout>
  );
}
