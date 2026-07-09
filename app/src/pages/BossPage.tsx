import { useMemo } from 'react';
import { PageLayout, DataTable } from '../components/DataComponents';

/** 20档世界Boss配置 */
const BOSS_LEVELS = [
  { name: '练气', levelIndex: 0,  hpMult: 1.4,  atkMult: 1.4,  rewardMult: 1.4 },
  { name: '筑基', levelIndex: 3,  hpMult: 2.1,  atkMult: 1.5,  rewardMult: 2.1 },
  { name: '金丹', levelIndex: 6,  hpMult: 2.8,  atkMult: 1.7,  rewardMult: 2.8 },
  { name: '元婴', levelIndex: 9,  hpMult: 3.5,  atkMult: 1.7,  rewardMult: 3.5 },
  { name: '化神', levelIndex: 12, hpMult: 4.2,  atkMult: 1.8,  rewardMult: 4.2 },
  { name: '炼虚', levelIndex: 15, hpMult: 4.9,  atkMult: 1.8,  rewardMult: 4.9 },
  { name: '合体', levelIndex: 18, hpMult: 5.6,  atkMult: 1.8,  rewardMult: 5.6 },
  { name: '大乘', levelIndex: 21, hpMult: 6.3,  atkMult: 2.0,  rewardMult: 6.3 },
  { name: '神火', levelIndex: 24, hpMult: 7.0,  atkMult: 2.0,  rewardMult: 7.0 },
  { name: '真一', levelIndex: 27, hpMult: 7.7,  atkMult: 2.0,  rewardMult: 7.7 },
  { name: '圣祭', levelIndex: 30, hpMult: 8.4,  atkMult: 2.1,  rewardMult: 8.4 },
  { name: '天神', levelIndex: 33, hpMult: 9.1,  atkMult: 2.1,  rewardMult: 9.1 },
  { name: '虚道', levelIndex: 36, hpMult: 9.8,  atkMult: 2.1,  rewardMult: 9.8 },
  { name: '斩我', levelIndex: 39, hpMult: 10.5, atkMult: 2.1,  rewardMult: 10.5 },
  { name: '混沌', levelIndex: 42, hpMult: 11.2, atkMult: 2.1,  rewardMult: 11.2 },
  { name: '创世', levelIndex: 45, hpMult: 12.6, atkMult: 2.1,  rewardMult: 12.6 },
  { name: '金仙', levelIndex: 48, hpMult: 14.0, atkMult: 2.1,  rewardMult: 14.0 },
  { name: '轮回', levelIndex: 51, hpMult: 15.4, atkMult: 2.2,  rewardMult: 15.4 },
  { name: '虚神', levelIndex: 54, hpMult: 15.4, atkMult: 2.2,  rewardMult: 15.4 },
  { name: '仙帝', levelIndex: 57, hpMult: 16.8, atkMult: 2.2,  rewardMult: 16.8 },
];

const BOSS_NAMES = [
  '血魔', '邪修', '魔头', '妖王', '魔君',
  '异兽', '凶兽', '妖尊', '魔尊', '邪帝',
  '天魔', '地魔', '魔神', '妖神', '邪神',
];

/** 掉落档位配置（含所有锻造材料） */
const DROP_TIERS = [
  {
    label: '低阶 (low)',
    range: '练气~筑基 (level_index ≤ 6)',
    items: [
      { name: '灵草', weight: 50, min: 2, max: 5 },
      { name: '精铁', weight: 30, min: 1, max: 3 },
      { name: '百年灵草', weight: 20, min: 1, max: 2 },
      { name: '紫金沙', weight: 10, min: 1, max: 1 },
    ],
  },
  {
    label: '中阶 (mid)',
    range: '金丹~化神 (level_index ≤ 12)',
    items: [
      { name: '灵草', weight: 30, min: 4, max: 10 },
      { name: '精铁', weight: 20, min: 2, max: 5 },
      { name: '百年灵草', weight: 15, min: 2, max: 4 },
      { name: '紫金沙', weight: 15, min: 1, max: 3 },
      { name: '魔核碎片', weight: 10, min: 1, max: 2 },
      { name: '赤炎石', weight: 10, min: 1, max: 2 },
    ],
  },
  {
    label: '高阶 (high)',
    range: '炼虚~天神 (level_index ≤ 33)',
    items: [
      { name: '灵草', weight: 20, min: 8, max: 20 },
      { name: '精铁', weight: 15, min: 5, max: 15 },
      { name: '百年灵草', weight: 10, min: 5, max: 10 },
      { name: '紫金沙', weight: 15, min: 2, max: 5 },
      { name: '魔核碎片', weight: 15, min: 2, max: 4 },
      { name: '赤炎石', weight: 15, min: 2, max: 4 },
      { name: '亡者之息', weight: 10, min: 1, max: 3 },
      { name: '幽魂草', weight: 10, min: 1, max: 3 },
      { name: '灵兽骨', weight: 8, min: 1, max: 2 },
    ],
  },
  {
    label: '究极 (ultra)',
    range: '虚道~合道 (level_index > 33)',
    items: [
      { name: '灵草', weight: 15, min: 15, max: 40 },
      { name: '精铁', weight: 12, min: 15, max: 40 },
      { name: '百年灵草', weight: 10, min: 10, max: 30 },
      { name: '亡者之息', weight: 15, min: 3, max: 6 },
      { name: '幽魂草', weight: 15, min: 3, max: 6 },
      { name: '星辉晶砂', weight: 12, min: 2, max: 5 },
      { name: '灵兽骨', weight: 10, min: 3, max: 8 },
      { name: '天火熔晶', weight: 8, min: 2, max: 4 },
      { name: '九幽寒铁', weight: 8, min: 2, max: 4 },
      { name: '玄冰之核', weight: 8, min: 1, max: 3 },
      { name: '月光粉尘', weight: 8, min: 1, max: 3 },
      { name: '龙骨髓', weight: 5, min: 1, max: 2 },
      { name: '妖丹', weight: 3, min: 1, max: 1 },
      { name: '混沌源石', weight: 3, min: 1, max: 1 },
    ],
  },
];

