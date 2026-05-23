import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import BriefAssistant from './pages/BriefAssistant'
import CreateEvent from './pages/CreateEvent'
import Dashboard from './pages/Dashboard'
import EventDetail from './pages/EventDetail'
import OptimisationPage from './pages/OptimisationPage'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/events/new" element={<CreateEvent />} />
        <Route path="/events/:id" element={<EventDetail />} />
        <Route path="/events/:id/optimise" element={<OptimisationPage />} />
        <Route path="/briefs" element={<BriefAssistant />} />
      </Routes>
    </Layout>
  )
}
