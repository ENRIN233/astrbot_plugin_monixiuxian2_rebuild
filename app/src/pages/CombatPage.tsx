
import { PageLayout } from '../components/DataComponents';

interface FormulaCardProps {
  title: string;
  formula: string;
  description: string;
  variables: { name: string; desc: string }[];
  index?: number;
}

function FormulaCard({ title, formula, description, variables, index }: FormulaCardProps) {
  return (
    <div
      className="bg-card rounded-xl border border-white/5 p-6 md:p-8 hover:border-[rgba(212,175,55,0.12)] hover:shadow-[0_0_16px_rgba(212,175,55,0.04)] transition-all duration-300"
    >
      <div className="flex items-center gap-3 mb-4">
        <span
          className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
          style={{ background: 'rgba(212,175,55,0.08)', color: '#d4af37' }}
        >
          {String((index ?? 0) + 1).padStart(2, '0')}
        </span>
        <h3 className="text-base font-semibold" style={{ color: '#E1E0CC' }}>{title}</h3>
      </div>

      <div
        className="font-mono text-sm p-4 rounded-lg mb-4 overflow-x-auto gold-glow"
        style={{ background: 'rgba(0,0,0,0.5)', color: '#d4af37', border: '1px solid rgba(212,175,55,0.1)' }}
      >
        <code>{formula}</code>
      </div>

      <p className="text-sm mb-3" style={{ color: 'rgba(222,219,200,0.6)' }}>{description}</p>

      {variables.length > 0 && (
        <div className="space-y-1">
          {variables.map(v => (
            <div key={v.name} className="flex gap-2 text-xs">
              <span className="font-mono shrink-0" style={{ color: '#d4af37' }}>{v.name}</span>
              <span style={{ color: 'rgba(222,219,200,0.4)' }}>{v.desc}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const FORMULAS: FormulaCardProps[] = [
  {
    title: '生命值 (HP)',
    formula: 'HP = max(1000, int(exp / 2 × (1 + hp_buff))) × (1 + hp_bonus)',
    description: '生命值由修为经验值决定，装备和心法提供的 hp_bonus 为最终乘算加成。基础下限为1000。',
    variables: [
      { name: 'exp', desc: '当前修为经验值' },
      { name: 'hp_buff', desc: '装备/心法提供的HP百分比加成' },
      { name: 'hp_bonus', desc: '最终HP乘算加成' },
    ],
  },
  {
    title: '法力值 (MP)',
    formula: 'MP = max(100, int(exp × (1 + mp_buff))) × (1 + mp_bonus)',
    description: '法力值同样基于修为经验值，基础下限为100。神通技能消耗法力值进行释放。',
    variables: [
      { name: 'exp', desc: '当前修为经验值' },
      { name: 'mp_buff', desc: '装备/心法提供的MP百分比加成' },
      { name: 'mp_bonus', desc: '最终MP乘算加成' },
    ],
  },
  {
    title: '攻击力 (ATK)',
    formula: 'ATK = max(100, int(exp / 10)) × (atk_practice × 0.04 + 1) × (1 + technique) × (1 + weapon) × (1 + armor) + permanent_buff',
    description: '攻击力采用多层乘算叠加机制。基础攻击力由修为决定，经攻击修炼、心法、武器、防具加成后叠加永久丹药增益。',
    variables: [
      { name: 'atk_practice', desc: '宗门攻击修炼等级（每级+4%）' },
      { name: 'technique', desc: '心法提供的ATK百分比加成' },
      { name: 'weapon', desc: '武器提供的ATK百分比加成' },
      { name: 'armor', desc: '防具提供的ATK百分比加成' },
      { name: 'permanent_buff', desc: '永久丹药提供的固定攻击力加成' },
    ],
  },
  {
    title: '修为速度 (Power)',
    formula: 'Power = round(exp × root_speed × realm_spend)',
    description: '修为获取速度是修炼效率的核心指标，受灵根倍率和境界系数影响。',
    variables: [
      { name: 'exp', desc: '基础经验值（每分钟）' },
      { name: 'root_speed', desc: '灵根修炼速度倍率（0~2.5）' },
      { name: 'realm_spend', desc: '境界修炼系数（level_config中的spend字段）' },
    ],
  },
  {
    title: '修炼经验获取',
    formula: '每分钟经验 = 60 × 分钟数 × root_speed × realm_spend × (1 + technique) × (1 + closing_exp) × pill × (1 + land) × (1 + permanent_mult)',
    description: '闭关修炼经验采用多层乘算，涵盖灵根、心法、丹药、灵田、永久增益等多个维度。',
    variables: [
      { name: 'closing_exp', desc: '功法闭关经验加成' },
      { name: 'pill', desc: '修为丹药倍率' },
      { name: 'land', desc: '灵田增益倍率' },
      { name: 'permanent_mult', desc: '永久修炼速度倍率（丹药）' },
    ],
  },
  {
    title: '暴击伤害',
    formula: 'CritMult = max(1.5, 1.0 + weapon_crit_damage + technique_crit_damage + impart_burst_per)',
    description: '暴击伤害以1.0为基准，装备和心法提供额外加成，最低保证1.5倍。暴击率由武器和心法叠加提供。',
    variables: [
      { name: 'weapon_crit_damage', desc: '武器暴击伤害加成' },
      { name: 'technique_crit_damage', desc: '心法暴击伤害加成' },
      { name: 'impart_burst_per', desc: '传承卡暴击伤害加成' },
    ],
  },
  {
    title: '伤害公式',
    formula: '最终伤害 = ATK × 0.5 × crit_mult × 1.5 × float × (1 - def_buff + armor_pen/100 + sub_break_pct)',
    description: '伤害先减半（平衡系数0.5），再乘暴击倍率、武器系数1.5，最后扣除目标防御。破甲属性可从百分比扣除防御。',
    variables: [
      { name: 'crit_mult', desc: '暴击倍率（不暴击=1）' },
      { name: 'float', desc: '随机浮动系数' },
      { name: 'def_buff', desc: '目标防御百分比（上限90%）' },
      { name: 'armor_pen', desc: '破甲率（百分比）' },
      { name: 'sub_break_pct', desc: '辅修功法破甲百分比' },
    ],
  },
  {
    title: '防御减伤',
    formula: 'def_buff = min(0.9, armor_def_buff + weapon_damage_reduction + technique_damage_reduction)',
    description: '防御采用百分比减伤机制，上限为90%。防具基础防御 + 武器减伤 + 心法减伤叠加。部分Boss技能可无视50%防御。',
    variables: [
      { name: 'armor_def_buff', desc: '防具提供的防御百分比' },
      { name: 'weapon_damage_reduction', desc: '武器提供的减伤' },
      { name: 'technique_damage_reduction', desc: '心法提供的减伤' },
    ],
  },
];

const ATTRIBUTE_COLUMNS = [
  { category: '基础属性', attrs: [
    { name: 'blood_qi (气血)', desc: '生命值上限', source: '修为经验值' },
    { name: 'spiritual_qi (灵力)', desc: '法力值上限', source: '修为经验值' },
    { name: 'lifespan (寿命)', desc: '角色寿命上限', source: '境界晋升' },
  ]},
  { category: '战斗属性', attrs: [
    { name: 'atk_bonus', desc: '攻击力百分比加成', source: '武器/防具' },
    { name: 'hp_bonus', desc: '生命值百分比加成', source: '心法' },
    { name: 'mp_bonus', desc: '法力值百分比加成', source: '心法/武器' },
    { name: 'crit_rate', desc: '暴击率', source: '武器/心法' },
    { name: 'crit_damage', desc: '暴击伤害额外加成', source: '武器/心法' },
    { name: 'armor_pen', desc: '破甲率', source: '武器' },
    { name: 'lifesteal', desc: '吸血比例', source: '武器' },
    { name: 'double_hit', desc: '连击概率', source: '武器' },
  ]},
  { category: '防御属性', attrs: [
    { name: 'def_buff', desc: '防御百分比（上限90%）', source: '防具' },
    { name: 'dodge_rate', desc: '闪避率', source: '防具' },
    { name: 'crit_resist', desc: '暴击抗性', source: '防具' },
    { name: 'reflect_pct', desc: '反伤比例', source: '防具' },
    { name: 'block_value', desc: '格挡值', source: '防具' },
    { name: 'hp_regen_pct', desc: '每回合回血比例', source: '防具' },
    { name: 'damage_reduction', desc: '减伤', source: '武器/心法' },
  ]},
  { category: '修炼与功能', attrs: [
    { name: 'breakthrough_bonus', desc: '突破概率加成', source: '心法' },
    { name: 'breakthrough_number', desc: '突破概率+突破次数/100', source: '心法' },
    { name: 'closing_exp_bonus', desc: '闭关经验加成', source: '心法' },
    { name: 'closing_recovery_bonus', desc: '闭关经验保护', source: '心法' },
    { name: 'harvest_bonus', desc: '灵田收获加成', source: '心法' },
    { name: 'alchemy_exp_bonus', desc: '炼丹经验加成', source: '心法' },
    { name: 'alchemy_count_bonus', desc: '炼丹出丹数加成', source: '心法/丹炉' },
    { name: 'dual_cultivation_bonus', desc: '双修加成', source: '心法' },
    { name: 'exp_multiplier', desc: '经验倍率', source: '心法' },
    { name: 'random_buff', desc: '随机效果', source: '心法' },
  ]},
];

export default function CombatPage() {
  return (
    <PageLayout title="战斗数值" pageId="combat" subtitle="核心战斗公式与属性详解">
      {/* Info box */}
      <div className="info-box">
        战斗系统采用回合制自动战斗。神通技能按概率自动触发，每个技能有独立冷却和法力消耗。
        装备属性叠加计算，辅修功法提供每回合增益或减益效果。Boss战斗玩家攻击力翻倍。
      </div>

      {/* Formula cards */}
      <h2 className="section-title"><span className="jade-dot" />核心公式</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
        {FORMULAS.map((f, i) => (
          <FormulaCard key={f.title} {...f} index={i} />
        ))}
      </div>

      {/* Attributes table */}
      <h2 className="section-title"><span className="jade-dot" />战斗属性一览</h2>
      <div className="space-y-6">
        {ATTRIBUTE_COLUMNS.map(category => (
          <div key={category.category} className="overflow-x-auto rounded-xl border border-white/5 bg-surface">
            <div
              className="px-4 py-2.5 text-xs font-semibold tracking-wider border-b border-white/5"
              style={{ color: '#5fb3b3' }}
            >
              {category.category}
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>
                    属性名
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>
                    说明
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider" style={{ color: 'rgba(222,219,200,0.5)' }}>
                    来源
                  </th>
                </tr>
              </thead>
              <tbody>
                {category.attrs.map(attr => (
                  <tr key={attr.name} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-2.5 text-sm font-mono" style={{ color: '#99c794' }}>{attr.name}</td>
                    <td className="px-4 py-2.5 text-sm" style={{ color: '#d3d7d4' }}>{attr.desc}</td>
                    <td className="px-4 py-2.5 text-sm" style={{ color: 'rgba(222,219,200,0.5)' }}>{attr.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      <div className="decorative-line" />

      {/* Special mechanics */}
      <h2 className="section-title"><span className="jade-dot" />特殊机制</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card rounded-xl border border-white/5 p-5 hover:border-[rgba(197,148,197,0.2)] transition-all duration-300">
          <div className="flex items-center gap-2 mb-3">
            <span
              className="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold"
              style={{ background: 'rgba(197,148,197,0.12)', color: '#c594c5' }}
            >
              01
            </span>
            <h4 className="text-sm font-semibold" style={{ color: '#c594c5' }}>神通系统</h4>
          </div>
          <ul className="space-y-1.5 text-xs m-0" style={{ color: 'rgba(222,219,200,0.6)' }}>
            <li>53种神通技能，4种类型</li>
            <li>按 rate 概率自动触发</li>
            <li>turncost 冷却机制</li>
            <li>持续技能独立 DOT 回合</li>
            <li>Buff/Debuff 引擎管理</li>
          </ul>
        </div>
        <div className="bg-card rounded-xl border border-white/5 p-5 hover:border-[rgba(95,179,179,0.2)] transition-all duration-300">
          <div className="flex items-center gap-2 mb-3">
            <span
              className="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold"
              style={{ background: 'rgba(95,179,179,0.12)', color: '#5fb3b3' }}
            >
              02
            </span>
            <h4 className="text-sm font-semibold" style={{ color: '#5fb3b3' }}>辅修功法</h4>
          </div>
          <ul className="space-y-1.5 text-xs m-0" style={{ color: 'rgba(222,219,200,0.6)' }}>
            <li>23种辅修功法</li>
            <li>13种 buff_type 效果</li>
            <li>战斗开始时应用被动增益</li>
            <li>每回合持续效果</li>
            <li>破甲/吸血/中毒等机制</li>
          </ul>
        </div>
        <div className="bg-card rounded-xl border border-white/5 p-5 hover:border-[rgba(236,95,103,0.2)] transition-all duration-300">
          <div className="flex items-center gap-2 mb-3">
            <span
              className="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold"
              style={{ background: 'rgba(236,95,103,0.12)', color: '#ec5f67' }}
            >
              03
            </span>
            <h4 className="text-sm font-semibold" style={{ color: '#ec5f67' }}>Boss战斗</h4>
          </div>
          <ul className="space-y-1.5 text-xs m-0" style={{ color: 'rgba(222,219,200,0.6)' }}>
            <li>玩家ATK×2</li>
            <li>20档Boss覆盖全境界</li>
            <li>8种Boss Buff类型，4档强度</li>
            <li>特殊攻击：紫玄掌/子龙朱雀</li>
            <li>CAS乐观锁首杀判定</li>
          </ul>
        </div>
      </div>
    </PageLayout>
  );
}
