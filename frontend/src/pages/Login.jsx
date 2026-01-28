import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import api from '../lib/api'

export default function Login() {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    const navigate = useNavigate()
    const setAuth = useAuthStore((state) => state.setAuth)

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError('')
        setLoading(true)

        try {
            const { data } = await api.post('/auth/login/', { email, password })
            const { user, access, refresh } = data

            setAuth(user, access, refresh)

            navigate(user.role === 'master_admin' ? '/master-admin' : '/college')
        } catch (err) {
            setError(err.response?.data?.error || 'Invalid credentials')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-100">
            <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl shadow-lg">
                <div className="px-8 pt-8 pb-6 border-b border-slate-200 text-center">
                    <h1 className="text-2xl font-semibold text-slate-800">
                        College Timetable System
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Administrative Login
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="px-8 py-6 space-y-5">
                    {error && (
                        <div className="text-sm bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded">
                            {error}
                        </div>
                    )}

                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">
                            Email
                        </label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600"
                            placeholder="admin@college.edu"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">
                            Password
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600"
                            placeholder="••••••••"
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-blue-700 text-white py-2.5 rounded-md font-medium hover:bg-blue-800 transition disabled:opacity-60"
                    >
                        {loading ? 'Authenticating…' : 'Sign in'}
                    </button>
                </form>

                <div className="px-8 pb-6 text-center text-xs text-slate-400">
                    Authorized personnel only
                </div>
            </div>
        </div>
    )
}