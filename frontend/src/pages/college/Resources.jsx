import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'
import { Plus, Edit, Trash2, Users, BookOpen, Building, GraduationCap, Settings, X } from 'lucide-react'

export default function Resources() {
  const [activeTab, setActiveTab] = useState('departments')

  const tabs = [
    { id: 'departments', label: 'Departments', icon: Building },
    { id: 'teachers', label: 'Teachers', icon: Users },
    { id: 'subjects', label: 'Subjects', icon: BookOpen },
    { id: 'sections', label: 'Sections', icon: GraduationCap },
    { id: 'classrooms', label: 'Classrooms', icon: Building },
    { id: 'mappings', label: 'Subject-Teacher', icon: Settings },
    { id: 'preferences', label: 'Teacher Preferences', icon: Settings },
  ]

  return (
    <div className="px-4 py-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Resource Management</h2>
      
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8 overflow-x-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </nav>
      </div>

      <div>
        {activeTab === 'departments' && <DepartmentsTab />}
        {activeTab === 'teachers' && <TeachersTab />}
        {activeTab === 'subjects' && <SubjectsTab />}
        {activeTab === 'sections' && <SectionsTab />}
        {activeTab === 'classrooms' && <ClassroomsTab />}
        {activeTab === 'mappings' && <MappingsTab />}
        {activeTab === 'preferences' && <PreferencesTab />}
      </div>
    </div>
  )
}

// Modal Component
function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

