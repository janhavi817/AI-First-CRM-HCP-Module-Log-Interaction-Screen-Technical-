# Aegis CRM: Healthcare Professional (HCP) Interaction Module

An AI-First CRM module designed for life sciences and pharmaceutical sales representatives to seamlessly log and edit interaction logs using a conversational interface driven by **LangGraph** and **Groq LLM (Gemma-2-9b-it)**.

## 🚀 Key Features

1. **Split-Screen Workspace**:
   - **Left Panel (Structured CRM Form)**: Displays HCP name, interaction type, date, time, attendees, topics discussed, sentiment, materials distributed, and an AI-generated executive summary. By default, this is locked to ensure programmatically correct inputs via AI, but supports a **Manual Override Mode** for sales representatives.
   - **Right Panel (Conversational AI Assistant)**: Allows representative to log interactions via natural language prompts, check details, edit form fields, search doctors, view product sheets, and schedule follow-ups.
2. **LangGraph StateGraph & 5 Sales Tools**:
   - `log_interaction`: Parses natural language prompt entities to populate fields.
   - `edit_interaction`: Updates specific form fields on request while preserving others.
   - `search_hcp`: Queries the database for HCP details, hospitals, or specialties.
   - `get_product_info`: Fetches drug descriptions and brochures (e.g., *Prodo-X*, *CardioShield*).
   - `schedule_followup`: Schedules follow-up tasks linked to the database.
3. **Execution Node Visualizer**:
   - Real-time workflow chart lighting up nodes during agent execution: `User Request` ➔ `LLM Agent (Decision)` ➔ `Tools Node` ➔ `Form Render`. Shows exactly how LangGraph processes the request.
4. **Resilient Mock Mode**:
   - Automatically falls back to a smart mock agent if no `GROQ_API_KEY` is provided, enabling instant offline review.
5. **Database Interoperability**:
   - Uses SQLAlchemy. Connects to SQLite by default, but can be switched to MySQL or PostgreSQL by editing the `.env` connection string.

---

## 📂 Project Structure

```text
Naukri project/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── agent.py         # LangGraph workflow, tool declarations, mock agent
│   │   ├── database.py      # SQLAlchemy models & seeding initial HCP / Product records
│   │   ├── main.py          # FastAPI application routing & server endpoints
│   │   └── schemas.py       # Pydantic schemas for data serialization
│   ├── .env                 # Environment variables (GROQ_API_KEY)
│   └── requirements.txt     # Python requirements
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AIChat.jsx             # AI chat bubbles, suggestions, input text
│   │   │   ├── AgentGraphVisualizer.jsx # LangGraph visualizer flowchart
│   │   │   ├── Header.jsx             # Top bar with health-check indicator status
│   │   │   ├── InteractionForm.jsx    # Left panel structured form (AI locked)
│   │   │   └── PastInteractions.jsx   # Database logged interactions & task list
│   │   ├── store/
│   │   │   ├── crmSlice.js            # Redux actions, state reducer, async thunks
│   │   │   └── index.js               # Redux store config
│   │   ├── App.jsx
│   │   ├── index.css                  # Custom styling (Inter typography, scrollbars, glow)
│   │   └── main.jsx
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── package.json
├── implementation_plan.md
├── run.bat                            # Double-click launcher (starts both services)
└── README.md
```

---

## 🛠️ Installation & Running

### Prerequisites
- Python 3.10+
- Node.js 18+

### Step 1: Configure Environment Variables
1. Navigate to the `backend/` folder.
2. Edit the `.env` file:
   ```env
   # Add your Groq key (Get one for free at https://console.groq.com)
   GROQ_API_KEY=your_groq_api_key_here

   # Database URL (Default is SQLite, can be changed to MySQL/Postgres)
   DATABASE_URL=sqlite:///./crm_hcp.db
   ```
   *Note: If no `GROQ_API_KEY` is provided, the backend falls back to an offline rule-based Mock Agent, allowing you to test all five tools.*

### Step 2: Running with Double-Click Launcher (Windows)
Double-click `run.bat` in the project root directory. This batch script will:
1. Boot up the FastAPI server on `http://localhost:8000`.
2. Automatically seed initial doctor profiles (Dr. Sarah Jenkins, Dr. Alan Smith, etc.) and drug products (Prodo-X, CardioShield).
3. Start the Vite React development server on `http://localhost:5173`.
4. Open both logs in separate terminals.

---

## 🕹️ Interactive Demo Guide (5 LangGraph Tools)

You can click any of the **Quick Sandbox Prompts** in the chat panel to instantly trigger the tools:

1. **Tool 1: Log Interaction**
   - Click the **Log Visit** chip or type:  
     *"I visited Dr. Sarah Jenkins today at 2 PM. We discussed Prodo-X trials. She was positive and requested a sample kit. Dr. Alan Smith was also present."*
   - *Result*: Left form is auto-populated. The visualizer highlights `User Request` ➔ `LLM Agent` ➔ `Tools Node` ➔ `Form Render`. Under the response, the executed tool is listed with extracted arguments.
2. **Tool 2: Edit Interaction**
   - Click the **Correct Form** chip or type:  
     *"Actually, change the sentiment to Neutral and set the time to 3 PM."*
   - *Result*: The sentiment radio and time field in the left panel update instantly. Other fields remain intact.
3. **Tool 3: Search HCP Profile**
   - Click the **Find Doctor** chip or type:  
     *"Search doctor profiles for Alan"* or *"Find oncologists"*
   - *Result*: The bot queries the database and prints matched profile records (specialty, hospital, phone) in the chat response.
4. **Tool 4: Retrieve Product Info**
   - Click the **Get Drug Info** chip or type:  
     *"Get product information for CardioShield"*
   - *Result*: Returns drug description and pdf brochure link from the product database.
5. **Tool 5: Schedule Follow-up**
   - Click the **Schedule Task** chip or type:  
     *"Schedule a follow-up visit with Dr. Sarah Jenkins next Tuesday to deliver the sample kit."*
   - *Result*: Saves the follow-up task directly in the SQLite/MySQL database and updates the "Scheduled Follow-Ups" list in the history panel.