/** Boss Buff体系（仅level_index ≥ 24的Boss拥有） */
const BUFF_TIERS = [
  {
    tier: 0,
    range: '神火~天神 (24-33)',
    atk: 0.3, crit: 0.1, critDmg: 0.5,
    redAtk: 0.3, redCrit: 0.3, redCritDmg: 0.05,
    redLsMin: 0.3, redLsMax: 0.5,
  },
  {
    tier: 1,
    range: '虚道~混沌 (36-42)',
    atk: 0.5, crit: 0.25, critDmg: 0.9,
    redAtk: 0.45, redCrit: 0.45, redCritDmg: 0.2,
    redLsMin: 0.8, redLsMax: 1.0,
  },
  {
    tier: 2,
    range: '创世~金仙 (45-48)',
    atk: 0.7, crit: 0.45, critDmg: 1.3,
    redAtk: 0.55, redCrit: 0.6, redCritDmg: 0.4,
    redLsMin: 1.0, redLsMax: 1.0,
  },
  {
    tier: 3,
    range: '轮回~仙帝 (51-57)',
    atk: 0.9, crit: 0.6, critDmg: 1.7,
    redAtk: 0.62, redCrit: 0.67, redCritDmg: 0.6,
    redLsMin: 1.0, redLsMax: 1.0,
  },
];