// Departments Tab
function DepartmentsTab() {
  const [showModal, setShowModal] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const queryClient = useQueryClient()

  const { data: departments, isLoading } = useQuery({
    queryKey: ['departments'],
    queryFn: async () => {
      const response = await api.get('/departments/')
      return response.data.results || response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/departments/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] })
      setShowModal(false)
      setEditingItem(null)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => api.patch(`/departments/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] })
      setShowModal(false)
      setEditingItem(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/departments/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] })
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const data = {
      name: formData.get('name'),
      code: formData.get('code'),
    }
    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Departments</h3>
        <button
          onClick={() => {
            setEditingItem(null)
            setShowModal(true)
          }}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          <span>Add Department</span>
        </button>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {departments?.map((dept) => (
              <tr key={dept.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{dept.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{dept.code}</td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                  <button
                    onClick={() => {
                      setEditingItem(dept)
                      setShowModal(true)
                    }}
                    className="text-indigo-600 hover:text-indigo-900"
                  >
                    <Edit className="w-4 h-4 inline" />
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(dept.id)}
                    className="text-red-600 hover:text-red-900"
                  >
                    <Trash2 className="w-4 h-4 inline" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <Modal
          title={editingItem ? 'Edit Department' : 'Add Department'}
          onClose={() => {
            setShowModal(false)
            setEditingItem(null)
          }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                name="name"
                placeholder="Department Name"
                required
                defaultValue={editingItem?.name}
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Code</label>
              <input
                name="code"
                placeholder="Code"
                required
                defaultValue={editingItem?.code}
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
            <div className="flex space-x-2">
              <button
                type="submit"
                className="flex-1 bg-primary-600 text-white py-2 rounded-md hover:bg-primary-700"
              >
                {editingItem ? 'Update' : 'Create'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowModal(false)
                  setEditingItem(null)
                }}
                className="flex-1 bg-gray-300 text-gray-700 py-2 rounded-md hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

// Teachers Tab
function TeachersTab() {
  const [showModal, setShowModal] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const queryClient = useQueryClient()

  const { data: teachers, isLoading } = useQuery({
    queryKey: ['teachers'],
    queryFn: async () => {
      const response = await api.get('/teachers/')
      return response.data.results || response.data
    },
  })

  const { data: departments } = useQuery({
    queryKey: ['departments'],
    queryFn: async () => {
      const response = await api.get('/departments/')
      return response.data.results || response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/teachers/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teachers'] })
      setShowModal(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/teachers/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teachers'] })
    },
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    
    // First create user, then teacher
    const userData = {
      email: formData.get('email'),
      password: formData.get('password'),
      password2: formData.get('password'),
      first_name: formData.get('first_name'),
      last_name: formData.get('last_name'),
      role: 'faculty',
    }
    
    try {
      // Register user first
      const userResponse = await api.post('/auth/register/', userData)
      const userId = userResponse.data.user.id
      
      // Then create teacher
      const teacherData = {
        user: userId,
        employee_id: formData.get('employee_id'),
        department: formData.get('department'),
        designation: formData.get('designation'),
        max_weekly_hours: parseInt(formData.get('max_weekly_hours')) || 20,
      }
      
      createMutation.mutate(teacherData)
    } catch (error) {
      console.error('Error creating teacher:', error)
    }
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Teachers</h3>
        <button
          onClick={() => {
            setEditingItem(null)
            setShowModal(true)
          }}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          <span>Add Teacher</span>
        </button>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Employee ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Department</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Designation</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {teachers?.map((teacher) => (
              <tr key={teacher.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{teacher.user_name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{teacher.employee_id}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{teacher.department_name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{teacher.designation}</td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => deleteMutation.mutate(teacher.id)}
                    className="text-red-600 hover:text-red-900"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <Modal
          title="Add Teacher"
          onClose={() => {
            setShowModal(false)
            setEditingItem(null)
          }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
              <input name="first_name" required className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
              <input name="last_name" required className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input name="email" type="email" required className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input name="password" type="password" required className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Employee ID</label>
              <input name="employee_id" required className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
              <select name="department" required className="w-full px-3 py-2 border rounded-md">
                <option value="">Select Department</option>
                {departments?.map(dept => (
                  <option key={dept.id} value={dept.id}>{dept.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Designation</label>
              <input name="designation" required className="w-full px-3 py-2 border rounded-md" placeholder="e.g., Professor" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Weekly Hours</label>
              <input name="max_weekly_hours" type="number" defaultValue={20} className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div className="flex space-x-2">
              <button type="submit" className="flex-1 bg-primary-600 text-white py-2 rounded-md hover:bg-primary-700">
                Create
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowModal(false)
                  setEditingItem(null)
                }}
                className="flex-1 bg-gray-300 text-gray-700 py-2 rounded-md hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

// Subjects Tab
function SubjectsTab() {
  const [showModal, setShowModal] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const queryClient = useQueryClient()

  const { data: subjects, isLoading } = useQuery({
    queryKey: ['subjects'],
    queryFn: async () => {
      const response = await api.get('/subjects/')
      return response.data.results || response.data
    },
  })

  const { data: departments } = useQuery({
    queryKey: ['departments'],
    queryFn: async () => {
      const response = await api.get('/departments/')
      return response.data.results || response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/subjects/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects'] })
      setShowModal(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => api.patch(`/subjects/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects'] })
      setShowModal(false)
      setEditingItem(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/subjects/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects'] })
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const data = {
      code: formData.get('code'),
      name: formData.get('name'),
      credits: parseInt(formData.get('credits')),
      weekly_quota: parseInt(formData.get('weekly_quota')),
      is_lab: formData.get('is_lab') === 'on',
      department: formData.get('department') || null,
    }
    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Subjects</h3>
        <button
          onClick={() => {
            setEditingItem(null)
            setShowModal(true)
          }}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          <span>Add Subject</span>
        </button>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Credits</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Weekly Quota</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {subjects?.map((subject) => (
              <tr key={subject.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{subject.code}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">{subject.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{subject.credits}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{subject.weekly_quota}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <span className={`px-2 py-1 text-xs rounded-full ${subject.is_lab ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}`}>
                    {subject.is_lab ? 'Lab' : 'Theory'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                  <button
                    onClick={() => {
                      setEditingItem(subject)
                      setShowModal(true)
                    }}
                    className="text-indigo-600 hover:text-indigo-900"
                  >
                    <Edit className="w-4 h-4 inline" />
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(subject.id)}
                    className="text-red-600 hover:text-red-900"
                  >
                    <Trash2 className="w-4 h-4 inline" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <Modal
          title={editingItem ? 'Edit Subject' : 'Add Subject'}
          onClose={() => {
            setShowModal(false)
            setEditingItem(null)
          }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subject Code</label>
              <input name="code" required defaultValue={editingItem?.code} className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subject Name</label>
              <input name="name" required defaultValue={editingItem?.name} className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Credits</label>
              <input name="credits" type="number" required defaultValue={editingItem?.credits} className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Weekly Quota (Classes per week)</label>
              <input name="weekly_quota" type="number" required defaultValue={editingItem?.weekly_quota} className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
              <select name="department" defaultValue={editingItem?.department} className="w-full px-3 py-2 border rounded-md">
                <option value="">Select Department</option>
                {departments?.map(dept => (
                  <option key={dept.id} value={dept.id}>{dept.name}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center">
              <input name="is_lab" type="checkbox" defaultChecked={editingItem?.is_lab} className="mr-2" />
              <label className="text-sm font-medium text-gray-700">Is Lab Subject</label>
            </div>
            <div className="flex space-x-2">
              <button type="submit" className="flex-1 bg-primary-600 text-white py-2 rounded-md hover:bg-primary-700">
                {editingItem ? 'Update' : 'Create'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowModal(false)
                  setEditingItem(null)
                }}
                className="flex-1 bg-gray-300 text-gray-700 py-2 rounded-md hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

// Sections Tab
function SectionsTab() {
  const [showModal, setShowModal] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const queryClient = useQueryClient()

  const { data: sections, isLoading } = useQuery({
    queryKey: ['sections'],
    queryFn: async () => {
      const response = await api.get('/sections/')
      return response.data.results || response.data
    },
  })

  const { data: departments } = useQuery({
    queryKey: ['departments'],
    queryFn: async () => {
      const response = await api.get('/departments/')
      return response.data.results || response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/sections/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sections'] })
      setShowModal(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => api.patch(`/sections/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sections'] })
      setShowModal(false)
      setEditingItem(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/sections/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sections'] })
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const data = {
      name: formData.get('name'),
      student_strength: parseInt(formData.get('student_strength')),
      department: formData.get('department') || null,
      year: formData.get('year') ? parseInt(formData.get('year')) : null,
      semester: formData.get('semester') ? parseInt(formData.get('semester')) : null,
    }
    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Sections</h3>
        <button
          onClick={() => {
            setEditingItem(null)
            setShowModal(true)
          }}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          <span>Add Section</span>
        </button>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Strength</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Year</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Semester</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sections?.map((section) => (
              <tr key={section.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{section.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{section.student_strength}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{section.year || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{section.semester || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                  <button
                    onClick={() => {
                      setEditingItem(section)
                      setShowModal(true)
                    }}
                    className="text-indigo-600 hover:text-indigo-900"
                  >
                    <Edit className="w-4 h-4 inline" />
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(section.id)}
                    className="text-red-600 hover:text-red-900"
                  >
                    <Trash2 className="w-4 h-4 inline" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <Modal
          title={editingItem ? 'Edit Section' : 'Add Section'}
          onClose={() => {
            setShowModal(false)
            setEditingItem(null)
          }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Section Name</label>
              <input name="name" required defaultValue={editingItem?.name} className="w-full px-3 py-2 border rounded-md" placeholder="e.g., A" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Student Strength</label>
              <input name="student_strength" type="number" required defaultValue={editingItem?.student_strength} className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
              <select name="department" defaultValue={editingItem?.department} className="w-full px-3 py-2 border rounded-md">
                <option value="">Select Department</option>
                {departments?.map(dept => (
                  <option key={dept.id} value={dept.id}>{dept.name}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                <input name="year" type="number" defaultValue={editingItem?.year} className="w-full px-3 py-2 border rounded-md" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Semester</label>
                <input name="semester" type="number" defaultValue={editingItem?.semester} className="w-full px-3 py-2 border rounded-md" />
              </div>
            </div>
            <div className="flex space-x-2">
              <button type="submit" className="flex-1 bg-primary-600 text-white py-2 rounded-md hover:bg-primary-700">
                {editingItem ? 'Update' : 'Create'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowModal(false)
                  setEditingItem(null)
                }}
                className="flex-1 bg-gray-300 text-gray-700 py-2 rounded-md hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

// Classrooms Tab
function ClassroomsTab() {
  const [showModal, setShowModal] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const queryClient = useQueryClient()

  const { data: classrooms, isLoading } = useQuery({
    queryKey: ['classrooms'],
    queryFn: async () => {
      const response = await api.get('/classrooms/')
      return response.data.results || response.data
    },
  })

  const { data: departments } = useQuery({
    queryKey: ['departments'],
    queryFn: async () => {
      const response = await api.get('/departments/')
      return response.data.results || response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/classrooms/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classrooms'] })
      setShowModal(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => api.patch(`/classrooms/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classrooms'] })
      setShowModal(false)
      setEditingItem(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/classrooms/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classrooms'] })
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const data = {
      name: formData.get('name'),
      capacity: parseInt(formData.get('capacity')),
      is_lab: formData.get('is_lab') === 'on',
      department: formData.get('department') || null,
    }
    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Classrooms & Labs</h3>
        <button
          onClick={() => {
            setEditingItem(null)
            setShowModal(true)
          }}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          <span>Add Classroom/Lab</span>
        </button>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Capacity</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {classrooms?.map((classroom) => (
              <tr key={classroom.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{classroom.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{classroom.capacity}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <span className={`px-2 py-1 text-xs rounded-full ${classroom.is_lab ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}`}>
                    {classroom.is_lab ? 'Lab' : 'Classroom'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                  <button
                    onClick={() => {
                      setEditingItem(classroom)
                      setShowModal(true)
                    }}
                    className="text-indigo-600 hover:text-indigo-900"
                  >
                    <Edit className="w-4 h-4 inline" />
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(classroom.id)}
                    className="text-red-600 hover:text-red-900"
                  >
                    <Trash2 className="w-4 h-4 inline" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <Modal
          title={editingItem ? 'Edit Classroom/Lab' : 'Add Classroom/Lab'}
          onClose={() => {
            setShowModal(false)
            setEditingItem(null)
          }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input name="name" required defaultValue={editingItem?.name} className="w-full px-3 py-2 border rounded-md" placeholder="e.g., R101 or L101" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Capacity</label>
              <input name="capacity" type="number" required defaultValue={editingItem?.capacity} className="w-full px-3 py-2 border rounded-md" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
              <select name="department" defaultValue={editingItem?.department} className="w-full px-3 py-2 border rounded-md">
                <option value="">Select Department</option>
                {departments?.map(dept => (
                  <option key={dept.id} value={dept.id}>{dept.name}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center">
              <input name="is_lab" type="checkbox" defaultChecked={editingItem?.is_lab} className="mr-2" />
              <label className="text-sm font-medium text-gray-700">Is Lab</label>
            </div>
            <div className="flex space-x-2">
              <button type="submit" className="flex-1 bg-primary-600 text-white py-2 rounded-md hover:bg-primary-700">
                {editingItem ? 'Update' : 'Create'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowModal(false)
                  setEditingItem(null)
                }}
                className="flex-1 bg-gray-300 text-gray-700 py-2 rounded-md hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

// Subject-Teacher Mappings Tab
function MappingsTab() {
  const [showModal, setShowModal] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const queryClient = useQueryClient()

  const { data: mappings, isLoading } = useQuery({
    queryKey: ['mappings'],
    queryFn: async () => {
      const response = await api.get('/subject-teacher-mappings/')
      return response.data.results || response.data
    },
  })

  const { data: subjects } = useQuery({
    queryKey: ['subjects'],
    queryFn: async () => {
      const response = await api.get('/subjects/')
      return response.data.results || response.data
    },
  })

  const { data: teachers } = useQuery({
    queryKey: ['teachers'],
    queryFn: async () => {
      const response = await api.get('/teachers/')
      return response.data.results || response.data
    },
  })

  const { data: sections } = useQuery({
    queryKey: ['sections'],
    queryFn: async () => {
      const response = await api.get('/sections/')
      return response.data.results || response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/subject-teacher-mappings/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mappings'] })
      setShowModal(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/subject-teacher-mappings/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mappings'] })
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const data = {
      subject: formData.get('subject'),
      teacher: formData.get('teacher'),
      section: formData.get('section') || null,
      is_primary: formData.get('is_primary') === 'on',
    }
    createMutation.mutate(data)
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Subject-Teacher Mappings</h3>
        <button
          onClick={() => {
            setEditingItem(null)
            setShowModal(true)
          }}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          <span>Add Mapping</span>
        </button>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Subject</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Teacher</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Section</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Primary</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {mappings?.map((mapping) => (
              <tr key={mapping.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{mapping.subject_code} - {mapping.subject_name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{mapping.teacher_name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{mapping.section_name || 'All'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  {mapping.is_primary ? (
                    <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">Yes</span>
                  ) : (
                    <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-800">No</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => deleteMutation.mutate(mapping.id)}
                    className="text-red-600 hover:text-red-900"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <Modal
          title="Add Subject-Teacher Mapping"
          onClose={() => {
            setShowModal(false)
            setEditingItem(null)
          }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
              <select name="subject" required className="w-full px-3 py-2 border rounded-md">
                <option value="">Select Subject</option>
                {subjects?.map(subject => (
                  <option key={subject.id} value={subject.id}>{subject.code} - {subject.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Teacher</label>
              <select name="teacher" required className="w-full px-3 py-2 border rounded-md">
                <option value="">Select Teacher</option>
                {teachers?.map(teacher => (
                  <option key={teacher.id} value={teacher.id}>{teacher.user_name} ({teacher.employee_id})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Section (Optional)</label>
              <select name="section" className="w-full px-3 py-2 border rounded-md">
                <option value="">All Sections</option>
                {sections?.map(section => (
                  <option key={section.id} value={section.id}>{section.name}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center">
              <input name="is_primary" type="checkbox" defaultChecked className="mr-2" />
              <label className="text-sm font-medium text-gray-700">Primary Teacher</label>
            </div>
            <div className="flex space-x-2">
              <button type="submit" className="flex-1 bg-primary-600 text-white py-2 rounded-md hover:bg-primary-700">
                Create
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowModal(false)
                  setEditingItem(null)
                }}
                className="flex-1 bg-gray-300 text-gray-700 py-2 rounded-md hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

// Teacher Preferences Tab
function PreferencesTab() {
  const [showModal, setShowModal] = useState(false)
  const [selectedTeacher, setSelectedTeacher] = useState(null)
  const queryClient = useQueryClient()

  const { data: teachers } = useQuery({
    queryKey: ['teachers'],
    queryFn: async () => {
      const response = await api.get('/teachers/')
      return response.data.results || response.data
    },
  })

  const { data: preferences, isLoading } = useQuery({
    queryKey: ['preferences', selectedTeacher],
    queryFn: async () => {
      if (!selectedTeacher) return null
      const response = await api.get(`/teacher-preferences/?teacher=${selectedTeacher}`)
      return response.data.results?.[0] || response.data?.[0] || null
    },
    enabled: !!selectedTeacher,
  })

  const createOrUpdateMutation = useMutation({
    mutationFn: (data) => {
      if (preferences) {
        return api.patch(`/teacher-preferences/${preferences.id}/`, data)
      } else {
        return api.post('/teacher-preferences/', { ...data, teacher: selectedTeacher })
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preferences'] })
      setShowModal(false)
    },
  })

  const timeSlots = [
    { id: 1, label: '9:00 - 9:55' },
    { id: 2, label: '9:55 - 10:50' },
    { id: 3, label: '11:10 - 12:05' },
    { id: 4, label: '12:05 - 1:00' },
    { id: 5, label: '1:20 - 2:15' },
    { id: 6, label: '2:15 - 3:10' },
    { id: 7, label: '3:30 - 4:25' },
  ]

  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

  const handleSubmit = (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const preferredSlots = []
    const preferredDays = []
    const unavailableSlots = []

    timeSlots.forEach(slot => {
      if (formData.get(`pref_slot_${slot.id}`) === 'on') {
        preferredSlots.push(slot.id)
      }
      if (formData.get(`unavail_slot_${slot.id}`) === 'on') {
        unavailableSlots.push(slot.id)
      }
    })

    days.forEach(day => {
      if (formData.get(`pref_day_${day}`) === 'on') {
        preferredDays.push(day)
      }
    })

    createOrUpdateMutation.mutate({
      preferred_time_slots: preferredSlots,
      preferred_days: preferredDays,
      unavailable_slots: unavailableSlots,
    })
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Teacher Preferences</h3>
      </div>

      <div className="bg-white p-4 rounded-lg shadow mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">Select Teacher</label>
        <select
          value={selectedTeacher || ''}
          onChange={(e) => {
            setSelectedTeacher(e.target.value)
            setShowModal(false)
          }}
          className="w-full px-3 py-2 border rounded-md"
        >
          <option value="">Select a teacher</option>
          {teachers?.map(teacher => (
            <option key={teacher.id} value={teacher.id}>{teacher.user_name} ({teacher.employee_id})</option>
          ))}
        </select>
      </div>

      {selectedTeacher && (
        <div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 mb-4"
          >
            <Plus className="w-4 h-4" />
            <span>Edit Preferences</span>
          </button>

          {preferences && (
            <div className="bg-white p-4 rounded-lg shadow">
              <h4 className="font-semibold mb-2">Current Preferences</h4>
              <p className="text-sm text-gray-600">Preferred Time Slots: {preferences.preferred_time_slots?.join(', ') || 'None'}</p>
              <p className="text-sm text-gray-600">Preferred Days: {preferences.preferred_days?.join(', ') || 'None'}</p>
              <p className="text-sm text-gray-600">Unavailable Slots: {preferences.unavailable_slots?.join(', ') || 'None'}</p>
            </div>
          )}
        </div>
      )}

      {showModal && selectedTeacher && (
        <Modal
          title="Teacher Preferences"
          onClose={() => setShowModal(false)}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Preferred Time Slots</label>
              <div className="space-y-2">
                {timeSlots.map(slot => (
                  <label key={slot.id} className="flex items-center">
                    <input
                      type="checkbox"
                      name={`pref_slot_${slot.id}`}
                      defaultChecked={preferences?.preferred_time_slots?.includes(slot.id)}
                      className="mr-2"
                    />
                    <span className="text-sm">{slot.label}</span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Preferred Days</label>
              <div className="space-y-2">
                {days.map(day => (
                  <label key={day} className="flex items-center">
                    <input
                      type="checkbox"
                      name={`pref_day_${day}`}
                      defaultChecked={preferences?.preferred_days?.includes(day)}
                      className="mr-2"
                    />
                    <span className="text-sm">{day}</span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Unavailable Time Slots</label>
              <div className="space-y-2">
                {timeSlots.map(slot => (
                  <label key={slot.id} className="flex items-center">
                    <input
                      type="checkbox"
                      name={`unavail_slot_${slot.id}`}
                      defaultChecked={preferences?.unavailable_slots?.includes(slot.id)}
                      className="mr-2"
                    />
                    <span className="text-sm">{slot.label}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex space-x-2">
              <button type="submit" className="flex-1 bg-primary-600 text-white py-2 rounded-md hover:bg-primary-700">
                Save Preferences
              </button>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="flex-1 bg-gray-300 text-gray-700 py-2 rounded-md hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
