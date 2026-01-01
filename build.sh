#!/bin/bash

set -e  # Exit on error

echo "===== Starting build process ====="
echo "Current directory: $(pwd)"

# Install Python dependencies
echo "===== Installing Python dependencies ====="
pip install -r requirements.txt

# Install backend Node.js dependencies
echo "===== Installing backend dependencies ====="
cd backend
npm install
cd ..

# Install frontend dependencies and build
echo "===== Installing frontend dependencies ====="
cd frontend

# Check Node version
echo "Node version: $(node --version)"
echo "NPM version: $(npm --version)"

npm install

echo "===== Building React frontend ====="
CI=false npm run build

if [ -d "build" ]; then
    echo "✅ Build folder created successfully!"
    echo "Build folder contents:"
    ls -la build/
else
    echo "❌ ERROR: Build folder not created!"
    exit 1
fi

cd ..

echo "===== Build process finished! ====="
