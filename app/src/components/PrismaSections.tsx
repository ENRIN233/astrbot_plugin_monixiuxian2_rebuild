import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import { ArrowRight, Check } from 'lucide-react';

// ================== WordsPullUp ==================
interface WordsPullUpProps {
  text: string;
  className?: string;
  delay?: number;
  showAsterisk?: boolean;
}

export function WordsPullUp({ text, className = '', delay = 0, showAsterisk }: WordsPullUpProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });
  const words = text.split(' ');

  return (
    <span ref={ref} className={`inline-flex flex-wrap ${className}`}>
      {words.map((word, i) => (
        <motion.span
          key={i}
          className="relative inline-block mr-[0.3em] last:mr-0"
          initial={{ y: 20, opacity: 0 }}
          animate={isInView ? { y: 0, opacity: 1 } : {}}
          transition={{ duration: 0.5, delay: delay + i * 0.08, ease: [0.16, 1, 0.3, 1] }}
        >
          {word}
          {showAsterisk && i === words.length - 1 && (
            <span className="absolute top-[0.65em] -right-[0.2em] text-[0.31em]">*</span>
          )}
        </motion.span>
      ))}
    </span>
  );
}

// ================== WordsPullUpMultiStyle ==================
interface TextSegment {
  text: string;
  className?: string;
}

interface MultiStyleProps {
  segments: TextSegment[];
  className?: string;
  delay?: number;
}

export function WordsPullUpMultiStyle({ segments, className = '', delay = 0 }: MultiStyleProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });
  let globalIdx = 0;

  const allWords = segments.map(seg => ({
    words: seg.text.split(' '),
    className: seg.className || '',
  }));

  return (
    <span ref={ref} className={`inline-flex flex-wrap justify-center ${className}`}>
      {allWords.map((seg, si) => {
        const segmentElements = seg.words.map((word, wi) => {
          const idx = globalIdx++;
          return (
            <motion.span
              key={`${si}-${wi}`}
              className={`inline-block mr-[0.3em] last:mr-0 ${seg.className}`}
              initial={{ y: 20, opacity: 0 }}
              animate={isInView ? { y: 0, opacity: 1 } : {}}
              transition={{ duration: 0.5, delay: delay + idx * 0.08, ease: [0.16, 1, 0.3, 1] }}
            >
              {word}
            </motion.span>
          );
        });
        return segmentElements;
      })}
    </span>
  );
}

// ================== AnimatedLetter (scroll-linked) ==================
interface AnimatedLetterProps {
  text: string;
  className?: string;
  style?: React.CSSProperties;
}

export function AnimatedLetter({ text, className = '', style }: AnimatedLetterProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <span ref={ref} className={className} style={style}>
      {text.split('').map((char, i) => (
        <motion.span
          key={i}
          className="inline-block"
          initial={{ opacity: 0.2 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ duration: 0.5, delay: i * 0.01, ease: 'easeOut' }}
        >
          {char === ' ' ? ' ' : char}
        </motion.span>
      ))}
    </span>
  );
}

