# Dev Project Organizer 🚀

A clean and minimal Python Flask application to help developers organize and plan new projects with AI-powered insights using Groq (100% FREE & FAST!).

## Features

✨ **Project Management**
- Create and manage development projects
- Store project details and descriptions
- View all projects in a clean dashboard

🤖 **AI-Powered Analysis**
- Generate technical questions grouped by category
- Get recommended tech stack suggestions
- Receive ClickUp-style task plans
- Identify key project milestones

💾 **Data Persistence**
- Projects stored in JSON format
- Persistent storage between sessions
- Easy to backup and transfer

🎨 **Modern UI**
- Clean, responsive web interface
- Gradient backgrounds and smooth animations
- Mobile-friendly design

## Project Structure

```
dev_project_organizer/
│
├── app.py                  # Main Flask application with routes
├── ai_service.py           # AI plan generation using Groq API
├── storage.py              # JSON-based project storage
├── requirements.txt        # Python dependencies
├── README.md              # This file
│
├── templates/             # HTML templates
│   ├── base.html         # Base template with common layout
│   ├── index.html        # Home page - project list
│   ├── create.html       # Create project form
│   ├── project_detail.html  # Project details view
│   └── error.html        # Error page
│
└── projects.json         # Local data storage (auto-created)
```

## Installation

1. **Clone or download this project**

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   This will install Flask, Groq, and python-dotenv.

3. **Configure Groq API Key (100% FREE!)**
   
   Get your FREE API key from [Groq Console](https://console.groq.com/keys) - no credit card required!
   
   **Option 1: Environment Variable (Recommended)**
   ```bash
   # Windows PowerShell
   $env:GROQ_API_KEY="your-groq-api-key-here"
   
   # Windows CMD
   set GROQ_API_KEY=your-groq-api-key-here
   
   # Linux/Mac
   export GROQ_API_KEY="your-groq-api-key-here"
   ```
   
   **Option 2: .env File**
   ```bash
   # Copy the example file
   copy .env.example .env
   
   # Edit .env and add your API key
   GROQ_API_KEY=your-groq-api-key-here
   ```
   
   **Option 3: Direct in Code (Not Recommended)**
   
   Edit `ai_service.py` line 18:
   ```python
   client = Groq(api_key="your-groq-api-key-here")
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open in browser**
   ```
   http://127.0.0.1:5000
   ```

## Usage

### Creating a Project

1. Click **"Create Project"** on the home page
2. Enter your project name and detailed description
3. Click **"Generate AI Analysis"**
4. Review the AI-generated:
   - Technical questions by category
   - Recommended tech stack
   - Key milestones
   - ClickUp task plan
5. Click **"Save Project"** to store it

### Viewing Projects

- All projects are displayed on the home page
- Click any project card to view full details
- See technical questions, milestones, and task plans

### Deleting Projects

- Open a project detail page
- Click the **"Delete"** button
- Confirm deletion

## Data Structure

Projects are stored in `projects.json` with this structure:

```json
{
  "id": "uuid",
  "name": "Project Name",
  "created_at": "2025-10-16T10:00:00",
  "brief": "project description text",
  "ai_data": {
    "questions": {
      "Authentication & Authorization": ["question 1", "question 2"],
      "Database & Storage": ["question 1", "question 2"],
      "Security & Compliance": ["question 1"],
      "Architecture & Scalability": ["question 1"],
      "Others": ["question 1"]
    },
    "clickup_plan": "🚀 Phase 1: Setup\n- Task 1\n- Task 2\n...",
    "tech_stack_summary": "Django backend, React frontend, PostgreSQL database.",
    "key_milestones": [
      "Setup environment",
      "Implement authentication",
      "Integrate API",
      "Test & deploy"
    ]
  }
}
```

## AI Integration

The app uses **Groq's Llama 3.3 70B** model - completely FREE and incredibly FAST!

### How It Works

1. When you create a project and click "Generate AI Analysis", the app sends your project details to Groq
2. The AI analyzes your project and returns:
   - Categorized technical questions
   - Recommended tech stack
   - Key milestones
   - Detailed task plan with phases

### Model Configuration

By default, the app uses `llama-3.3-70b-versatile`. You can change this in `ai_service.py` line 70:

```python
model="llama-3.3-70b-versatile",  # Fast, powerful, and FREE!
```

**Available Groq models (all FREE):**
- `llama-3.3-70b-versatile` - Best balance (recommended) ⚡
- `llama-3.1-70b-versatile` - Very fast and capable
- `mixtral-8x7b-32768` - Good for longer contexts
- `gemma2-9b-it` - Lightweight and fast

### Why Groq?

- ✅ **100% FREE** - No credit card required
- ✅ **Ultra Fast** - Fastest inference in the market
- ✅ **Powerful** - Llama 3.3 70B is very capable
- ✅ **Generous Limits** - Much higher than competitors

### Customizing the AI Prompt

Edit the prompt in `ai_service.py` (lines 38-66) to customize what the AI generates.

## Customization

### Changing Storage Location

In `app.py`, modify the storage initialization:
```python
storage = ProjectStorage('path/to/your/projects.json')
```

### Modifying AI Categories

Edit the question categories in `ai_service.py`:
```python
questions = {
    "Your Category": [],
    "Another Category": [],
    # Add more categories
}
```

### Styling

All styles are embedded in the HTML templates. Modify the `<style>` blocks in:
- `templates/base.html` - Global styles
- Individual template files - Page-specific styles

## Error Handling

The app includes:
- Input validation for all forms
- Error messages for failed operations
- 404 and 500 error pages
- Try-catch blocks for API calls

## Development

### Running in Debug Mode

Debug mode is enabled by default in `app.py`:
```python
app.run(debug=True, host='127.0.0.1', port=5000)
```

### Testing the API

Test the AI generation endpoint:
```bash
curl -X POST http://127.0.0.1:5000/generate-plan \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Project","description":"A test project description"}'
```

## Requirements

- Python 3.7+
- Flask 3.0.0
- groq 0.11.0 (FREE AI API)
- python-dotenv 1.0.0

## License

This project is open source and available for personal and commercial use.

## Future Enhancements

- [ ] Export projects to PDF or Markdown
- [ ] Project templates for common types
- [ ] Collaboration features
- [ ] Integration with project management tools
- [ ] Advanced AI prompts and model selection
- [ ] Database migration to SQLite
- [ ] User authentication
- [ ] Project sharing capabilities

## Support

For issues or questions:
1. Check the code comments in each file
2. Review the error messages in the browser console
3. Ensure all dependencies are installed correctly

---

**Made with ❤️ for developers**

Happy coding! 🚀
