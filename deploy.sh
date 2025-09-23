#!/bin/bash

# Simple deployment script for Luna AI
echo "🚀 Deploying Luna Customer Support AI..."

# Check Python version
python3 --version

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOL
SECRET_KEY=your-super-secret-key-change-this-in-production
OPENAI_API_KEY=your-openai-api-key-here
ELEVENLABS_API_KEY=your-elevenlabs-api-key-here
DATABASE_URL=sqlite:///./customer_support.db
ENVIRONMENT=production
EOL
    echo "⚠️  Please update .env with your actual API keys!"
fi

# Initialize database
echo "Initializing database..."
rm -f customer_support.db
python3 -c "from app.services.faq_service import FAQService; FAQService()"

# Start the server
echo "Starting Luna AI server..."
echo "Access points:"
echo "  - Chat UI: http://localhost:8000/luna"
echo "  - Admin Panel: http://localhost:8000/admin"
echo "  - API Docs: http://localhost:8000/docs"
echo ""

# Run with production settings
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2