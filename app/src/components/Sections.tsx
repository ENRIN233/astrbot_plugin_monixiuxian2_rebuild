import { motion, useInView } from 'framer-motion';
import { useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BookOpen, FlaskRound, Sword, Sparkles, Layers, Trophy, Gem, Zap, Users, Settings, Skull, Leaf, Swords } from 'lucide-react';

// ================== WordsPullUp ==================
interface WordsPullUpProps {
  text: string;
  className?: string;
  delay?: number;
}

export function WordsPullUp({ text, className = '', delay = 0 }: WordsPullUpProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });
  const words = text.split('');

  return (
    <span ref={ref} className={`inline-flex flex-wrap ${className}`}>
      {words.map((word, i) => (
        <motion.span
          key={i}
          className="relative inline-block mr-[0.05em] last:mr-0"
          initial={{ y: 20, opacity: 0 }}
          animate={isInView ? { y: 0, opacity: 1 } : {}}
          transition={{ duration: 0.5, delay: delay + i * 0.04, ease: [0.16, 1, 0.3, 1] }}
        >
          {word}
        </motion.span>
      ))}
    </span>
  );
}

// ================== AnimatedChar (Chinese char scroll-linked) ==================
interface AnimatedCharProps {
  text: string;
  className?: string;
}

export function AnimatedChar({ text, className = '' }: AnimatedCharProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <span ref={ref} className={className}>
      {text.split('').map((char, i) => (
        <motion.span
          key={i}
          className="inline-block"
          initial={{ opacity: 0.15 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ duration: 0.4, delay: i * 0.008, ease: 'easeOut' }}
        >
          {char}
        </motion.span>
      ))}
    </span>
  );
}

