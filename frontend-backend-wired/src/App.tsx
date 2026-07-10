import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ExplorePage from './pages/ExplorePage'
import SimulationPage from './pages/SimulationPage'

import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/explore" replace />} />
        <Route path="/explore" element={<ExplorePage />} />
        <Route path="/simulation" element={<SimulationPage />} />
        <Route path="*" element={<Navigate to="/explore" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App