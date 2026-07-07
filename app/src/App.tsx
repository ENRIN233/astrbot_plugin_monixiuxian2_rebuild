import { HashRouter, Routes, Route } from 'react-router-dom';
import { HeroSection, AboutSection, StatsSection, SystemsSection, Footer } from './components/Sections';
import LevelsPage from './pages/LevelsPage';
import PillsPage from './pages/PillsPage';
import EquipmentPage from './pages/EquipmentPage';
import SkillsPage from './pages/SkillsPage';
import BossPage from './pages/BossPage';
import BountyPage from './pages/BountyPage';
import ForgingPage from './pages/ForgingPage';
import AlchemyPage from './pages/AlchemyPage';
import RootsPage from './pages/RootsPage';
import CombatPage from './pages/CombatPage';
import SectPage from './pages/SectPage';

function Landing() {
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

import ChangelogPage from './pages/ChangelogPage';

// ... keep all existing imports above

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/levels" element={<LevelsPage />} />
        <Route path="/pills" element={<PillsPage />} />
        <Route path="/equipment" element={<EquipmentPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/boss" element={<BossPage />} />
        <Route path="/bounty" element={<BountyPage />} />
        <Route path="/forging" element={<ForgingPage />} />
        <Route path="/alchemy" element={<AlchemyPage />} />
        <Route path="/roots" element={<RootsPage />} />
        <Route path="/combat" element={<CombatPage />} />
        <Route path="/sect" element={<SectPage />} />
        <Route path="/systems" element={<Landing />} />
        <Route path="/changelog" element={<ChangelogPage />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
