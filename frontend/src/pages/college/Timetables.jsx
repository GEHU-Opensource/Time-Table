import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import { Eye, Download } from 'lucide-react'
import * as XLSX from 'xlsx'

export default function Timetables() {
  const navigate = useNavigate()

  const { data: timetables, isLoading } = useQuery({
    queryKey: ['timetables'],
    queryFn: async () => {
      const response = await api.get('/timetables/')
      return response.data.results || response.data
    },
  })

  const exportToExcel = (timetable) => {
    if (!timetable?.timetable_data) return

    const workbook = XLSX.utils.book_new()
    const weekData = timetable.timetable_data[Object.keys(timetable.timetable_data)[0]] || {}
    
    const days = Object.keys(weekData)
    const sections = new Set()
    days.forEach(day => {
      Object.keys(weekData[day] || {}).forEach(section => sections.add(section))
    })
    
    const sheetData = [['Day', 'Time Slot', ...Array.from(sections)]]
    
    days.forEach(day => {
      const dayData = weekData[day] || {}
      const timeSlots = new Set()
      
      Object.values(dayData).forEach(sectionSchedule => {
        if (Array.isArray(sectionSchedule)) {
          sectionSchedule.forEach(entry => {
            if (entry?.time_slot) timeSlots.add(entry.time_slot)
          })
        }
      })
      
      Array.from(timeSlots).sort().forEach(timeSlot => {
        const row = [day, timeSlot]
        Array.from(sections).forEach(section => {
          const sectionSchedule = dayData[section] || []
          const entry = Array.isArray(sectionSchedule)
            ? sectionSchedule.find(e => e?.time_slot === timeSlot)
            : null
          row.push(entry ? `${entry.subject_id || ''} (${entry.teacher_id || ''}) - ${entry.classroom_id || ''}` : '')
        })
        sheetData.push(row)
      })
    })
    
    const worksheet = XLSX.utils.aoa_to_sheet(sheetData)
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Timetable')
    
    const fileName = `${timetable.name || 'timetable'}_${timetable.academic_year || 'unknown'}.xlsx`
    XLSX.writeFile(workbook, fileName)
  }

  if (isLoading) return <div className="p-6">Loading...</div>

  return (
    <div className="px-4 py-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Timetables</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {timetables?.map((timetable) => (
          <div key={timetable.id} className="bg-white p-6 rounded-lg shadow hover:shadow-lg transition">
            <h3 className="text-lg font-semibold mb-2">{timetable.name}</h3>
            <p className="text-sm text-gray-600 mb-4">
              {timetable.academic_year} - {timetable.semester}
            </p>
            <div className="flex justify-between items-center mb-4">
              <span
                className={`px-2 py-1 text-xs rounded-full ${
                  timetable.status === 'published'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-yellow-100 text-yellow-800'
                }`}
              >
                {timetable.status}
              </span>
              {timetable.fitness_score && (
                <span className="text-sm text-gray-600">
                  Score: {timetable.fitness_score.toFixed(2)}
                </span>
              )}
            </div>
            <div className="flex space-x-2">
              <button
                onClick={() => navigate(`/college/timetables/${timetable.id}`)}
                className="flex-1 flex items-center justify-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 text-sm"
              >
                <Eye className="w-4 h-4" />
                <span>View</span>
              </button>
              <button
                onClick={() => exportToExcel(timetable)}
                className="flex items-center justify-center space-x-2 bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm"
                title="Download Excel"
              >
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
        {(!timetables || timetables.length === 0) && (
          <div className="col-span-full text-center py-12 text-gray-500">
            No timetables found. Generate your first timetable!
          </div>
        )}
      </div>
    </div>
  )
}
