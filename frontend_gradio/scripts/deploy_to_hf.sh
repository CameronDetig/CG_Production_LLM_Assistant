#!/bin/bash
# Deploy CG Production Assistant frontend to Hugging Face Spaces

set -e  # Exit on error

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the frontend directory (parent of scripts/)
cd "$SCRIPT_DIR/.."

# Verify we're in the correct directory
if [ ! -f "app.py" ] || [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Could not find app.py or requirements.txt in frontend directory"
    exit 1
fi

echo "🚀 Deploying to Hugging Face Spaces..."
echo ""

# Load .env file if it exists
if [ -f ".env" ]; then
    echo "📄 Loading credentials from .env file..."
    export $(grep -v '^#' .env | xargs)
    echo ""
fi

# Check if HF_USERNAME is set
if [ -z "$HF_USERNAME" ]; then
    echo "❌ Error: HF_USERNAME not found"
    echo "Please add HF_USERNAME=your-username to your .env file"
    echo "Or set it with: export HF_USERNAME=your-huggingface-username"
    exit 1
fi

# Check if SPACE_NAME is set, use default if not
SPACE_NAME=${SPACE_NAME:-"cg-production-assistant"}

echo "📦 Deploying to: https://huggingface.co/spaces/$HF_USERNAME/$SPACE_NAME"
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📝 Initializing git repository..."
    git init
    echo ""
fi

# Check if HF remote exists
if git remote | grep -q "^hf$"; then
    echo "✓ Hugging Face remote already configured"
else
    echo "🔗 Adding Hugging Face remote..."
    git remote add hf https://huggingface.co/spaces/$HF_USERNAME/$SPACE_NAME
fi

echo ""
echo "📋 Files to be deployed:"
echo "  - app.py"
echo "  - requirements.txt"
echo "  - README.md"
echo "  - .gitignore"
echo ""

# Stage ONLY the essential files (everything else is ignored)
echo "📦 Staging files..."
git add -f app.py requirements.txt README.md .gitignore

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "✓ No changes to commit"
else
    echo "💾 Committing changes..."
    git commit -m "Deploy to Hugging Face Spaces"
fi

echo ""
echo "🚀 Pushing to Hugging Face Spaces..."
echo "   (You may be prompted for your Hugging Face credentials)"
echo ""

# Push to HF Spaces
git push hf main --force

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Your Space will be available at:"
echo "   https://huggingface.co/spaces/$HF_USERNAME/$SPACE_NAME"
echo ""
echo "⚙️  Next steps:"
echo "   1. Go to your Space settings"
echo "   2. Add Repository secrets:"
echo "      - API_ENDPOINT: Your AWS Lambda URL"
echo "      - DEMO_EMAIL: demo@cgassistant.com"
echo "      - DEMO_PASSWORD: DemoPass10!"
echo "   3. Wait for the Space to build (~2 minutes)"
echo "   4. Test your app!"
echo ""
