import { Routes, Route, Link, useNavigate, Navigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import Colleges from './Colleges'
import Users from './Users'
import { LogOut, Building2, Users as UsersIcon } from 'lucide-react'

export default function MasterAdminDashboard() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center space-x-8">
              <h1 className="text-xl font-bold text-gray-900">Master Admin</h1>
              <div className="flex space-x-4">
                <Link
                  to="/master-admin/colleges"
                  className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  <Building2 className="w-4 h-4" />
                  <span>Colleges</span>
                </Link>
                <Link
                  to="/master-admin/users"
                  className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  <UsersIcon className="w-4 h-4" />
                  <span>Users</span>
                </Link>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-700">{user?.email}</span>
              <button
                onClick={handleLogout}
                className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md"
              >
                <LogOut className="w-4 h-4" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <Routes>
          <Route path="colleges/*" element={<Colleges />} />
          <Route path="users/*" element={<Users />} />
          <Route path="/" element={<Navigate to="/master-admin/colleges" replace />} />
        </Routes>
      </main>
    </div>
  )
}
