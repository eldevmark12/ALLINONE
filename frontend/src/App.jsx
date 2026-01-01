import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Campaigns from './pages/Campaigns'
import CampaignDetails from './pages/CampaignDetails'
import SMTPPool from './pages/SMTPPool'
import FromAddresses from './pages/FromAddresses'
import Templates from './pages/Templates'
import Login from './pages/Login'
import api from './services/api'

function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if user is logged in
    const token = localStorage.getItem('token')
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      setUser({ token })
    }
    setLoading(false)
  }, [])

  const handleLogin = (token) => {
    localStorage.setItem('token', token)
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
    setUser({ token })
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    delete api.defaults.headers.common['Authorization']
    setUser(null)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-white text-xl">Loading...</div>
      </div>
    )
  }

  if (!user) {
    return <Login onLogin={handleLogin} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout onLogout={handleLogout} />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="campaigns" element={<Campaigns />} />
          <Route path="campaigns/:id" element={<CampaignDetails />} />
          <Route path="smtp" element={<SMTPPool />} />
          <Route path="from-addresses" element={<FromAddresses />} />
          <Route path="templates" element={<Templates />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