// ================== Hero Section ==================
export function HeroSection() {
  return (
    <section className="relative h-screen w-full p-4 md:p-6">
      <div className="relative w-full h-full rounded-2xl md:rounded-[2rem] overflow-hidden">
        {/* Video placeholder */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#1a1510] via-[#0d0d0a] to-[#000]">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(222,219,200,0.03),transparent_70%)]" />
        </div>

        {/* Noise overlay */}
        <div className="noise-overlay" />

        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/60 pointer-events-none" />

        {/* Navbar */}
        <nav className="absolute top-0 left-1/2 -translate-x-1/2 z-20">
          <div className="bg-black rounded-b-2xl md:rounded-b-3xl px-4 py-2 md:px-8">
            <ul className="flex items-center gap-3 sm:gap-6 md:gap-12 lg:gap-14 list-none m-0 p-0">
              {['Our story', 'Collective', 'Workshops', 'Programs', 'Inquiries'].map(item => (
                <li key={item}>
                  <a
                    href="#"
                    className="text-[10px] sm:text-xs md:text-sm no-underline transition-colors duration-300"
                    style={{ color: 'rgba(225,224,204,0.8)' }}
                    onMouseEnter={e => (e.currentTarget.style.color = '#E1E0CC')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'rgba(225,224,204,0.8)')}
                  >
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </nav>

        {/* Hero Content */}
        <div className="absolute bottom-0 left-0 right-0 p-8 md:p-12 lg:p-16">
          <div className="grid grid-cols-12 gap-4 md:gap-8">
            {/* Left: Giant Heading */}
            <div className="col-span-12 md:col-span-8">
              <h1
                className="font-medium leading-[0.85] tracking-[-0.07em] m-0"
                style={{
                  fontSize: 'clamp(4rem, 26vw, 20vw)',
                  color: '#E1E0CC',
                }}
              >
                <WordsPullUp text="Prisma" />
              </h1>
            </div>

            {/* Right: Text + CTA */}
            <div className="col-span-12 md:col-span-4 flex flex-col justify-end">
              <motion.p
                className="text-primary/70 text-xs sm:text-sm md:text-base leading-[1.2] mb-6"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
              >
                Prisma is a worldwide network of visual artists, filmmakers and storytellers
                bound not by place, status or labels but by passion and hunger to unlock
                potential through our unique perspectives.
              </motion.p>

              <motion.button
                className="group inline-flex items-center gap-2 bg-primary rounded-full text-black font-medium text-sm sm:text-base px-6 py-3 w-fit cursor-pointer border-none"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.7, ease: [0.16, 1, 0.3, 1] }}
                whileHover={{ gap: '12px' }}
              >
                Join the lab
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
      <div className="bg-[#101010] max-w-6xl mx-auto rounded-2xl p-8 md:p-16 lg:p-24 text-center">
        <p className="text-primary text-[10px] sm:text-xs mb-8 tracking-widest uppercase">
          Visual arts
        </p>

        <div className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl xl:text-7xl max-w-3xl mx-auto leading-[0.95] sm:leading-[0.9]">
          <WordsPullUpMultiStyle
            segments={[
              { text: 'I am Marcus Chen,', className: 'font-normal' },
              { text: 'a self-taught director.', className: 'font-serif italic' },
              { text: 'I have skills in color grading, visual effects, and narrative design.', className: 'font-normal' },
            ]}
            delay={0.1}
          />
        </div>

        <div className="mt-12 max-w-2xl mx-auto">
          <AnimatedLetter
            text="Over the last seven years, I have worked with Parallax, a Berlin-based production house that crafts cinema, series, and Noir Studio in Paris. Together, we have created work that has earned international acclaim at several major festivals."
            className="text-xs sm:text-sm md:text-base leading-relaxed"
            style={{ color: '#DEDBC8' }}
          />
        </div>
      </div>
    </section>
  );
}

// ================== Features Section ==================
function FeatureCard({
  children,
  index,
}: {
  children: React.ReactNode;
  index: number;
}) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <motion.div
      ref={ref}
      className="bg-[#212121] rounded-2xl overflow-hidden flex flex-col"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={isInView ? { opacity: 1, scale: 1 } : {}}
      transition={{ duration: 0.6, delay: index * 0.15, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

function ChecklistItem({ text }: { text: string }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      <Check className="w-4 h-4 mt-0.5 shrink-0 text-primary" />
      <span className="text-gray-400">{text}</span>
    </li>
  );
}

export function FeaturesSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  return (
    <section className="relative min-h-screen bg-black py-24 md:py-32 px-4">
      <div className="bg-noise" />
      <div className="relative z-10 max-w-7xl mx-auto">
        {/* Header */}
        <div ref={ref} className="text-center mb-16">
          {isInView && (
            <>
              <WordsPullUpMultiStyle
                segments={[
                  { text: 'Studio-grade workflows for visionary creators.', className: '' },
                ]}
                delay={0.1}
              />
              <div className="mt-4">
                <WordsPullUpMultiStyle
                  segments={[
                    { text: 'Built for pure vision. Powered by art.', className: 'text-gray-500' },
                  ]}
                  delay={0.3}
                />
              </div>
            </>
          )}
        </div>

        {/* Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 lg:h-[480px]">
          {/* Card 1: Video */}
          <FeatureCard index={0}>
            <div className="relative flex-1 min-h-[200px] bg-gradient-to-br from-[#2a2520] to-[#1a1510] flex items-center justify-center">
              <p className="text-sm px-4 py-2" style={{ color: '#E1E0CC' }}>
                Video placeholder
              </p>
            </div>
            <div className="p-4">
              <p className="text-sm font-medium" style={{ color: '#E1E0CC' }}>
                Your creative canvas.
              </p>
            </div>
          </FeatureCard>

          {/* Card 2 */}
          <FeatureCard index={1}>
            <div className="flex-1 p-6 flex flex-col">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded bg-[#2a2a2a] mb-4 flex items-center justify-center text-lg">
                🎨
              </div>
              <h3 className="text-base font-semibold mb-1" style={{ color: '#E1E0CC' }}>
                Project Storyboard.
              </h3>
              <p className="text-xs text-gray-500 mb-4">(01)</p>
              <ul className="space-y-2 mb-6 list-none p-0">
                <ChecklistItem text="Visual timeline planning" />
                <ChecklistItem text="Scene-by-scene breakdown" />
                <ChecklistItem text="Collaborative annotation" />
                <ChecklistItem text="Version history tracking" />
              </ul>
              <button className="group flex items-center gap-2 text-xs text-primary mt-auto cursor-pointer bg-transparent border-none p-0">
                Learn more
                <ArrowRight className="w-3 h-3 transition-transform duration-300 -rotate-45 group-hover:rotate-0" />
              </button>
            </div>
          </FeatureCard>

          {/* Card 3 */}
          <FeatureCard index={2}>
            <div className="flex-1 p-6 flex flex-col">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded bg-[#2a2a2a] mb-4 flex items-center justify-center text-lg">
                🤖
              </div>
              <h3 className="text-base font-semibold mb-1" style={{ color: '#E1E0CC' }}>
                Smart Critiques.
              </h3>
              <p className="text-xs text-gray-500 mb-4">(02)</p>
              <ul className="space-y-2 mb-6 list-none p-0">
                <ChecklistItem text="AI-powered analysis" />
                <ChecklistItem text="Instant creative notes" />
                <ChecklistItem text="Tool integration ready" />
              </ul>
              <button className="group flex items-center gap-2 text-xs text-primary mt-auto cursor-pointer bg-transparent border-none p-0">
                Learn more
                <ArrowRight className="w-3 h-3 transition-transform duration-300 -rotate-45 group-hover:rotate-0" />
              </button>
            </div>
          </FeatureCard>

          {/* Card 4 */}
          <FeatureCard index={3}>
            <div className="flex-1 p-6 flex flex-col">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded bg-[#2a2a2a] mb-4 flex items-center justify-center text-lg">
                🧘
              </div>
              <h3 className="text-base font-semibold mb-1" style={{ color: '#E1E0CC' }}>
                Immersion Capsule.
              </h3>
              <p className="text-xs text-gray-500 mb-4">(03)</p>
              <ul className="space-y-2 mb-6 list-none p-0">
                <ChecklistItem text="Notification silencing" />
                <ChecklistItem text="Ambient soundscapes" />
                <ChecklistItem text="Schedule syncing" />
              </ul>
              <button className="group flex items-center gap-2 text-xs text-primary mt-auto cursor-pointer bg-transparent border-none p-0">
                Learn more
                <ArrowRight className="w-3 h-3 transition-transform duration-300 -rotate-45 group-hover:rotate-0" />
              </button>
            </div>
          </FeatureCard>
        </div>
      </div>
    </section>
  );
}
