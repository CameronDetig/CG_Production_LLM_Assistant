# CG Production Assistant - Blender Addon

A Blender addon that provides an AI-powered chatbot interface for querying CG production asset metadata. Ask questions about files, search by visual similarity, and open .blend files directly from query results.

## Features

- **Natural Language Queries**: Ask questions in plain English about production assets
- **Visual Search**: Upload images or capture your viewport to find visually similar assets
- **Viewport Capture**: Render your current 3D view and use it for similarity search
- **Direct .blend Opening**: Download and open .blend files directly from query results
- **Conversation Management**: Save and resume conversations
- **Streaming Responses**: See SQL queries, results, and answers as they stream in

## Requirements

- Blender 2.93 or later (tested up to 4.x)
- Internet connection to reach the backend API
- Account on the CG Production Assistant platform (or use demo account)

## Installation

### Method 1: Install from ZIP (Recommended)

1. Download or create a ZIP file of the `frontend_blender` folder
2. Open Blender and go to **Edit > Preferences > Add-ons**
3. Click **Install...** and select the ZIP file
4. Enable the addon by checking the box next to "CG Production Assistant"

### Method 2: Install from Folder

1. Copy the `frontend_blender` folder to your Blender addons directory:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`
   - **macOS**: `~/Library/Application Support/Blender/<version>/scripts/addons/`
   - **Linux**: `~/.config/blender/<version>/scripts/addons/`
2. Rename the folder to `cg_production_assistant`
3. Open Blender and go to **Edit > Preferences > Add-ons**
4. Search for "CG Production Assistant" and enable it

## Configuration

### API Endpoint

The addon comes pre-configured with the default API endpoint. To change it:

1. Go to **Edit > Preferences > Add-ons**
2. Find "CG Production Assistant" and expand it
3. Update the **API Endpoint** field

### Demo Account

A demo account is provided for quick testing:
- Email: `demo@cgassistant.com`
- Password: `DemoPass10!`

You can change these defaults in the addon preferences.

## Usage

### Opening the Panel

1. In the 3D Viewport, press **N** to open the sidebar
2. Click on the **CG Assistant** tab

### Authentication

1. Click **Demo Login** for quick access with the demo account
2. Or expand **Authentication** and enter your credentials

### Sending Queries

1. Type your question in the message input field
2. Click **Send Message** or press Enter

Example queries:
- "Find all 4K renders from Charge"
- "Show me blend files with character rigs"
- "What files have moody lighting?"
- "Count videos longer than 30 seconds"

### Visual Search

#### Upload an Image
1. Click **Upload** in the "Image for Query" section
2. Select an image file
3. Type a query or just click **Send with Image**

#### Capture Viewport
1. Set up your 3D view with the desired angle
2. Click **Capture VP** (Capture Viewport)
3. The current view will be rendered at 512x512 and attached to your query
4. Type a query like "Find similar looking scenes" and send

### Opening .blend Files

When query results include .blend files:

1. Expand the **Blend Files** panel
2. Select a file from the list
3. Click **Open in Blender** to download and open it

**Note**: If you have unsaved changes, you'll be prompted to save first.

## Panel Overview

```
+-------------------------------+
| CG Production Assistant       |
+-------------------------------+
| > Authentication              |
|   [Demo Login]                |
|   Status: Logged in as...     |
+-------------------------------+
| > Conversations               |
|   [List of conversations]     |
|   [New] [Load] [Delete] [↻]   |
+-------------------------------+
| > Chat                        |
|   [Message history list]      |
|   [Selected message preview]  |
+-------------------------------+
| > Blend Files (if results)    |
|   [List of .blend files]      |
|   [Open in Blender] [Copy]    |
+-------------------------------+
| > Image for Query             |
|   [Upload] [Capture VP]       |
+-------------------------------+
| > Send Message                |
|   [Message input field]       |
|   [Send Message]              |
+-------------------------------+
```

## Troubleshooting

### "Connection error" when logging in

- Check your internet connection
- Verify the API endpoint is correct in addon preferences
- The backend may be experiencing a cold start (wait 10-20 seconds and try again)

### Viewport capture not working

- Make sure you're in the 3D Viewport (not Image Editor, etc.)
- Try switching to a different shading mode and back
- Check Blender's console for error messages

### .blend file won't open

- Ensure you have write permissions to your temp directory
- Check if the download URL has expired (try a new query)
- Large files may take time to download

### Chat not updating

- Check if the "Loading..." indicator is visible
- Blender's UI may need a manual refresh (move your mouse over the panel)
- Long queries may take up to 2 minutes for Lambda cold starts

## Development

### File Structure

```
frontend_blender/
├── __init__.py      # Addon registration and bl_info
├── properties.py    # PropertyGroups for state management
├── operators.py     # All operator classes
├── panels.py        # UI Panel definitions
├── api_client.py    # HTTP client with threading
├── utils.py         # Helper functions
├── README.md        # This file
└── .env.example     # Configuration template
```

### Building a ZIP for Distribution

```bash
cd /path/to/CG_Production_LLM_Assistant
zip -r cg_production_assistant.zip frontend_blender -x "*.pyc" -x "__pycache__/*" -x ".env"
```

## Backend Requirements

This addon requires the CG Production Assistant backend to be running. The backend provides:

- `/auth` - Authentication endpoint
- `/signup` - User registration
- `/chat` - Chat with streaming (SSE)
- `/conversations` - Conversation management

For .blend file downloads to work, the backend must have `SOURCE_BUCKET` configured and the `get_file_download_url()` function implemented.

## License

MIT License - See the main repository for details.

## Support

For issues and feature requests, please open an issue on the GitHub repository.
