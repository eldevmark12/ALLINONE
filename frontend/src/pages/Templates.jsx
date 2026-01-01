import { useState, useEffect } from 'react';
import axios from 'axios';

function Templates() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showEditor, setShowEditor] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [templateForm, setTemplateForm] = useState({
    name: '',
    subject: '',
    html_content: '',
    variables: ['RECIPIENT', 'NAME', 'DATE', 'RAND']
  });

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get('/api/templates', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTemplates(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching templates:', error);
      setLoading(false);
    }
  };

  const handleSaveTemplate = async (e) => {
    e.preventDefault();
    
    try {
      const token = localStorage.getItem('token');
      
      if (editingTemplate) {
        // Update existing template
        await axios.put(`/api/templates/${editingTemplate.id}`, templateForm, {
          headers: { Authorization: `Bearer ${token}` }
        });
      } else {
        // Create new template
        await axios.post('/api/templates', templateForm, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
      
      setShowEditor(false);
      setEditingTemplate(null);
      setTemplateForm({
        name: '',
        subject: '',
        html_content: '',
        variables: ['RECIPIENT', 'NAME', 'DATE', 'RAND']
      });
      fetchTemplates();
    } catch (error) {
      alert('Error saving template: ' + error.response?.data?.error);
    }
  };

  const handleEditTemplate = (template) => {
    setEditingTemplate(template);
    setTemplateForm({
      name: template.name,
      subject: template.subject,
      html_content: template.html_content,
      variables: template.variables || ['RECIPIENT', 'NAME', 'DATE', 'RAND']
    });
    setShowEditor(true);
  };

  const handleDeleteTemplate = async (id) => {
    if (!confirm('Are you sure you want to delete this template?')) return;
    
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`/api/templates/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchTemplates();
    } catch (error) {
      alert('Error deleting template: ' + error.response?.data?.error);
    }
  };

  const insertVariable = (variable) => {
    const textarea = document.getElementById('html_content');
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const text = templateForm.html_content;
      const before = text.substring(0, start);
      const after = text.substring(end, text.length);
      const newText = before + `{${variable}}` + after;
      
      setTemplateForm({ ...templateForm, html_content: newText });
      
      // Set cursor position after inserted variable
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = start + variable.length + 2;
        textarea.focus();
      }, 0);
    }
  };

  const exampleTemplate = `<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #007bff; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background: #f9f9f9; }
        .footer { text-align: center; padding: 20px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Hello {NAME}!</h1>
        </div>
        <div class="content">
            <p>Dear {RECIPIENT},</p>
            <p>This is a personalized email sent on {DATE}.</p>
            <p>Your unique number is: {RAND:1-1000}</p>
            <p>Thank you for your time!</p>
        </div>
        <div class="footer">
            <p>&copy; 2024 Your Company. All rights reserved.</p>
        </div>
    </div>
</body>
</html>`;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-xl">Loading templates...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Email Templates</h1>
        <button
          onClick={() => {
            setEditingTemplate(null);
            setTemplateForm({
              name: '',
              subject: '',
              html_content: '',
              variables: ['RECIPIENT', 'NAME', 'DATE', 'RAND']
            });
            setShowEditor(true);
          }}
          className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold"
        >
          + New Template
        </button>
      </div>

      {/* Template Editor Modal */}
      {showEditor && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
          <div className="bg-white rounded-lg p-8 max-w-4xl w-full mx-4 my-8">
            <h2 className="text-2xl font-bold mb-4">
              {editingTemplate ? 'Edit Template' : 'Create Template'}
            </h2>
            <form onSubmit={handleSaveTemplate}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Template Name*</label>
                  <input
                    type="text"
                    value={templateForm.name}
                    onChange={(e) => setTemplateForm({...templateForm, name: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg"
                    placeholder="My Campaign Template"
                    required
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Subject Line*</label>
                  <input
                    type="text"
                    value={templateForm.subject}
                    onChange={(e) => setTemplateForm({...templateForm, subject: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg"
                    placeholder="Hello {NAME}! Special offer for you"
                    required
                  />
                  <p className="text-sm text-gray-500 mt-1">You can use variables in the subject line too</p>
                </div>
                
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="block text-sm font-medium text-gray-700">HTML Content*</label>
                    <div className="flex space-x-2">
                      <span className="text-sm text-gray-500">Insert variable:</span>
                      {['RECIPIENT', 'NAME', 'DATE', 'RAND'].map(v => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => insertVariable(v)}
                          className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs hover:bg-blue-200"
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                  </div>
                  <textarea
                    id="html_content"
                    value={templateForm.html_content}
                    onChange={(e) => setTemplateForm({...templateForm, html_content: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg font-mono text-sm"
                    rows={20}
                    placeholder={exampleTemplate}
                    required
                  />
                  <div className="mt-2 p-3 bg-blue-50 rounded-lg">
                    <p className="text-sm font-semibold text-blue-800 mb-2">Available Variables:</p>
                    <ul className="text-sm text-blue-700 space-y-1">
                      <li><code className="bg-white px-2 py-1 rounded">{'{RECIPIENT}'}</code> - Recipient email address</li>
                      <li><code className="bg-white px-2 py-1 rounded">{'{NAME}'}</code> - Recipient name (email if no name)</li>
                      <li><code className="bg-white px-2 py-1 rounded">{'{DATE}'}</code> - Current date</li>
                      <li><code className="bg-white px-2 py-1 rounded">{'{RAND:1-100}'}</code> - Random number (specify range)</li>
                    </ul>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setShowEditor(false);
                    setEditingTemplate(null);
                  }}
                  className="px-6 py-2 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  {editingTemplate ? 'Update Template' : 'Create Template'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Templates List */}
      {templates.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="text-xl font-semibold text-gray-700 mb-2">No templates yet</h3>
          <p className="text-gray-500 mb-6">Create your first email template to get started</p>
          <button
            onClick={() => setShowEditor(true)}
            className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold"
          >
            Create Template
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map(template => (
            <div key={template.id} className="bg-white rounded-lg shadow hover:shadow-lg transition">
              <div className="p-6">
                <h3 className="text-xl font-semibold mb-2">{template.name}</h3>
                <p className="text-gray-600 text-sm mb-4">{template.subject}</p>
                
                <div className="mb-4">
                  <p className="text-xs text-gray-500 mb-2">Variables used:</p>
                  <div className="flex flex-wrap gap-2">
                    {(template.variables || []).map(variable => (
                      <span key={variable} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
                        {'{' + variable + '}'}
                      </span>
                    ))}
                  </div>
                </div>
                
                <div className="flex items-center justify-between text-xs text-gray-500 mb-4">
                  <span>Created: {new Date(template.created_at).toLocaleDateString()}</span>
                  {template.updated_at && template.updated_at !== template.created_at && (
                    <span>Updated: {new Date(template.updated_at).toLocaleDateString()}</span>
                  )}
                </div>
                
                <div className="flex space-x-2">
                  <button
                    onClick={() => handleEditTemplate(template)}
                    className="flex-1 px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 font-medium"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDeleteTemplate(template.id)}
                    className="flex-1 px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 font-medium"
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

export default Templates;
