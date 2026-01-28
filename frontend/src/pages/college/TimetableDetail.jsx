import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../../lib/api'
import { ArrowLeft, Download } from 'lucide-react'
import * as XLSX from 'xlsx'

export default function TimetableDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const { data: timetable, isLoading } = useQuery({
    queryKey: ['timetable', id],
    queryFn: async () => {
      const response = await api.get(`/timetables/${id}/`)
      return response.data
    },
  })

  const exportToExcel = () => {
    if (!timetable?.timetable_data) return

    const workbook = XLSX.utils.book_new()

    // Process each week
    Object.keys(timetable.timetable_data).forEach((weekKey) => {
      const weekData = timetable.timetable_data[weekKey]
      
      // Create a sheet for each week
      const weekSheetData = []
      
      // Header row
      const days = Object.keys(weekData)
      const sections = new Set()
      
      // Collect all sections
      days.forEach(day => {
        Object.keys(weekData[day] || {}).forEach(section => sections.add(section))
      })
      
      // Create header
      const header = ['Day', 'Time Slot', ...Array.from(sections)]
      weekSheetData.push(header)
      
      // Process each day
      days.forEach(day => {
        const dayData = weekData[day] || {}
        const timeSlots = new Set()
        
        // Collect all time slots for this day
        Object.values(dayData).forEach(sectionSchedule => {
          if (Array.isArray(sectionSchedule)) {
            sectionSchedule.forEach(entry => {
              if (entry?.time_slot) timeSlots.add(entry.time_slot)
            })
          }
        })
        
        // Create rows for each time slot
        Array.from(timeSlots).sort().forEach(timeSlot => {
          const row = [day, timeSlot]
          
          Array.from(sections).forEach(section => {
            const sectionSchedule = dayData[section] || []
            const entry = Array.isArray(sectionSchedule) 
              ? sectionSchedule.find(e => e?.time_slot === timeSlot)
              : null
            
            if (entry) {
              const cellValue = `${entry.subject_id || ''}\n${entry.teacher_id || ''}\n${entry.classroom_id || ''}`
              row.push(cellValue)
            } else {
              row.push('')
            }
          })
          
          weekSheetData.push(row)
        })
      })
      
      const worksheet = XLSX.utils.aoa_to_sheet(weekSheetData)
      XLSX.utils.book_append_sheet(workbook, worksheet, weekKey.substring(0, 31)) // Excel sheet name limit
    })
    
    // Download
    const fileName = `${timetable.name || 'timetable'}_${timetable.academic_year || 'unknown'}.xlsx`
    XLSX.writeFile(workbook, fileName)
  }

  if (isLoading) return <div className="p-6">Loading...</div>
  if (!timetable) return <div className="p-6">Timetable not found</div>

  const timetableData = timetable.timetable_data || {}

  return (
    <div className="px-4 py-6">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/college/timetables')}
            className="p-2 hover:bg-gray-100 rounded-md"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{timetable.name}</h2>
            <p className="text-sm text-gray-600">
              {timetable.academic_year} - {timetable.semester}
            </p>
          </div>
        </div>
        <button
          onClick={exportToExcel}
          className="flex items-center space-x-2 bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700"
        >
          <Download className="w-4 h-4" />
          <span>Export Excel</span>
        </button>
      </div>

      <div className="space-y-6">
        {Object.keys(timetableData).map((weekKey) => {
          const weekData = timetableData[weekKey]
          const days = Object.keys(weekData || {})
          const sections = new Set()
          
          days.forEach(day => {
            const dayData = weekData[day] || {}
            Object.keys(dayData).forEach(section => sections.add(section))
          })

          return (
            <div key={weekKey} className="bg-white rounded-lg shadow overflow-hidden">
              <div className="bg-primary-600 text-white px-6 py-3">
                <h3 className="text-lg font-semibold">{weekKey}</h3>
              </div>
              
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase sticky left-0 bg-gray-50">Day</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time Slot</th>
                      {Array.from(sections).map(section => (
                        <th key={section} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase min-w-[200px]">
                          Section {section}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {days.map(day => {
                      const dayData = weekData[day] || {}
                      const timeSlots = new Set()
                      
                      Object.values(dayData).forEach(sectionSchedule => {
                        if (Array.isArray(sectionSchedule)) {
                          sectionSchedule.forEach(entry => {
                            if (entry?.time_slot) timeSlots.add(entry.time_slot)
                          })
                        }
                      })
                      
                      return Array.from(timeSlots).sort().map((timeSlot, idx) => (
                        <tr key={`${day}-${timeSlot}`} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          {idx === 0 && (
                            <td rowSpan={timeSlots.size} className="px-4 py-3 text-sm font-medium text-gray-900 align-middle sticky left-0 bg-white border-r">
                              {day}
                            </td>
                          )}
                          <td className="px-4 py-3 text-sm text-gray-500">{timeSlot}</td>
                          {Array.from(sections).map(section => {
                            const sectionSchedule = dayData[section] || []
                            const entry = Array.isArray(sectionSchedule)
                              ? sectionSchedule.find(e => e?.time_slot === timeSlot)
                              : null
                            
                            return (
                              <td key={section} className="px-4 py-3 text-sm border-l">
                                {entry ? (
                                  <div className="space-y-1">
                                    <div className="font-medium text-primary-700">{entry.subject_id || '-'}</div>
                                    <div className="text-gray-600 text-xs">{entry.teacher_id || '-'}</div>
                                    <div className="text-gray-400 text-xs">{entry.classroom_id || '-'}</div>
                                  </div>
                                ) : (
                                  <span className="text-gray-300">-</span>
                                )}
                              </td>
                            )
                          })}
                        </tr>
                      ))
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