export default function BossPage() {
  const tierColumns = [
    { key: 'rank', label: '#' },
    { key: 'name', label: '境界' },
    { key: 'levelIndex', label: 'Level指数' },
    { key: 'hpMult', label: 'HP倍数' },
    { key: 'atkMult', label: '攻击倍数' },
    { key: 'rewardMult', label: '奖励倍数' },
    { key: 'defense', label: '防御' },
  ];

  const tierRows = useMemo(() =>
    BOSS_LEVELS.map((b, i) => ({
      rank: i + 1,
      name: b.name,
      levelIndex: b.levelIndex,
      hpMult: b.hpMult.toFixed(1),
      atkMult: b.atkMult.toFixed(1),
      rewardMult: b.rewardMult.toFixed(1),
      defense: b.levelIndex >= 15 ? '减伤40%~90%' : '无',
    })), []
  );

  const buffColumns = [
    { key: 'range', label: '触发境界' },
    { key: 'atk', label: 'ATK攻%', render: (v: unknown) => <span style={{ color: '#ec5f67' }}>+{(v as number * 100).toFixed(0)}%</span> },
    { key: 'crit', label: '暴击率', render: (v: unknown) => <span style={{ color: '#ec5f67' }}>+{(v as number * 100).toFixed(0)}%</span> },
    { key: 'critDmg', label: '暴击伤害', render: (v: unknown) => <span style={{ color: '#ec5f67' }}>+{(v as number * 100).toFixed(0)}%</span> },
    { key: 'redAtk', label: '减玩家攻', render: (v: unknown) => <span style={{ color: '#5fb3b3' }}>-{(v as number * 100).toFixed(0)}%</span> },
    { key: 'redCrit', label: '减玩家暴', render: (v: unknown) => <span style={{ color: '#5fb3b3' }}>-{(v as number * 100).toFixed(0)}%</span> },
    { key: 'redCritDmg', label: '减玩家暴伤', render: (v: unknown) => <span style={{ color: '#5fb3b3' }}>-{(v as number * 100).toFixed(0)}%</span> },
    { key: 'redLs', label: '削减吸血', render: (_v: unknown, row: Record<string, unknown>) => {
      const min = row.redLsMin as number;
      const max = row.redLsMax as number;
      const txt = min === max ? `${(min * 100).toFixed(0)}%` : `${(min * 100).toFixed(0)}%~${(max * 100).toFixed(0)}%`;
      return <span style={{ color: '#eacb2c' }}>-{txt}</span>;
    }},
  ];

  const buffRows = useMemo(() =>
    BUFF_TIERS.map(b => ({
      range: b.range,
      atk: b.atk,
      crit: b.crit,
      critDmg: b.critDmg,
      redAtk: b.redAtk,
      redCrit: b.redCrit,
      redCritDmg: b.redCritDmg,
      redLsMin: b.redLsMin,
      redLsMax: b.redLsMax,
    })), []
  );

  return (
    <PageLayout title="世界Boss" subtitle="20档Boss全数据">
      {/* 说明文字 */}
      <p className="info-box">
        世界Boss系统覆盖全部58级修炼体系，每3级一个档位共20档。玩家ATK对Boss造成2倍伤害。
        Boss每小时自动刷新，所有玩家均可挑战。击败Boss后获得灵石奖励 + 锻造材料掉落。
      </p>

      {/* Boss档位表 */}
      <h3 className="section-title">Boss档位一览</h3>
      <DataTable columns={tierColumns} data={tierRows as unknown as Record<string, unknown>[]} />

      {/* 名称池 */}
      <h3 className="section-title" style={{ marginTop: 40 }}>
        <span className="jade-dot" />Boss名称池
      </h3>
      <div className="overflow-x-auto rounded-xl border border-white/5 bg-[#0a0a0a] p-5 gold-glow">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {BOSS_NAMES.map((n, i) => (
            <span
              key={i}
              className="inline-block px-4 py-1.5 rounded-md text-sm font-semibold transition-all duration-250 cursor-default hover:border-[rgba(212,175,55,0.3)] hover:bg-[rgba(212,175,55,0.06)]"
              style={{
                background: 'rgba(236,95,103,0.08)',
                border: '1px solid rgba(236,95,103,0.2)',
                color: '#ec5f67',
              }}
            >
              {n}
            </span>
          ))}
        </div>
        <div className="decorative-line thin" />
        <p style={{ fontSize: 12, color: 'rgba(222,219,200,0.4)', margin: '8px 0 0' }}>
          Boss名字由名称池随机选取 + 当前档位境界名拼接而成，例如「血魔·练气境」
        </p>
      </div>

      {/* 掉落规则 */}
      <h3 className="section-title" style={{ marginTop: 40 }}>
        <span className="jade-dot" />掉落规则
      </h3>
      <p style={{ fontSize: 13, color: 'rgba(222,219,200,0.5)', marginBottom: 16 }}>
        Boss掉落分为4个档位，根据Boss的 level_index 决定掉落池。每个物品按权重随机抽取。
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
        {DROP_TIERS.map(tier => (
          <div
            key={tier.label}
            style={{
              background: '#0a0a0a',
              border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: 12,
              overflow: 'hidden',
            }}
          >
            <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(212,175,55,0.15)', background: 'rgba(212,175,55,0.03)' }}>
              <span style={{ color: '#d4af37', fontWeight: 600, fontSize: 14 }}>{tier.label}</span>
              <span style={{ color: 'rgba(222,219,200,0.4)', fontSize: 12, marginLeft: 8 }}>{tier.range}</span>
            </div>
            <table className="data-table" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th>物品</th>
                  <th>权重</th>
                  <th>数量</th>
                </tr>
              </thead>
              <tbody>
                {tier.items.map((item, i) => (
                  <tr key={i}>
                    <td style={{ color: '#d3d7d4' }}>{item.name}</td>
                    <td>{item.weight}</td>
                    <td>{item.min}-{item.max}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {/* Boss Buff体系 */}
      <h3 className="section-title" style={{ marginTop: 40 }}>
        <span className="jade-dot" />Boss Buff体系
      </h3>
      <p style={{ fontSize: 13, color: 'rgba(222,219,200,0.5)', marginBottom: 16 }}>
        仅 level_index ≥ 24（神火及以上）的Boss拥有Buff。每档Boss随机获得2个Buff：1个进攻型 + 1个削弱型。
      </p>
      <DataTable columns={buffColumns} data={buffRows as unknown as Record<string, unknown>[]} />
      <p style={{ fontSize: 12, color: 'rgba(222,219,200,0.35)', marginTop: 12 }}>
        进攻型Buff（25%概率各一）：ATK攻 / 暴击率 / 暴击伤害 / 削减玩家吸血&emsp;
        削弱型Buff（25%概率各一）：削弱玩家攻击 / 削弱玩家暴击 / 削弱玩家暴击伤害
      </p>
    </PageLayout>
  );
}
