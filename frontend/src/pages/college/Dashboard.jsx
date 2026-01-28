import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '../../stores/authStore'
import Timetables from './Timetables'
import TimetableDetail from './TimetableDetail'
import GenerateTimetable from './GenerateTimetable'
import Resources from './Resources'
import { LogOut, Calendar, Plus, Settings, Home, Building, Users, BookOpen, GraduationCap } from 'lucide-react'
import api from '../../lib/api'

export default function CollegeDashboard() {
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
              <h1 className="text-xl font-bold text-gray-900">
                {user?.college_name || 'College Dashboard'}
              </h1>
              <div className="flex space-x-4">
                <Link
                  to="/college"
                  className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  <Home className="w-4 h-4" />
                  <span>Dashboard</span>
                </Link>
                <Link
                  to="/college/timetables"
                  className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  <Calendar className="w-4 h-4" />
                  <span>Timetables</span>
                </Link>
                <Link
                  to="/college/resources"
                  className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  <Settings className="w-4 h-4" />
                  <span>Resources</span>
                </Link>
                <Link
                  to="/college/generate"
                  className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  <Plus className="w-4 h-4" />
                  <span>Generate</span>
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
          <Route path="timetables" element={<Timetables />} />
          <Route path="timetables/:id" element={<TimetableDetail />} />
          <Route path="generate" element={<GenerateTimetable />} />
          <Route path="resources" element={<Resources />} />
          <Route path="/" element={<DashboardHome />} />
        </Routes>
      </main>
    </div>
  )
}

function DashboardHome() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      try {
        const [timetables, departments, teachers, subjects, sections, classrooms] = await Promise.all([
          api.get('/timetables/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/departments/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/teachers/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/subjects/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/sections/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/classrooms/').then(r => r.data.results || r.data || []).catch(() => []),
        ])
        return {
          timetables: timetables?.length || 0,
          departments: departments?.length || 0,
          teachers: teachers?.length || 0,
          subjects: subjects?.length || 0,
          sections: sections?.length || 0,
          classrooms: classrooms?.length || 0,
        }
      } catch (error) {
        return {
          timetables: 0,
          departments: 0,
          teachers: 0,
          subjects: 0,
          sections: 0,
          classrooms: 0,
        }
      }
    },
  })

  if (isLoading) return <div className="p-6">Loading...</div>

  return (
    <div className="px-4 py-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Dashboard Overview</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard title="Timetables" value={stats?.timetables || 0} icon={Calendar} />
        <StatCard title="Departments" value={stats?.departments || 0} icon={Building} />
        <StatCard title="Teachers" value={stats?.teachers || 0} icon={Users} />
        <StatCard title="Subjects" value={stats?.subjects || 0} icon={BookOpen} />
        <StatCard title="Sections" value={stats?.sections || 0} icon={GraduationCap} />
        <StatCard title="Classrooms" value={stats?.classrooms || 0} icon={Building} />
      </div>
    </div>
  )
}

function StatCard({ title, value, icon: Icon }) {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-2">{value}</p>
        </div>
        <Icon className="w-8 h-8 text-primary-600" />
      </div>
    </div>
  )
}
