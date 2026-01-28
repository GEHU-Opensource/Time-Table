import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import api from '../../lib/api'
import { Plus, Edit, Trash2 } from 'lucide-react'

export default function Colleges() {
  const [showModal, setShowModal] = useState(false)
  const [editingCollege, setEditingCollege] = useState(null)
  const queryClient = useQueryClient()

  const { data: colleges, isLoading } = useQuery({
    queryKey: ['colleges'],
    queryFn: async () => {
      const response = await api.get('/colleges/')
      return response.data.results || response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/colleges/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['colleges'] })
      setShowModal(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) =>
      api.patch(`/colleges/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['colleges'] })
      setShowModal(false)
      setEditingCollege(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/colleges/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['colleges'] })
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const data = {
      name: formData.get('name'),
      code: formData.get('code'),
      subdomain: formData.get('subdomain'),
      email: formData.get('email'),
      phone: formData.get('phone'),
      address: formData.get('address'),
    }

    if (editingCollege) {
      updateMutation.mutate({ id: editingCollege.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div className="px-4 py-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Colleges</h2>
        <button
          onClick={() => {
            setEditingCollege(null)
            setShowModal(true)
          }}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          <span>Add College</span>
        </button>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Code
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Subdomain
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {colleges?.map((college) => (
              <tr key={college.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {college.name}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {college.code}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {college.subdomain || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      college.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {college.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => {
                      setEditingCollege(college)
                      setShowModal(true)
                    }}
                    className="text-indigo-600 hover:text-indigo-900 mr-4"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(college.id)}
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
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <h3 className="text-lg font-bold mb-4">
              {editingCollege ? 'Edit College' : 'Add College'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <input
                name="name"
                placeholder="College Name"
                required
                defaultValue={editingCollege?.name}
                className="w-full px-3 py-2 border rounded-md"
              />
              <input
                name="code"
                placeholder="Code"
                required
                defaultValue={editingCollege?.code}
                className="w-full px-3 py-2 border rounded-md"
              />
              <input
                name="subdomain"
                placeholder="Subdomain"
                defaultValue={editingCollege?.subdomain}
                className="w-full px-3 py-2 border rounded-md"
              />
              <input
                name="email"
                type="email"
                placeholder="Email"
                defaultValue={editingCollege?.email}
                className="w-full px-3 py-2 border rounded-md"
              />
              <input
                name="phone"
                placeholder="Phone"
                defaultValue={editingCollege?.phone}
                className="w-full px-3 py-2 border rounded-md"
              />
              <textarea
                name="address"
                placeholder="Address"
                defaultValue={editingCollege?.address}
                className="w-full px-3 py-2 border rounded-md"
              />
              <div className="flex space-x-2">
                <button
                  type="submit"
                  className="flex-1 bg-primary-600 text-white py-2 rounded-md hover:bg-primary-700"
                >
                  {editingCollege ? 'Update' : 'Create'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false)
                    setEditingCollege(null)
                  }}
                  className="flex-1 bg-gray-300 text-gray-700 py-2 rounded-md hover:bg-gray-400"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
