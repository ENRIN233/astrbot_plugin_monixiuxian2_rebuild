import { PageLayout } from '../components/DataComponents';

const changelog = [
  {
    version: 'v4.3.0',
    title: '数值资料库全面焕新 + 多项优化',
    sections: [
      {
        heading: '🌐 数值资料库全面重构',
        items: [
          '12+ 数据详情页：灵根/境界/丹药/装备/神通/Boss/悬赏/锻造/炼丹/战斗公式/宗门系统，独立路由页面',
          '古风主题 UI：暗色水墨背景 + 宣纸纹理，玄黑/藏青/月白/苍青主色调，Noto Serif SC 宋体排版',
          '品阶发光边框：人阶/黄阶/地阶/仙阶/无上五阶品级发光边框特效',
          'Light/Dark 双主题：浅色羊皮纸模式适配不同使用场景',
          '页面入场动画 + 粒子质感：framer-motion 驱动，每个数据页独立纹理背景',
          '响应式布局：完整移动端适配（<480px/<768px/桌面端三级断点）',
          '后台数据缓存爆破：修复长期运行导致的 JSON 缓存陈旧问题',
          '稀有度光谱交互修复：修复鼠标悬停时光谱条因 width/flex 布局冲突导致的抽搐',
        ],
      },
      {
        heading: '🎬 首页英雄视频',
        items: [
          '自动播放修仙氛围视频背景（GPU 合成层，零 CSS 滤镜性能损耗）',
          '页面不可见时自动暂停节省 GPU 解码资源',
        ],
      },
      {
        heading: '🔄 其他优化',
        items: [
          '神通持续页修复 atkvalue 类型错误导致的白屏问题',
          '武器/防具品阶标签全站统一渲染',
          '搜索栏、回到顶部按钮、数据快速导航',
        ],
      },
      {
        heading: '📋 指令更新',
        items: [
          '新增 稻草人 练习战指令',
          '新增 金银阁 赌坊系统及完整指令集',
          '新增 宗门刷新任务 指令',
          '指令总数更新为 150+ 条',
        ],
      },
    ],
  },
  {
    version: 'v4.2.0',
    title: '锻造系统（炼器）',
    sections: [
      {
        heading: '🔨 锻造系统（全新）',
        items: [
          '52 个锻造配方：13 个品阶（下品符器→无上仙器），33 武器 + 19 防具',
          '三阶材料体系：基础材料（精铁/百年灵草）+ 强化材料（赤炎石/紫金沙等 9 种）+ 核心材料（龙骨髓/妖丹/混沌源石等 5 种）',
          '品质系统：下品(×0.85) / 中品(×1.0) / 上品(×1.2) / 极品(×1.5)，锻造等级越高极品率越高',
          '随机词条：8 种词条池（嗜血/破甲/连击/精准/铁壁/闪避/暴伤/回春），品质越高词条越多（0-4 条）',
          '锻造经验等级：N×30 升级曲线，Lv.60 解锁所有配方，预估约 77 天满级',
          '分解回收：按品质回收 25%-50% 材料',
          'BOSS 掉落：掉落表扩展为 4 档，高阶 Boss 掉落的低阶材料数量倍增',
          '武器实例：所有锻造装备独立存储，可装备/卸下/分解，战斗属性完全生效',
          '天罪合成：原罪（残缺）+ 无罪（残缺）→ 天罪，继承双方词条取高品质',
          '序号操作：装备/分解/融合均支持武器列表中的序号，无需输入完整 ID',
        ],
      },
      {
        heading: '📋 新增命令',
        items: [
          '`锻造 <配方名> [数量]` — 消耗材料锻造装备，支持 1-10 批量',
          '`锻造配方` — 查看可锻造的配方和材料',
          '`锻造信息` — 查看锻造等级和品质概率',
          '`武器列表 [页码]` — 查看武器库中的锻造实例（支持序号操作）',
          '`装备 <序号/ID>` — 装备锻造武器/防具',
          '`分解 <序号/ID>` — 分解武器回收材料',
          '`融合 <序号1> <序号2>` — 原罪+无罪→天罪，继承词条取高品质',
        ],
      },
      {
        heading: '🔄 其他变更',
        items: [
          'Boss 数值倍率曲线调整（平滑高阶跳变）',
          '新增 5 种锻造材料（灵兽骨/妖丹/天火熔晶/九幽寒铁/混沌源石）',
        ],
      },
    ],
  },
  {
    version: 'v4.1.0',
    title: '宗门系统大迁移 + 传统丹药清理',
    sections: [
      {
        heading: '🏯 宗门系统迁移（NoneBot2 → AstrBot）',
        items: [
          '攻击修炼：消耗灵石+宗门建设度升级，最高50级，每级+4%攻击力，已计入战斗公式',
          '丹房建设：5级丹房（黄级→仙级），升级消耗灵石+建设度，品阶上限从凡品到皇品',
          '领取丹药：每日一次，按丹房等级和品阶上限加权随机选取修为丹，高品阶权重更高',
          '宗门改名：消耗500贡献度修改宗门名称',
          '自动传位：宗主离线7天自动传位给最高贡献成员',
          '每日资材发放：每日12:00按建设度×10%自动发放宗门资材',
        ],
      },
      {
        heading: '⚔️ 宗门任务重做',
        items: [
          '奖励改为固定值：贡献 +10,000、资材 +100,000、建设度 +50,000',
          '每日3次，冷却10分钟，通过 extra_data 存储冷却（不占用忙碌状态）',
          '修复原 perform_sect_task 中全局重置所有玩家任务次数的 bug',
          '修复 donate_to_sect 未读取 scale_ratio 配置的 bug',
        ],
      },
      {
        heading: '🗑️ 传统丹药清理',
        items: [
          '删除 items.json 中 ID 1001-1033 共33个传统丹药',
          '移除网页"传统丹药"标签页及相关渲染代码',
          '修复 rift_manager.py 秘境掉落表引用已删除丹药的问题，替换为功能丹',
          '修复 game_config.json 同步清理',
        ],
      },
      {
        heading: '🐛 Bug 修复',
        items: [
          '修复丹药选择函数 _select_random_pills 字段名错误',
          '修复 pill_rank_max 参数未传递到丹药选择逻辑的问题',
          '修复低品丹药概率过高问题，改为按品阶加权随机',
        ],
      },
    ],
  },
  {
    version: 'v4.0.2',
    title: '每日活跃度系统 + 幸运丹调整 + 合体境突破惩罚',
    sections: [
      {
        heading: '📊 每日活跃度系统',
        items: [
          '新增9个每日任务，完成全部可获得100活跃值',
          '任务列表：签到/历练/秘境/悬赏/商店购买/灵田收获/炼丹/领取利息/宗门贡献',
          '/每日活跃 查看当日任务进度面板，/活跃奖励 活跃值满100后领取渡厄丹×1',
        ],
      },
      {
        heading: '🍀 幸运丹调整',
        items: ['幸运丹品阶：皇品 → 道品，价格：5000万灵石', '天命幸运丹品阶：帝品 → 仙品，价格：1亿灵石'],
      },
      {
        heading: '⚔️ 合体境突破惩罚',
        items: ['合体境及以上突破失败修为惩罚提升至1%~5%', '合体境以下保持0.1%~1%不变'],
      },
      {
        heading: '📅 签到里程碑奖励',
        items: ['第7天：5,000,000 灵石', '第14天：天道加速丹 ×4', '第21天：混元加速丹 ×2', '第28天：天命幸运丹 ×1'],
      },
    ],
  },
  {
    version: 'v4.0.1',
    title: '菜单体系重构 + 寄售系统优化 + 交易功能扩展',
    sections: [
      {
        heading: '📋 菜单体系重构',
        items: [
          '/菜单 总览同步所有子菜单变更，描述更精准',
          '/修仙帮助 全面校对，/菜单 放置首行方便导航',
          '/修炼 突破拆分为 突破 + 突破 [丹药名]',
          '/探索 移除灵眼板块，新增悬赏任务板块',
          '/战斗 更新切磋/决斗描述（含气血消耗与冷却）',
          '/排行 移除成就列表，仅保留六大排行榜',
          '/银行 拆分为独立子菜单',
          '/玩家交易 新增移除物品/移除灵石功能',
        ],
      },
      {
        heading: '🏪 寄售系统优化',
        items: ['寄售价格改为单价制，手续费按总价计算', '购买寄售 <编号> [数量] 支持部分购买'],
      },
    ],
  },
  {
    version: 'v4.0.0',
    title: '古风视觉重构',
    sections: [
      {
        heading: '🎨 古风修仙主题重构',
        items: [
          '深色水墨背景 + 暗色宣纸纹理叠加，玄黑/藏青/月白/苍青主色调',
          '引入 Noto Serif SC 宋体字体，全局宋体排版',
          '所有卡片去除大圆角改为方角，添加内阴影厚重感',
          '物品卡片标题竖排 writing-mode: vertical-rl 显示',
          '五阶品级发光边框特效',
          '天地灵气粒子动效（particles.js 缓慢上升白光粒子）',
          '全站所有品阶表格行均带品阶发光边框',
        ],
      },
    ],
  },
  {
    version: 'v3.3.0',
    title: '寿命体系重构 + 数值资料库',
    sections: [
      {
        heading: '📊 寿命体系重构',
        items: [
          '突破寿命收益从扁平制改为阶梯型指数增长',
          '高境界突破带来质变级寿命飞跃（炼气5年→大罗金仙3000年）',
        ],
      },
      {
        heading: '🌐 数值资料库网页',
        items: ['新增 GitHub Pages 数值资料库，涵盖 9 大板块'],
      },
    ],
  },
];

