require('dotenv').config();
const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');
const session = require('express-session');
const bodyParser = require('body-parser');
const path = require('path');

const { PORT, CORS_ORIGIN, SESSION_SECRET } = require('./config/constants');
const errorHandler = require('./middleware/errorHandler');
const setupWebSocket = require('./sockets/campaignSocket');

// Routes
const authRoutes = require('./routes/auth');
const smtpRoutes = require('./routes/smtp');
const emailRoutes = require('./routes/emails');
const campaignRoutes = require('./routes/campaign');
const templateRoutes = require('./routes/template');

// Initialize Express
const app = express();
const server = http.createServer(app);

// Initialize Socket.IO
const io = socketIo(server, {
  cors: {
    origin: CORS_ORIGIN,
    credentials: true
  }
});

// Middleware
app.use(cors({
  origin: CORS_ORIGIN,
  credentials: true
}));
app.use(bodyParser.json({ limit: '50mb' }));
app.use(bodyParser.urlencoded({ extended: true, limit: '50mb' }));

// Session middleware
app.use(session({
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: {
    maxAge: 24 * 60 * 60 * 1000, // 24 hours
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production'
  }
}));

// Setup WebSocket
setupWebSocket(io);

// API Routes
app.use('/api/auth', authRoutes);
app.use('/api/smtp', smtpRoutes);
app.use('/api/emails', emailRoutes);
app.use('/api/campaign', campaignRoutes);
app.use('/api/template', templateRoutes);

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    uptime: process.uptime()
  });
});

// Serve React Frontend (Production)
if (process.env.NODE_ENV === 'production') {
  const frontendPath = path.join(__dirname, '../../../frontend/build');
  
  console.log('=== Frontend Configuration ===');
  console.log('NODE_ENV:', process.env.NODE_ENV);
  console.log('Frontend path:', frontendPath);
  console.log('__dirname:', __dirname);
  
  // Check if build folder exists
  const fs = require('fs');
  if (fs.existsSync(frontendPath)) {
    console.log('✅ Frontend build folder exists');
    console.log('Contents:', fs.readdirSync(frontendPath));
  } else {
    console.error('❌ Frontend build folder NOT found at:', frontendPath);
    console.log('Trying alternative path...');
    const altPath = path.join(__dirname, '../../frontend/build');
    console.log('Alternative path:', altPath);
    if (fs.existsSync(altPath)) {
      console.log('✅ Found at alternative path!');
    }
  }
  
  // Serve static files
  app.use(express.static(frontendPath));
  
  // Handle React routing - return index.html for all non-API routes
  app.get('*', (req, res) => {
    const indexPath = path.join(frontendPath, 'index.html');
    if (fs.existsSync(indexPath)) {
      res.sendFile(indexPath);
    } else {
      res.status(500).json({ 
        success: false, 
        error: `Frontend not built. Looking for: ${indexPath}`,
        buildPath: frontendPath,
        exists: fs.existsSync(frontendPath)
      });
    }
  });
} else {
  // Development - API info
  app.get('/', (req, res) => {
    res.json({ 
      message: 'ALL-in-One Email Portal API',
      version: '1.0.0',
      status: 'running',
      mode: 'development'
    });
  });
}

// Error handler (must be last)
app.use(errorHandler);

// Start server
server.listen(PORT, () => {
  console.log(`
╔════════════════════════════════════════╗
║   ALL-in-One Email Portal Backend     ║
║   Server running on port ${PORT}         ║
║   Environment: ${process.env.NODE_ENV || 'development'}            ║
╚════════════════════════════════════════╝
  `);
  console.log(`API: http://localhost:${PORT}`);
  console.log(`WebSocket: ws://localhost:${PORT}`);
});

// Handle graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received. Shutting down gracefully...');
  server.close(() => {
    console.log('Server closed');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('\nSIGINT received. Shutting down gracefully...');
  server.close(() => {
    console.log('Server closed');
    process.exit(0);
  });
});

module.exports = { app, server, io };
