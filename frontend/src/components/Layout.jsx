import { Link, useLocation } from 'react-router-dom';

function Layout({ children, onLogout }) {
  const location = useLocation();

  const navigation = [
    { name: 'Dashboard', path: '/dashboard', icon: '📊' },
    { name: 'Campaigns', path: '/campaigns', icon: '📧' },
    { name: 'SMTP Pool', path: '/smtp', icon: '🔌' },
    { name: 'FROM Addresses', path: '/from-addresses', icon: '📤' },
    { name: 'Templates', path: '/templates', icon: '📝' }
  ];

  const isActive = (path) => {
    if (path === '/campaigns') {
      return location.pathname.startsWith('/campaigns');
    }
    return location.pathname === path;
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Navigation */}
      <nav className="bg-white shadow-lg">
        <div className="container mx-auto px-4">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-8">
              <Link to="/dashboard" className="text-2xl font-bold text-blue-600">
                📬 ALL-in-One
              </Link>
              
              <div className="hidden md:flex space-x-1">
                {navigation.map((item) => (
                  <Link
                    key={item.name}
                    to={item.path}
                    className={`px-4 py-2 rounded-lg font-medium transition ${
                      isActive(item.path)
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <span className="mr-2">{item.icon}</span>
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>

            <button
              onClick={onLogout}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main>
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-12">
        <div className="container mx-auto px-4 py-6">
          <div className="text-center text-gray-600 text-sm">
            <p>© 2024 ALL-in-One Email Platform. Built with Flask + React + Celery.</p>
            <p className="mt-2">Background persistence powered by Celery workers.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default Layout;
