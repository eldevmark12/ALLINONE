// Main JavaScript for ALL-in-One Email Portal

// Utility function to show toast notifications
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        const container = document.createElement('div');
        container.id = 'toastContainer';
        container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999;';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show`;
    toast.role = 'alert';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.getElementById('toastContainer').appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Format date/time
function formatDateTime(dateString) {
    if (!dateString) return '--';
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Format duration
function formatDuration(startTime) {
    if (!startTime) return '--:--';
    const start = new Date(startTime);
    const now = new Date();
    const diff = Math.floor((now - start) / 1000);
    
    const hours = Math.floor(diff / 3600);
    const minutes = Math.floor((diff % 3600) / 60);
    const seconds = diff % 60;
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

// Auto-refresh functionality
let refreshInterval = null;

function startAutoRefresh(callback, interval = 5000) {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    refreshInterval = setInterval(callback, interval);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Export for use in other scripts
window.appUtils = {
    showToast,
    formatDateTime,
    formatDuration,
    startAutoRefresh,
    stopAutoRefresh
};

// Initialize Socket.IO connection with optimized settings for render.com
try {
    if (typeof io !== 'undefined') {
        // Check if socket already exists (prevent multiple connections)
        if (window.socket && window.socket.connected) {
            console.log('✅ Socket.IO already connected - reusing existing connection');
        } else {
            window.socket = io({
                transports: ['polling', 'websocket'],  // Start with polling for better compatibility
                reconnection: true,
                reconnectionDelay: 2000,
                reconnectionDelayMax: 10000,
                reconnectionAttempts: Infinity,
                timeout: 60000,  // Increased from 20s to 60s for render.com
                pingTimeout: 60000,  // Time to wait for pong response (60s for render.com)
                pingInterval: 25000,  // How often to send ping (25s)
                autoConnect: true,
                forceNew: false,
                multiplex: true,
                upgrade: true,
                rememberUpgrade: true,
                // Additional render.com-specific settings
                path: '/socket.io/',
                secure: true,
                rejectUnauthorized: false
            });
        }
        
        socket.on('connect', function() {
            console.log('✅ Socket.IO connected (transport:', socket.io.engine.transport.name, ')');
        });
        
        socket.on('disconnect', function(reason) {
            if (reason === 'io server disconnect') {
                // Server disconnected, reconnect manually
                console.log('⚠️ Server disconnected - reconnecting...');
                socket.connect();
            } else {
                console.log('⚠️ Socket.IO disconnected:', reason);
            }
        });
        
        socket.on('connect_error', function(error) {
            console.error('❌ Socket.IO connection error:', error.message);
            console.log('💡 Falling back to polling transport...');
        });
        
        socket.on('reconnect', function(attemptNumber) {
            console.log('🔄 Socket.IO reconnected after', attemptNumber, 'attempts');
        });
        
        socket.on('reconnect_attempt', function(attemptNumber) {
            if (attemptNumber % 5 === 0) {
                console.log('🔄 Reconnection attempt:', attemptNumber);
            }
        });
        
        // Log transport upgrade
        socket.io.on('upgrade', function(transport) {
            console.log('⬆️ Transport upgraded to:', transport.name);
        });
    } else {
        console.warn('Socket.IO library not loaded');
    }
} catch (error) {
    console.error('Error initializing Socket.IO:', error);
}

console.log('ALL-in-One Email Portal loaded successfully');