export default function ChangelogPage() {
  return (
    <PageLayout title="更新日志" pageId="changelog" subtitle="模拟修仙2 版本历史">
      <div className="space-y-8">
        {changelog.map((release, ri) => (
          <div key={release.version}>
            {ri > 0 && <div className="decorative-line thin" />}
            <div className="bg-card rounded-xl border border-white/5 p-6 md:p-8 hover:border-[rgba(212,175,55,0.12)] transition-all duration-300 gold-glow">
            <div className="flex items-baseline gap-3 mb-6">
              <h2 className="text-xl font-semibold m-0" style={{ color: '#d4af37' }}>
                {release.version}
              </h2>
              <span className="text-sm" style={{ color: 'rgba(222,219,200,0.4)' }}>
                {release.title}
              </span>
            </div>

            <div className="space-y-5">
              {release.sections.map((section, si) => (
                <div key={si}>
                  <h3 className="text-sm font-medium mb-3 flex items-center gap-2" style={{ color: '#5fb3b3' }}>
                    <span className="jade-dot" />
                    {section.heading}
                  </h3>
                  <ul className="space-y-1.5 list-none p-0">
                    {section.items.map((item, ii) => (
                      <li key={ii} className="flex items-start gap-2 text-sm leading-relaxed">
                        <span className="w-1 h-1 rounded-full mt-2 shrink-0" style={{ background: '#5fb3b3', opacity: 0.4 }} />
                        <span className="text-gray-400">{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            </div>
          </div>
        ))}
      </div>
    </PageLayout>
  );
}
