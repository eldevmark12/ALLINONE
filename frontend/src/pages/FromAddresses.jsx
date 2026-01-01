import { useState, useEffect } from 'react';
import axios from 'axios';

function FromAddresses() {
  const [addresses, setAddresses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [showExtractForm, setShowExtractForm] = useState(false);
  const [bulkText, setBulkText] = useState('');
  const [newAddress, setNewAddress] = useState({
    email: '',
    name: ''
  });
  const [extractConfig, setExtractConfig] = useState({
    imap_host: '',
    imap_port: 993,
    imap_email: '',
    imap_password: '',
    lookback_hours: 24,
    max_emails: 500
  });
  const [filter, setFilter] = useState('all'); // all, verified, unverified, dead

  useEffect(() => {
    fetchAddresses();
  }, []);

  const fetchAddresses = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get('/api/from-addresses', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAddresses(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching FROM addresses:', error);
      setLoading(false);
    }
  };

  const handleAddAddress = async (e) => {
    e.preventDefault();
    
    try {
      const token = localStorage.getItem('token');
      await axios.post('/api/from-addresses', newAddress, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setNewAddress({ email: '', name: '' });
      setShowAddForm(false);
      fetchAddresses();
    } catch (error) {
      alert('Error adding FROM address: ' + error.response?.data?.error);
    }
  };

  const handleBulkImport = async (e) => {
    e.preventDefault();
    
    try {
      const token = localStorage.getItem('token');
      const response = await axios.post('/api/from-addresses/bulk-import', {
        emails: bulkText
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      alert(response.data.message);
      setBulkText('');
      setShowBulkImport(false);
      fetchAddresses();
    } catch (error) {
      alert('Error importing FROM addresses: ' + error.response?.data?.error);
    }
  };

  const handleExtractFromInbox = async (e) => {
    e.preventDefault();
    
    try {
      const token = localStorage.getItem('token');
      const response = await axios.post('/api/from-addresses/extract-from-inbox', extractConfig, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      alert(`Extraction started! Task ID: ${response.data.task_id}\nThis will run in the background.`);
      setShowExtractForm(false);
      
      // Refresh after a delay
      setTimeout(fetchAddresses, 30000); // Refresh after 30 seconds
    } catch (error) {
      alert('Error starting extraction: ' + error.response?.data?.error);
    }
  };

  const deleteAddress = async (id) => {
    if (!confirm('Are you sure you want to delete this FROM address?')) return;
    
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`/api/from-addresses/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchAddresses();
    } catch (error) {
      alert('Error deleting FROM address: ' + error.response?.data?.error);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      verified: 'bg-green-100 text-green-800',
      unverified: 'bg-gray-100 text-gray-800',
      verifying: 'bg-yellow-100 text-yellow-800',
      dead: 'bg-red-100 text-red-800',
      collected: 'bg-blue-100 text-blue-800'
    };
    
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${styles[status] || styles.unverified}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  const filteredAddresses = addresses.filter(addr => {
    if (filter === 'all') return true;
    return addr.status === filter;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-xl">Loading FROM addresses...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">FROM Addresses</h1>
        <div className="flex space-x-3">
          <button
            onClick={() => setShowExtractForm(true)}
            className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-semibold"
          >
            Extract from Inbox
          </button>
          <button
            onClick={() => setShowBulkImport(true)}
            className="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-semibold"
          >
            Bulk Import
          </button>
          <button
            onClick={() => setShowAddForm(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold"
          >
            + Add Address
          </button>
        </div>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-500 text-sm mb-2">Total</p>
          <p className="text-3xl font-bold">{addresses.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-500 text-sm mb-2">Verified</p>
          <p className="text-3xl font-bold text-green-600">
            {addresses.filter(a => a.status === 'verified').length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-500 text-sm mb-2">Unverified</p>
          <p className="text-3xl font-bold text-gray-600">
            {addresses.filter(a => a.status === 'unverified').length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-500 text-sm mb-2">Dead</p>
          <p className="text-3xl font-bold text-red-600">
            {addresses.filter(a => a.status === 'dead').length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-500 text-sm mb-2">Collected</p>
          <p className="text-3xl font-bold text-blue-600">
            {addresses.filter(a => a.status === 'collected').length}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow mb-6 p-4">
        <div className="flex space-x-2 overflow-x-auto">
          {['all', 'verified', 'unverified', 'verifying', 'dead', 'collected'].map(status => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap ${
                filter === status
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Extract from Inbox Modal */}
      {showExtractForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4">
            <h2 className="text-2xl font-bold mb-4">Extract FROM Addresses from IMAP Inbox</h2>
            <form onSubmit={handleExtractFromInbox}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">IMAP Host*</label>
                  <input
                    type="text"
                    value={extractConfig.imap_host}
                    onChange={(e) => setExtractConfig({...extractConfig, imap_host: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg"
                    placeholder="imap.gmail.com"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">IMAP Port*</label>
                  <input
                    type="number"
                    value={extractConfig.imap_port}
                    onChange={(e) => setExtractConfig({...extractConfig, imap_port: parseInt(e.target.value)})}
                    className="w-full px-4 py-2 border rounded-lg"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">IMAP Email*</label>
                  <input
                    type="email"
                    value={extractConfig.imap_email}
                    onChange={(e) => setExtractConfig({...extractConfig, imap_email: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">IMAP Password*</label>
                  <input
                    type="password"
                    value={extractConfig.imap_password}
                    onChange={(e) => setExtractConfig({...extractConfig, imap_password: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Lookback Hours</label>
                  <input
                    type="number"
                    value={extractConfig.lookback_hours}
                    onChange={(e) => setExtractConfig({...extractConfig, lookback_hours: parseInt(e.target.value)})}
                    className="w-full px-4 py-2 border rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Max Emails</label>
                  <input
                    type="number"
                    value={extractConfig.max_emails}
                    onChange={(e) => setExtractConfig({...extractConfig, max_emails: parseInt(e.target.value)})}
                    className="w-full px-4 py-2 border rounded-lg"
                  />
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowExtractForm(false)}
                  className="px-6 py-2 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                >
                  Start Extraction
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Bulk Import Modal */}
      {showBulkImport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 max-w-2xl w-full mx-4">
            <h2 className="text-2xl font-bold mb-4">Bulk Import FROM Addresses</h2>
            <form onSubmit={handleBulkImport}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Email Addresses (one per line)
                </label>
                <textarea
                  value={bulkText}
                  onChange={(e) => setBulkText(e.target.value)}
                  className="w-full px-4 py-2 border rounded-lg h-64 font-mono text-sm"
                  placeholder="user@example.com&#10;another@example.com&#10;test@domain.com"
                  required
                />
              </div>
              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowBulkImport(false)}
                  className="px-6 py-2 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                >
                  Import
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Address Modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4">
            <h2 className="text-2xl font-bold mb-4">Add FROM Address</h2>
            <form onSubmit={handleAddAddress}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email*</label>
                  <input
                    type="email"
                    value={newAddress.email}
                    onChange={(e) => setNewAddress({...newAddress, email: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg"
                    placeholder="sender@example.com"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name (optional)</label>
                  <input
                    type="text"
                    value={newAddress.name}
                    onChange={(e) => setNewAddress({...newAddress, name: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg"
                    placeholder="John Doe"
                  />
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-6 py-2 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Add Address
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Address List */}
      {filteredAddresses.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <h3 className="text-xl font-semibold text-gray-700 mb-2">No FROM addresses found</h3>
          <p className="text-gray-500 mb-6">Add FROM addresses to use in your campaigns</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredAddresses.map(address => (
            <div key={address.id} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <h3 className="font-semibold text-lg">{address.email}</h3>
                    {getStatusBadge(address.status)}
                  </div>
                  {address.name && (
                    <p className="text-gray-600 text-sm mb-2">Name: {address.name}</p>
                  )}
                  <div className="flex items-center space-x-6 text-sm text-gray-500">
                    <span>Source: {address.source || 'manual'}</span>
                    {address.verified_at && (
                      <span>Verified: {new Date(address.verified_at).toLocaleDateString()}</span>
                    )}
                    {address.extracted_at && (
                      <span>Extracted: {new Date(address.extracted_at).toLocaleDateString()}</span>
                    )}
                  </div>
                  {address.last_error && (
                    <p className="text-red-600 text-sm mt-2">⚠️ {address.last_error}</p>
                  )}
                </div>
                <div className="flex space-x-2 ml-4">
                  <button
                    onClick={() => deleteAddress(address.id)}
                    className="px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 font-medium"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default FromAddresses;
