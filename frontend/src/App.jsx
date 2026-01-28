import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Login from './pages/Login'
import MasterAdminDashboard from './pages/master-admin/Dashboard'
import CollegeDashboard from './pages/college/Dashboard'
import ProtectedRoute from './components/ProtectedRoute'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/master-admin/*"
            element={
              <ProtectedRoute allowedRoles={['master_admin']}>
                <MasterAdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/college/*"
            element={
              <ProtectedRoute allowedRoles={['college_admin', 'hod', 'faculty']}>
                <CollegeDashboard />
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
