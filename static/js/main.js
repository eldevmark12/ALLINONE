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

// Initialize Socket.IO connection with crash-prevention for render.com
// Declare variables outside the block for proper scope
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
let isIntentionalDisconnect = false;

try {
    if (typeof io !== 'undefined') {
        // Check if socket already exists (prevent multiple connections)
        if (window.socket && window.socket.connected) {
            console.log('✅ Socket.IO already connected - reusing existing connection');
        } else {
            window.socket = io({
                transports: ['polling', 'websocket'],  // Start with polling for better compatibility
                reconnection: true,
                reconnectionDelay: 3000,              // Increased from 2s to 3s
                reconnectionDelayMax: 15000,          // Increased from 10s to 15s
                reconnectionAttempts: MAX_RECONNECT_ATTEMPTS,  // Limit attempts to prevent crashes
                timeout: 30000,                        // Reduced from 60s to 30s for faster failure detection
                pingTimeout: 30000,                    // Reduced from 60s to 30s
                pingInterval: 25000,                   // Keep at 25s
                autoConnect: true,
                forceNew: false,
                multiplex: true,
                upgrade: false,                        // DISABLE auto-upgrade to prevent WebSocket crashes
                rememberUpgrade: false,                // Don't remember WebSocket upgrades
                path: '/socket.io/',
                secure: true,
                rejectUnauthorized: false
            });
        }
        
        window.socket.on('connect', function() {
            reconnectAttempts = 0; // Reset on successful connection
            console.log('✅ Socket.IO connected (transport:', window.socket.io.engine.transport.name, ')');
        });
        
        window.socket.on('disconnect', function(reason) {
            // Don't try to reconnect if we're intentionally disconnecting
            if (isIntentionalDisconnect) {
                return;
            }
            
            console.log('⚠️ Socket.IO disconnected:', reason);
            
            // If server disconnected, try to reconnect ONCE
            if (reason === 'io server disconnect') {
                if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    console.log('🔄 Server disconnected - attempting reconnection...');
                    setTimeout(() => {
                        window.socket.connect();
                    }, 5000); // Wait 5 seconds before reconnecting
                } else {
                    console.warn('❌ Max reconnection attempts reached - stopping to prevent crash');
                }
            }
        });
        
        window.socket.on('connect_error', function(error) {
            reconnectAttempts++;
            
            // Only log every 3rd error to reduce console spam
            if (reconnectAttempts % 3 === 0) {
                console.warn(`⚠️ Socket.IO connection error (attempt ${reconnectAttempts}):`, error.message);
            }
            
            // Stop trying after max attempts
            if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                console.error('❌ Max connection attempts reached - disconnecting to prevent system freeze');
                isIntentionalDisconnect = true;
                window.socket.disconnect();
                
                // Show user-friendly message
                const msg = document.createElement('div');
                msg.className = 'alert alert-warning position-fixed top-0 start-50 translate-middle-x mt-3';
                msg.style.zIndex = '9999';
                msg.innerHTML = '⚠️ Real-time connection unavailable. Page will still work but updates may be delayed. <button class="btn-close" onclick="this.parentElement.remove()"></button>';
                document.body.appendChild(msg);
            }
        });
        
        window.socket.on('reconnect', function(attemptNumber) {
            reconnectAttempts = 0; // Reset on successful reconnect
            console.log('🔄 Socket.IO reconnected after', attemptNumber, 'attempts');
        });
        
        window.socket.on('reconnect_attempt', function(attemptNumber) {
            // Only log every 5th attempt to reduce spam
            if (attemptNumber % 5 === 0) {
                console.log('🔄 Reconnection attempt:', attemptNumber);
            }
        });
        
        window.socket.on('reconnect_failed', function() {
            console.error('❌ Socket.IO reconnection failed - giving up to prevent crash');
            isIntentionalDisconnect = true;
        });
        
        // REMOVE transport upgrade listener to prevent WebSocket crashes
        // socket.io.on('upgrade', ...) - REMOVED
        
        // Handle page unload gracefully
        window.addEventListener('beforeunload', function() {
            isIntentionalDisconnect = true;
            if (window.socket && window.socket.connected) {
                window.socket.disconnect();
            }
        });
    } else {
        console.warn('Socket.IO library not loaded');
    }
} catch (error) {
    console.error('Error initializing Socket.IO:', error);
}

console.log('ALL-in-One Email Portal loaded successfully');
