import { useState } from 'react';
import axios from 'axios';

function Login({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (isRegister && formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    try {
      const endpoint = isRegister ? '/api/auth/register' : '/api/auth/login';
      const response = await axios.post(endpoint, {
        email: formData.email,
        password: formData.password
      });

      if (response.data.access_token) {
        onLogin(response.data.access_token);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-600 to-purple-700">
      <div className="bg-white rounded-lg shadow-2xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-5xl mb-4">📬</div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">ALL-in-One</h1>
          <p className="text-gray-600">Email Campaign Management Platform</p>
        </div>

        <div className="flex mb-6 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => {
              setIsRegister(false);
              setError('');
            }}
            className={`flex-1 py-2 rounded-lg font-medium transition ${
              !isRegister ? 'bg-white shadow text-blue-600' : 'text-gray-600'
            }`}
          >
            Login
          </button>
          <button
            onClick={() => {
              setIsRegister(true);
              setError('');
            }}
            className={`flex-1 py-2 rounded-lg font-medium transition ${
              isRegister ? 'bg-white shadow text-blue-600' : 'text-gray-600'
            }`}
          >
            Register
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email Address
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="you@example.com"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
              required
            />
          </div>

          {isRegister && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Confirm Password
              </label>
              <input
                type="password"
                value={formData.confirmPassword}
                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••••"
                required
              />
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Please wait...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600">
            {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button
              onClick={() => {
                setIsRegister(!isRegister);
                setError('');
              }}
              className="text-blue-600 hover:underline font-medium"
            >
              {isRegister ? 'Login' : 'Register'}
            </button>
          </p>
        </div>

        <div className="mt-8 pt-6 border-t">
          <div className="text-xs text-gray-500 text-center">
            <p className="mb-2">✨ Features:</p>
            <ul className="space-y-1">
              <li>• Background campaign persistence (runs 24/7)</li>
              <li>• Real-time WebSocket updates</li>
              <li>• SMTP pool rotation with auto-disable</li>
              <li>• FROM address verification & extraction</li>
              <li>• Template personalization engine</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;
