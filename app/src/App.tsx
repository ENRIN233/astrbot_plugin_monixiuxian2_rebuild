import { HeroSection, AboutSection, StatsSection, SystemsSection, Footer } from './components/Sections';

function App() {
  return (
    <div className="bg-black" style={{ color: '#E1E0CC' }}>
      <HeroSection />
      <AboutSection />
      <StatsSection />
      <SystemsSection />
      <Footer />
    </div>
  );
}

export default App;
