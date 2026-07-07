import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { HeroSection, AboutSection, FeaturesSection } from './components/PrismaSections';

// ================== Game Data Mini Section ==================
const gameStats = [
  { value: '58', label: '境界总数' },
  { value: '87', label: '神通数' },
  { value: '79', label: '主修心法' },
  { value: '105', label: '装备' },
  { value: '49', label: '炼丹配方' },
  { value: '14', label: '材料种类' },
];

function DataSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  return (
    <section className="bg-black py-24 md:py-32 px-4 relative">
      <div className="bg-noise" />
      <div className="relative z-10 max-w-6xl mx-auto">
        <div ref={ref} className="text-center mb-16">
          <motion.h2
            className="text-4xl md:text-5xl lg:text-6xl font-medium leading-[0.9]"
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            style={{ color: '#E1E0CC' }}
          >
            模拟修仙2
          </motion.h2>
          <motion.p
            className="text-gray-500 text-lg mt-4"
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            数值资料库 · 全面收录游戏配置数据
          </motion.p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-16">
          {gameStats.map((stat, i) => (
            <motion.div
              key={stat.label}
              className="bg-[#101010] rounded-2xl p-6 text-center border border-white/5"
              initial={{ opacity: 0, y: 20 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: 0.3 + i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="text-3xl font-bold mb-1" style={{ color: '#DEDBC8' }}>
                {stat.value}
              </div>
              <div className="text-sm text-gray-500">{stat.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Data sections */}
        <div className="space-y-8">
          <DataCard title="境界系统" description="58级修炼体系，19大境界，灵修/体修双路线" />
          <DataCard title="神通系统" description="87种战斗技能，4类型（攻击/持续/增益/控制），自动触发" />
          <DataCard title="炼丹系统" description="49个配方，材料收集+成功率，寒热调和机制" />
          <DataCard title="世界Boss" description="20档Boss等级，1小时刷新，CAS乐观锁首杀保护" />
          <DataCard title="装备锻造" description="收集材料打造武器防具，4品质等级（下品/中品/上品/极品）" />
          <DataCard title="悬赏令" description="每日3次，100%掉落功法/神通/辅修，按玩家等级缩放奖励" />
        </div>
      </div>
    </section>
  );
}

function DataCard({ title, description }: { title: string; description: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  return (
    <motion.div
      ref={ref}
      className="bg-[#101010] rounded-2xl p-6 md:p-8 border border-white/5 hover:border-primary/20 transition-colors duration-300"
      initial={{ opacity: 0, y: 20 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <h3 className="text-lg font-semibold mb-2" style={{ color: '#E1E0CC' }}>
        {title}
      </h3>
      <p className="text-sm text-gray-400">{description}</p>
    </motion.div>
  );
}

// ================== Footer ==================
function Footer() {
  return (
    <footer className="bg-black border-t border-white/5 py-8 px-4">
      <div className="max-w-6xl mx-auto text-center">
        <p className="text-sm text-gray-500">
          模拟修仙2 · 数值资料库 · v4.2.0
        </p>
        <p className="text-xs text-gray-600 mt-2">
          AstrBot Plugin · GitHub Pages
        </p>
      </div>
    </footer>
  );
}

// ================== App ==================
function App() {
  return (
    <div className="bg-black text-primary" style={{ color: '#E1E0CC' }}>
      <HeroSection />
      <AboutSection />
      <DataSection />
      <FeaturesSection />
      <Footer />
    </div>
  );
}

export default App;
