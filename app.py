"""
Simple Flask Web Application for Render Deployment
"""

from flask import Flask, jsonify, render_template_string
from datetime import datetime
import json

app = Flask(__name__)

# HTML template for the home page
HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALL-in-One Web Service</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
        }
        .endpoint {
            background: rgba(255, 255, 255, 0.2);
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }
        .endpoint code {
            background: rgba(0, 0, 0, 0.3);
            padding: 2px 8px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
        }
        .status {
            text-align: center;
            font-size: 1.2em;
            margin-top: 20px;
            padding: 15px;
            background: rgba(76, 175, 80, 0.3);
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 ALL-in-One Web Service</h1>
        <div class="status">
            ✅ Service is running successfully!
        </div>
        
        <h2>Available Endpoints:</h2>
        
        <div class="endpoint">
            <strong>GET /</strong><br>
            This page - Home page with API documentation
        </div>
        
        <div class="endpoint">
            <strong>GET /api/status</strong><br>
            Returns the current status of the service in JSON format
        </div>
        
        <div class="endpoint">
            <strong>GET /api/time</strong><br>
            Returns the current server time
        </div>
        
        <div class="endpoint">
            <strong>GET /api/fibonacci/<code>n</code></strong><br>
            Returns the Fibonacci sequence up to n terms<br>
            Example: <code>/api/fibonacci/10</code>
        </div>
        
        <div class="endpoint">
            <strong>GET /api/stats</strong><br>
            Calculate statistics from query parameters<br>
            Example: <code>/api/stats?numbers=1,2,3,4,5</code>
        </div>
        
        <div class="endpoint">
            <strong>GET /health</strong><br>
            Health check endpoint for monitoring
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    """Home page with API documentation."""
    return render_template_string(HOME_TEMPLATE)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route('/api/status')
def status():
    """Get service status."""
    return jsonify({
        "service": "ALL-in-One Web Service",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/time')
def get_time():
    """Get current server time."""
    now = datetime.now()
    return jsonify({
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": "UTC"
    })


@app.route('/api/fibonacci/<int:n>')
def fibonacci(n):
    """Generate Fibonacci sequence."""
    if n <= 0:
        return jsonify({"error": "n must be positive"}), 400
    if n > 100:
        return jsonify({"error": "n must be 100 or less"}), 400
    
    sequence = []
    if n >= 1:
        sequence.append(0)
    if n >= 2:
        sequence.append(1)
    
    while len(sequence) < n:
        sequence.append(sequence[-1] + sequence[-2])
    
    return jsonify({
        "n": n,
        "sequence": sequence,
        "last_value": sequence[-1] if sequence else 0
    })


@app.route('/api/stats')
def calculate_stats():
    """Calculate statistics from query parameters."""
    from flask import request
    
    numbers_str = request.args.get('numbers', '')
    if not numbers_str:
        return jsonify({"error": "Please provide 'numbers' query parameter (comma-separated)"}), 400
    
    try:
        numbers = [float(x.strip()) for x in numbers_str.split(',')]
    except ValueError:
        return jsonify({"error": "Invalid number format"}), 400
    
    if not numbers:
        return jsonify({"error": "No valid numbers provided"}), 400
    
    sorted_numbers = sorted(numbers)
    n = len(numbers)
    median = sorted_numbers[n // 2] if n % 2 else (sorted_numbers[n // 2 - 1] + sorted_numbers[n // 2]) / 2
    
    return jsonify({
        "count": n,
        "sum": sum(numbers),
        "mean": sum(numbers) / n,
        "median": median,
        "min": min(numbers),
        "max": max(numbers),
        "range": max(numbers) - min(numbers)
    })


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({
        "error": "Endpoint not found",
        "status": 404
    }), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors."""
    return jsonify({
        "error": "Internal server error",
        "status": 500
    }), 500


if __name__ == '__main__':
    # This is used when running locally
    app.run(host='0.0.0.0', port=5000, debug=False)
