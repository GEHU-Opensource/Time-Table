import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Link } from 'react-router-dom'
import api from '../../lib/api'
import { AlertCircle, CheckCircle } from 'lucide-react'

export default function GenerateTimetable() {
  const [formData, setFormData] = useState({
    name: '',
    academic_year: '',
    semester: '',
    total_generations: 50,
  })
  const navigate = useNavigate()

  // Fetch resources to check availability
  const { data: resources, isLoading: resourcesLoading } = useQuery({
    queryKey: ['generation-resources'],
    queryFn: async () => {
      try {
        const [departments, teachers, subjects, sections, classrooms, mappings] = await Promise.all([
          api.get('/departments/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/teachers/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/subjects/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/sections/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/classrooms/').then(r => r.data.results || r.data || []).catch(() => []),
          api.get('/subject-teacher-mappings/').then(r => r.data.results || r.data || []).catch(() => []),
        ])
        return {
          departments: departments?.length || 0,
          teachers: teachers?.length || 0,
          subjects: subjects?.length || 0,
          sections: sections?.length || 0,
          classrooms: classrooms?.length || 0,
          mappings: mappings?.length || 0,
        }
      } catch (error) {
        return {
          departments: 0,
          teachers: 0,
          subjects: 0,
          sections: 0,
          classrooms: 0,
          mappings: 0,
        }
      }
    },
  })

  const generateMutation = useMutation({
    mutationFn: (data) => api.post('/generate-timetable/generate/', data),
    onSuccess: () => {
      navigate('/college/timetables')
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    generateMutation.mutate(formData)
  }

  const canGenerate = resources && 
    resources.departments > 0 &&
    resources.teachers > 0 &&
    resources.subjects > 0 &&
    resources.sections > 0 &&
    resources.classrooms > 0 &&
    resources.mappings > 0

  return (
    <div className="px-4 py-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Generate Timetable</h2>

      {/* Resource Status */}
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <h3 className="text-lg font-semibold mb-4">Resource Status</h3>
        {resourcesLoading ? (
          <div>Loading resources...</div>
        ) : (
          <div className="space-y-2">
            <ResourceStatus 
              label="Departments" 
              count={resources?.departments || 0} 
              required={true}
            />
            <ResourceStatus 
              label="Teachers" 
              count={resources?.teachers || 0} 
              required={true}
            />
            <ResourceStatus 
              label="Subjects" 
              count={resources?.subjects || 0} 
              required={true}
            />
            <ResourceStatus 
              label="Sections" 
              count={resources?.sections || 0} 
              required={true}
            />
            <ResourceStatus 
              label="Classrooms" 
              count={resources?.classrooms || 0} 
              required={true}
            />
            <ResourceStatus 
              label="Subject-Teacher Mappings" 
              count={resources?.mappings || 0} 
              required={true}
            />
          </div>
        )}

        {!canGenerate && (
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
            <div className="flex items-start">
              <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5 mr-2" />
              <div>
                <p className="text-sm text-yellow-800 font-medium">
                  Missing required resources to generate timetable
                </p>
                <p className="text-sm text-yellow-700 mt-1">
                  Please add all required resources in the <Link to="/college/resources" className="underline font-medium">Resources</Link> section.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Generation Form */}
      <form onSubmit={handleSubmit} className="bg-white p-6 rounded-lg shadow space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Timetable Name
          </label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-primary-500"
            placeholder="e.g., Fall 2024 Timetable"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Academic Year
          </label>
          <input
            type="text"
            value={formData.academic_year}
            onChange={(e) => setFormData({ ...formData, academic_year: e.target.value })}
            required
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-primary-500"
            placeholder="e.g., 2024-2025"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Semester
          </label>
          <input
            type="text"
            value={formData.semester}
            onChange={(e) => setFormData({ ...formData, semester: e.target.value })}
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-primary-500"
            placeholder="e.g., Fall"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Generations (Algorithm iterations)
          </label>
          <input
            type="number"
            value={formData.total_generations}
            onChange={(e) =>
              setFormData({ ...formData, total_generations: parseInt(e.target.value) || 50 })
            }
            min="1"
            max="200"
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-primary-500"
          />
          <p className="text-xs text-gray-500 mt-1">Higher values may take longer but produce better results</p>
        </div>
        {generateMutation.error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {generateMutation.error?.response?.data?.error || generateMutation.error.message || 'Failed to generate timetable'}
          </div>
        )}
        <button
          type="submit"
          disabled={generateMutation.isPending || !canGenerate}
          className="w-full bg-primary-600 text-white py-2 px-4 rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generateMutation.isPending ? 'Generating...' : 'Generate Timetable'}
        </button>
      </form>
    </div>
  )
}

function ResourceStatus({ label, count, required }) {
  const hasResource = count > 0
  return (
    <div className="flex items-center justify-between p-2 rounded">
      <div className="flex items-center space-x-2">
        {hasResource ? (
          <CheckCircle className="w-5 h-5 text-green-600" />
        ) : (
          <AlertCircle className="w-5 h-5 text-red-600" />
        )}
        <span className="text-sm text-gray-700">{label}</span>
        {required && <span className="text-xs text-red-500">*</span>}
      </div>
      <span className={`text-sm font-medium ${hasResource ? 'text-green-600' : 'text-red-600'}`}>
        {count}
      </span>
    </div>
  )
}
