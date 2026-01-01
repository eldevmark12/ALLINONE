import React, { useEffect, useRef } from 'react';
import { Tag } from 'antd';
import './LogViewer.css';

const LogViewer = ({ logs, height = 500 }) => {
  const logContainerRef = useRef(null);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const getLogColor = (type) => {
    switch (type) {
      case 'success':
        return 'green';
      case 'error':
        return 'red';
      case 'warning':
        return 'orange';
      default:
        return 'blue';
    }
  };

  return (
    <div
      ref={logContainerRef}
      className="log-viewer"
      style={{ height: `${height}px` }}
    >
      {logs.length === 0 ? (
        <div className="log-empty">No logs available</div>
      ) : (
        logs.map((log, index) => (
          <div key={index} className="log-entry">
            <Tag color={getLogColor(log.type)} className="log-tag">
              {log.type.toUpperCase()}
            </Tag>
            <span className="log-timestamp">
              {new Date(log.timestamp).toLocaleTimeString()}
            </span>
            <span className="log-message">{log.message}</span>
          </div>
        ))
      )}
    </div>
  );
};

export default LogViewer;