// ================== Hero Section ==================
export function HeroSection() {
  const navItems = [
    { label: '总览', href: '#data' },
    { label: '境界', href: '#systems' },
    { label: '炼丹', href: '#systems' },
    { label: '装备', href: '#systems' },
    { label: '战斗', href: '#systems' },
  ];

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  const videoRef = useRef<HTMLVideoElement>(null);

  // Pause video when tab is hidden, resume when visible — saves GPU decode
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const onVisibility = () => {
      if (document.hidden) video.pause();
      else { video.play().catch(() => {}); }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  return (
    <section className="relative h-screen w-full p-4 md:p-6">
      <div className="relative w-full h-full rounded-2xl md:rounded-[2rem] overflow-hidden">
        {/* Background video — GPU composited, no CSS filter (use overlay instead) */}
        {typeof window !== 'undefined' && window.innerWidth > 768 && (
          <video
            ref={videoRef}
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            className="absolute inset-0 w-full h-full object-cover"
            style={{ transform: 'translateZ(0)' }}
          >
            <source src="./videos/VID_20260710_001808.mp4" type="video/mp4" />
          </video>
        )}

        {/* Black overlay — replaces CSS filter: brightness(0.5), zero GPU cost */}
        <div className="absolute inset-0 bg-black/40 pointer-events-none" />

        {/* Background with radial glow */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#1a1510]/30 via-[#0a0806]/20 to-[#000]/50">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_20%,rgba(222,219,200,0.04),transparent_60%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_70%_80%,rgba(95,179,179,0.025),transparent_50%)]" />
        </div>

        {/* Noise overlay */}
        <div className="noise-overlay" />

        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/60 pointer-events-none" />

        {/* Navbar */}
        <nav className="absolute top-0 left-1/2 -translate-x-1/2 z-20">
          <div className="bg-black/60 backdrop-blur-sm rounded-b-2xl md:rounded-b-3xl px-4 py-2 md:px-8 border-x border-b border-white/5">
            <ul className="flex items-center gap-2 sm:gap-8 md:gap-12 lg:gap-14 list-none m-0 p-0 overflow-x-auto flex-nowrap" style={{ scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}>
              {navItems.map(item => (
                <li key={item.label}>
                  <button
                    onClick={() => scrollTo(item.href.replace('#', ''))}
                    className="text-[10px] sm:text-xs md:text-sm no-underline transition-colors duration-300 tracking-wider cursor-pointer bg-transparent border-none"
                    style={{ color: 'rgba(222,219,200,0.7)' }}
                  >
                    {item.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </nav>

        {/* Hero Content */}
        <div className="absolute bottom-0 left-0 right-0 p-8 md:p-12 lg:p-16">
          <div className="grid grid-cols-12 gap-4 md:gap-8">
            {/* Left: Giant Title */}
            <div className="col-span-12 md:col-span-7">
              <h1
                className="font-medium leading-[0.85] tracking-[-0.04em] m-0"
                style={{
                  fontSize: 'clamp(3.5rem, 22vw, 18vw)',
                  color: '#E1E0CC',
                }}
              >
                <WordsPullUp text="修仙" />
                <span className="block text-[0.3em] tracking-[0.3em] mt-2 font-light" style={{ color: 'rgba(222,219,200,0.4)' }}>
                  <WordsPullUp text="XIUXIAN" delay={0.3} />
                </span>
              </h1>
            </div>

            {/* Right: Text + CTA */}
            <div className="col-span-12 md:col-span-5 flex flex-col justify-end">
              <motion.p
                className="text-primary/70 text-xs sm:text-sm md:text-base leading-[1.4] mb-6 max-w-md"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
              >
                一款功能丰富的修仙模拟游戏插件，包含境界突破、炼丹炼器、宗门经营、
                世界Boss、神通战斗等 <strong>30+</strong> 游戏系统。
                本资料库汇总所有数值配置，方便查阅与平衡性分析。
              </motion.p>

              <motion.button
                onClick={() => scrollTo('data')}
                className="group inline-flex items-center gap-3 bg-primary rounded-full text-black font-medium text-sm sm:text-base px-6 py-3 w-fit cursor-pointer border-none"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.7, ease: [0.16, 1, 0.3, 1] }}
                whileHover={{ gap: '16px' }}
              >
                探索资料库
                <span className="inline-flex items-center justify-center bg-black rounded-full w-9 h-9 sm:w-10 sm:h-10 transition-transform duration-300 group-hover:scale-110">
                  <ArrowRight className="w-4 h-4 text-primary" />
                </span>
                </motion.button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ================== About Section ==================
export function AboutSection() {
  return (
    <section className="bg-black py-24 md:py-32 px-4">
      <div className="bg-[#101010] max-w-6xl mx-auto rounded-2xl p-8 md:p-16 lg:p-24 text-center border border-white/5">
        <p className="text-primary/50 text-[10px] sm:text-xs mb-8 tracking-[0.3em] uppercase font-light">
          模拟修仙2 · 数值资料库
        </p>

        <div className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl xl:text-7xl max-w-4xl mx-auto leading-[1.1] sm:leading-[1.05]">
          <WordsPullUp text="修仙之路，数据为鉴" delay={0.1} />
        </div>

        <div className="mt-10 max-w-2xl mx-auto text-sm sm:text-base leading-relaxed opacity-80">
          <AnimatedChar
            text="从江湖好手到合道飞升，跨越58个境界等级。灵根决定修炼速率，心法提供属性加成，丹药辅助突破瓶颈。世界Boss每小时刷新，悬赏令每日三次，秘境探险获取珍稀材料。"
            className="text-sm sm:text-base leading-relaxed"
          />
        </div>

        <div className="mt-10 max-w-2xl mx-auto text-sm sm:text-base leading-relaxed opacity-60">
          <AnimatedChar
            text="战斗系统支持神通自动触发、辅修功法增益、装备属性叠加。宗门建设、灵田种植、双修道侣……三十多个子系统构筑完整的修仙世界。"
            className="text-sm sm:text-base leading-relaxed"
          />
        </div>
      </div>
    </section>
  );
}

// ================== Systems Section ==================
function FeatureCard({ children, index, className = '' }: { children: React.ReactNode; index: number; className?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <motion.div
      ref={ref}
      className={`bg-[#101010] rounded-2xl overflow-hidden flex flex-col border border-white/5 ${className}`}
      initial={{ opacity: 0, y: 30 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay: index * 0.12, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

const gameSystems = [
  {
    icon: <Layers className="w-5 h-5" />,
    title: '境界系统',
    subtitle: '58级修炼体系',
    features: ['19大境界 × 3子阶段', '灵修/体修双路线', '突破失败累积加成', '丹药辅助突破'],
    color: '#DEDBC8',
  },
  {
    icon: <FlaskRound className="w-5 h-5" />,
    title: '炼丹系统',
    subtitle: '49种配方',
    features: ['寒热调和机制', '材料收集 + 炼制', '品阶影响成功率', '丹药背包管理'],
    color: '#5fb3b3',
  },
  {
    icon: <Sword className="w-5 h-5" />,
    title: '战斗系统',
    subtitle: '神通 + 装备',
    features: ['87种神通自动触发', '4类型：攻击/持续/增益/控制', '辅修功法增益体系', '暴击/穿透/吸血等属性'],
    color: '#c594c5',
  },
  {
    icon: <BookOpen className="w-5 h-5" />,
    title: '世界Boss',
    subtitle: '20档挑战',
    features: ['1小时自动刷新', '全服动态难度', 'CAS乐观锁首杀', '4档掉落材料体系'],
    color: '#ec5f67',
  },
  {
    icon: <Trophy className="w-5 h-5" />,
    title: '悬赏令',
    subtitle: '每日3次',
    features: ['100%掉落功法/神通', '14品阶加权随机', '等级缩放奖励', '4种难度等级'],
    color: '#99c794',
  },
  {
    icon: <Sparkles className="w-5 h-5" />,
    title: '装备锻造',
    subtitle: '配方打造',
    features: ['武器/防具锻造', '4品质等级随机', '材料收集体系', '品质概率：下40%/中35%/上20%/极5%'],
    color: '#eacb2c',
  },
];

export function SystemsSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  return (
    <section id="systems" className="relative bg-black py-24 md:py-32 px-4">
      <div className="bg-noise" />
      <div className="relative z-10 max-w-7xl mx-auto">
        <div ref={ref} className="text-center mb-16">
          <motion.h2
            className="text-4xl md:text-5xl font-medium leading-[1.1]"
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            style={{ color: '#E1E0CC' }}
          >
            游戏系统
          </motion.h2>
          <motion.p
            className="text-gray-500 text-base md:text-lg mt-4"
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          >
            三十多个子系统构筑完整修仙世界
          </motion.p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {gameSystems.map((sys, i) => (
            <FeatureCard key={sys.title} index={i}>
              <div className="p-6 md:p-8">
                <div className="flex items-center gap-3 mb-4">
                  <span className="w-10 h-10 rounded-lg bg-black/50 flex items-center justify-center" style={{ color: sys.color }}>
                    {sys.icon}
                  </span>
                  <div>
                    <h3 className="text-base font-semibold" style={{ color: '#E1E0CC' }}>
                      {sys.title}
                    </h3>
                    <p className="text-xs" style={{ color: 'rgba(222,219,200,0.4)' }}>{sys.subtitle}</p>
                  </div>
                </div>
                <ul className="space-y-2 list-none p-0">
                  {sys.features.map((f, fi) => (
                    <li key={fi} className="flex items-start gap-2 text-sm">
                      <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: sys.color, opacity: 0.5 }} />
                      <span className="text-gray-400">{f}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </FeatureCard>
          ))}
        </div>
      </div>
    </section>
  );
}

// ================== Stats Section ==================
const stats = [
  { value: '58', label: '境界等级' },
  { value: '87', label: '神通技能' },
  { value: '79', label: '主修心法' },
  { value: '105', label: '武器装备' },
  { value: '49', label: '炼丹配方' },
  { value: '14', label: '品阶等级' },
  { value: '30+', label: '游戏系统' },
  { value: '150+', label: '游戏指令' },
];

export function StatsSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  return (
    <section id="data" className="bg-black py-24 md:py-32 px-4 relative">
      <div className="relative z-10 max-w-7xl mx-auto">
        <div ref={ref} className="text-center mb-16">
          <motion.h2
            className="text-3xl md:text-4xl font-medium"
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            style={{ color: '#E1E0CC' }}
          >
            数据总览
          </motion.h2>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              className="bg-[#101010] rounded-2xl p-6 md:p-8 text-center border border-white/5"
              initial={{ opacity: 0, y: 20 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: 0.2 + i * 0.06, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="text-3xl md:text-4xl font-bold mb-2" style={{ color: '#DEDBC8' }}>
                {stat.value}
              </div>
              <div className="text-sm text-gray-500 tracking-wider">{stat.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Quick links */}
        <div className="mt-16 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {[
            { title: '境界数据', desc: '58级修炼体系详表', icon: <Layers className="w-4 h-4" />, to: '/levels' },
            { title: '丹药大全', desc: '突破丹/修为丹/功能丹', icon: <FlaskRound className="w-4 h-4" />, to: '/pills' },
            { title: '装备列表', desc: '武器/防具/心法/储物戒', icon: <Sword className="w-4 h-4" />, to: '/equipment' },
            { title: '神通图鉴', desc: '87种技能完整数据', icon: <Zap className="w-4 h-4" />, to: '/skills' },
            { title: '世界Boss', desc: '20档Boss掉落与Buff', icon: <Skull className="w-4 h-4" />, to: '/boss' },
            { title: '悬赏令', desc: '功法掉落14品阶权重', icon: <Trophy className="w-4 h-4" />, to: '/bounty' },
            { title: '锻造配方', desc: '52种武器防具锻造', icon: <Sparkles className="w-4 h-4" />, to: '/forging' },
            { title: '炼丹配方', desc: '49种配方材料与成功率', icon: <Leaf className="w-4 h-4" />, to: '/alchemy' },
            { title: '灵根系谱', desc: '11品阶修炼速率', icon: <Gem className="w-4 h-4" />, to: '/roots' },
            { title: '战斗公式', desc: 'HP/ATK/暴击/防御公式', icon: <Swords className="w-4 h-4" />, to: '/combat' },
            { title: '宗门系统', desc: '宗门建设/修炼/丹房配置', icon: <Users className="w-4 h-4" />, to: '/sect' },
            { title: '游戏配置', desc: '全局参数一览', icon: <Settings className="w-4 h-4" />, to: '/systems' },
          ].map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 15 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.4, delay: 0.6 + i * 0.05, ease: [0.16, 1, 0.3, 1] }}
              whileHover={{ y: -2 }}
            >
              <Link
                to={item.to}
                className="group bg-[#101010] rounded-xl p-4 md:p-5 border border-white/5 no-underline hover:border-primary/20 transition-all duration-300 block"
              >
                <div className="flex items-center gap-2 mb-1" style={{ color: 'rgba(222,219,200,0.6)' }}>
                  {item.icon}
                  <span className="text-sm font-medium" style={{ color: '#E1E0CC' }}>{item.title}</span>
                </div>
                <p className="text-xs text-gray-500 m-0">{item.desc}</p>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ================== Footer ==================
export function Footer() {
  return (
    <footer className="bg-black border-t border-white/5 py-10 px-4">
      <div className="max-w-6xl mx-auto text-center">
        <div className="w-10 h-10 mx-auto mb-4 bg-primary/10 rounded-lg flex items-center justify-center" style={{ color: '#DEDBC8' }}>
          <span className="text-lg font-serif">仙</span>
        </div>
        <p className="text-sm text-gray-500">
          模拟修仙2 · 数值资料库 v4.3.0
        </p>
        <p className="text-xs text-gray-600 mt-1">
          AstrBot Plugin · 数据源自游戏配置文件
        </p>
        <div className="flex justify-center gap-4 mt-4">
          <a href="https://github.com/ENRIN233/astrbot_plugin_monixiuxian2_rebuild" target="_blank" rel="noopener" className="text-xs text-gray-600 hover:text-gray-400 transition-colors no-underline">
            Github
          </a>
          <span className="text-xs text-gray-700">·</span>
          <span className="text-xs text-gray-600">数据来源</span>
          <span className="text-xs text-gray-700">·</span>
          <Link to="/changelog" className="text-xs text-gray-600 hover:text-gray-400 transition-colors no-underline">
            更新日志
          </Link>
        </div>
      </div>
    </footer>
  );
}
