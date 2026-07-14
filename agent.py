import os
import json
from datetime import datetime, date
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from groq import Groq
from sqlalchemy.orm import Session
from .database import SessionLocal, HCPProfile, Product, FollowUp, Interaction

# Define the State for LangGraph
class AgentState(TypedDict):
    messages: List[Dict[str, str]] # History of chat messages
    current_state: Dict[str, Any]  # The current form fields
    steps: List[str]               # Node names visited during execution
    tools_called: List[Dict[str, Any]] # Tool calls executed in this turn
    reply: str                     # The assistant's conversational response
    hcp_search_results: Optional[List[Dict[str, Any]]]
    product_results: Optional[List[Dict[str, Any]]]
    followup_status: Optional[str]

# Tool Definitions (JSON schemas for Groq tool calling)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "log_interaction",
            "description": "Log details of a new interaction with a Healthcare Professional (HCP). Extracts properties like HCP name, type, date, time, attendees, topics discussed, sentiment, materials shared, and a summary. Call this tool when the user is reporting a meeting, visit, call, or interaction that they had.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hcp_name": {"type": "string", "description": "The name of the doctor/HCP (e.g. Dr. Sarah Jenkins)"},
                    "interaction_type": {
                        "type": "string", 
                        "enum": ["In-Person", "Video Call", "Phone Call", "Email"], 
                        "description": "The channel of communication"
                    },
                    "date": {"type": "string", "description": "The date of interaction in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "The time of interaction in HH:MM format"},
                    "attendees": {
                        "type": "array", 
                        "items": {"type": "string"}, 
                        "description": "List of other attendees present"
                    },
                    "topics_discussed": {"type": "string", "description": "A description of the main topics and clinical points discussed"},
                    "sentiment": {
                        "type": "string", 
                        "enum": ["Positive", "Neutral", "Negative"],
                        "description": "The attitude/sentiment of the HCP during the interaction"
                    },
                    "materials_shared": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "List of brochures, brochures, sample kits, clinical papers, or prescribing info shared"
                    },
                    "summary": {"type": "string", "description": "A brief one-sentence scientific summary of the interaction"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_interaction",
            "description": "Modify specific fields in the current interaction form based on user updates. Call this tool when the user asks to modify, correct, update, or change something in their active form (e.g., 'Change the sentiment to Neutral', 'The time was actually 3 PM', 'Add Dr. Smith to attendees').",
            "parameters": {
                "type": "object",
                "properties": {
                    "hcp_name": {"type": "string", "description": "New HCP name"},
                    "interaction_type": {"type": "string", "enum": ["In-Person", "Video Call", "Phone Call", "Email"]},
                    "date": {"type": "string", "description": "New date in YYYY-MM-DD"},
                    "time": {"type": "string", "description": "New time in HH:MM"},
                    "attendees": {"type": "array", "items": {"type": "string"}, "description": "New complete list of attendees"},
                    "topics_discussed": {"type": "string", "description": "New topics discussed content"},
                    "sentiment": {"type": "string", "enum": ["Positive", "Neutral", "Negative"]},
                    "materials_shared": {"type": "array", "items": {"type": "string"}, "description": "New complete list of materials shared"},
                    "summary": {"type": "string", "description": "New summary"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_hcp",
            "description": "Search the HCP profiles database by name or medical specialty to check credentials, hospital, phone number, and history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query (e.g. 'Sarah', 'Oncology', 'Cardiologist')"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_info",
            "description": "Retrieve information and brochure URLs for medical products, drugs, and therapeutics (e.g., 'Prodo-X', 'CardioShield').",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string", "description": "The name of the product/drug"}
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_followup",
            "description": "Schedule a follow-up appointment or task for a healthcare professional (HCP) in the CRM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hcp_name": {"type": "string", "description": "Name of the HCP"},
                    "date": {"type": "string", "description": "Date of the follow-up in YYYY-MM-DD"},
                    "notes": {"type": "string", "description": "Follow-up task details or objectives (e.g. 'Deliver Prodo-X sample kit')"}
                },
                "required": ["hcp_name", "date"]
            }
        }
    }
]

# Initialize Groq client
groq_api_key = os.getenv("GROQ_API_KEY", "")
client = None
if groq_api_key:
    client = Groq(api_key=groq_api_key)
    print("Groq Client initialized successfully.")
else:
    print("WARNING: GROQ_API_KEY not found. Running in MOCK AI AGENT mode.")

# --- MOCK AI AGENT LOGIC (Fallback) ---
def mock_agent_call(message: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    A rule-based mock LLM agent that processes the message and generates tool calls
    if GROQ_API_KEY is not set. This guarantees the application works out of the box.
    """
    message_lower = message.lower()
    
    # 1. Check if user is asking to schedule a follow up
    if "schedule" in message_lower or "follow-up" in message_lower or "followup" in message_lower:
        hcp = "Dr. Sarah Jenkins"
        for doc in ["sarah", "jenkins", "smith", "patel", "alan", "priya"]:
            if doc in message_lower:
                if doc in ["sarah", "jenkins"]: hcp = "Dr. Sarah Jenkins"
                elif doc in ["smith", "alan"]: hcp = "Dr. Alan Smith"
                elif doc in ["patel", "priya"]: hcp = "Dr. Priya Patel"
        
        # Simple date extraction
        date_str = str(date.today())
        if "next tuesday" in message_lower:
            date_str = "2026-07-14" # hardcoded future date for demo
        elif "next week" in message_lower:
            date_str = "2026-07-16"
        elif "tomorrow" in message_lower:
            date_str = "2026-07-10"

        return {
            "tool": "schedule_followup",
            "args": {
                "hcp_name": hcp,
                "date": date_str,
                "notes": f"Follow up regarding {current_state.get('topics_discussed') or 'previous discussion'}."
            },
            "reply": f"Understood. I will schedule a follow-up with {hcp} on {date_str}."
        }

    # 2. Check if user is searching for product info
    if "product" in message_lower or "brochure" in message_lower or "prodo" in message_lower or "cardio" in message_lower:
        prod = "Prodo-X"
        if "cardio" in message_lower: prod = "CardioShield"
        elif "neuro" in message_lower: prod = "NeuroRelief"
        elif "insulo" in message_lower: prod = "InsuloSmart"

        return {
            "tool": "get_product_info",
            "args": {"product_name": prod},
            "reply": f"Let me fetch the product materials for {prod}."
        }

    # 3. Check if user is searching for HCP
    if "search" in message_lower or "find doctor" in message_lower or "who is" in message_lower or "specialty" in message_lower:
        query = "Oncology"
        for spec in ["cardio", "pediatr", "neuro", "endo"]:
            if spec in message_lower:
                if spec == "cardio": query = "Cardiology"
                elif spec == "pediatr": query = "Pediatrics"
                elif spec == "neuro": query = "Neurology"
                elif spec == "endo": query = "Endocrinology"
        for name in ["sarah", "jenkins", "alan", "smith", "priya", "patel", "michael", "chang", "emily", "ross"]:
            if name in message_lower:
                query = name.capitalize()

        return {
            "tool": "search_hcp",
            "args": {"query": query},
            "reply": f"Searching our directory for '{query}'..."
        }

    # 4. Check if user is editing/updating fields
    is_edit = any(word in message_lower for word in ["change", "edit", "correct", "update", "set", "actually", "sorry"])
    if is_edit:
        args = {}
        # Parse fields to edit
        if "sentiment" in message_lower:
            if "positive" in message_lower: args["sentiment"] = "Positive"
            elif "negative" in message_lower: args["sentiment"] = "Negative"
            elif "neutral" in message_lower: args["sentiment"] = "Neutral"
        if "time" in message_lower:
            # Look for patterns like "3 PM" or "15:00"
            if "3 pm" in message_lower or "3pm" in message_lower: args["time"] = "15:00"
            elif "2 pm" in message_lower or "2pm" in message_lower: args["time"] = "14:00"
            elif "10 am" in message_lower or "10am" in message_lower: args["time"] = "10:00"
        if "hcp" in message_lower or "doctor" in message_lower or "name" in message_lower:
            if "jenkins" in message_lower or "sarah" in message_lower: args["hcp_name"] = "Dr. Sarah Jenkins"
            elif "smith" in message_lower or "alan" in message_lower: args["hcp_name"] = "Dr. Alan Smith"
            elif "patel" in message_lower or "priya" in message_lower: args["hcp_name"] = "Dr. Priya Patel"
        if "type" in message_lower or "meeting" in message_lower or "call" in message_lower:
            if "person" in message_lower: args["interaction_type"] = "In-Person"
            elif "video" in message_lower: args["interaction_type"] = "Video Call"
            elif "phone" in message_lower: args["interaction_type"] = "Phone Call"
            elif "email" in message_lower: args["interaction_type"] = "Email"

        if args:
            return {
                "tool": "edit_interaction",
                "args": args,
                "reply": f"I have updated the active form fields: {', '.join(args.keys())}."
            }

    # 5. Default: Log a new interaction from scratch
    # Parse basic entities
    hcp = "Dr. Sarah Jenkins"
    if "smith" in message_lower or "alan" in message_lower: hcp = "Dr. Alan Smith"
    elif "patel" in message_lower or "priya" in message_lower: hcp = "Dr. Priya Patel"
    elif "chang" in message_lower or "michael" in message_lower: hcp = "Dr. Michael Chang"
    elif "ross" in message_lower or "emily" in message_lower: hcp = "Dr. Emily Ross"

    int_type = "In-Person"
    if "video" in message_lower or "zoom" in message_lower or "teams" in message_lower: int_type = "Video Call"
    elif "phone" in message_lower or "call" in message_lower: int_type = "Phone Call"
    elif "email" in message_lower: int_type = "Email"

    sentiment = "Positive"
    if "negative" in message_lower or "unhappy" in message_lower or "refused" in message_lower: sentiment = "Negative"
    elif "neutral" in message_lower or "indifferent" in message_lower: sentiment = "Neutral"

    date_str = str(date.today())
    time_str = "14:00"

    # Extract attendees
    attendees = []
    if "dr. smith" in message_lower or "alan smith" in message_lower:
        if hcp != "Dr. Alan Smith": attendees.append("Dr. Alan Smith")
    if "dr. jenkins" in message_lower or "sarah jenkins" in message_lower:
        if hcp != "Dr. Sarah Jenkins": attendees.append("Dr. Sarah Jenkins")

    # Materials shared
    materials = []
    if "brochure" in message_lower: materials.append("Product Brochure")
    if "sample" in message_lower: materials.append("Sample Kit")
    if "clinical" in message_lower or "study" in message_lower: materials.append("Clinical Study PDF")
    if "prescribing" in message_lower: materials.append("Prescribing Information")

    topics = "Discussed clinical efficacy, safety profile, and patient access."
    if "efficacy" in message_lower or "trials" in message_lower:
        topics = "Detailed review of Phase III clinical trial efficacy data."
    
    summary = f"Logged productive {int_type} interaction with {hcp} showing {sentiment} response."

    return {
        "tool": "log_interaction",
        "args": {
            "hcp_name": hcp,
            "interaction_type": int_type,
            "date": date_str,
            "time": time_str,
            "attendees": attendees,
            "topics_discussed": topics,
            "sentiment": sentiment,
            "materials_shared": materials,
            "summary": summary
        },
        "reply": f"I've initialized the interaction form for {hcp} based on your description. Please review and verify the details."
    }

# --- LANGGRAPH NODE FUNCTIONS ---

def agent_node(state: AgentState) -> AgentState:
    """
    LLM Agent Node: Decides whether to invoke a tool or respond conversationally.
    """
    state["steps"].append("Agent Decider")
    
    latest_message = state["messages"][-1]["content"] if state["messages"] else ""
    
    # Fallback to mock agent if Groq is not available
    if not client:
        result = mock_agent_call(latest_message, state["current_state"])
        state["reply"] = result["reply"]
        state["tools_called"].append({
            "name": result["tool"],
            "args": result["args"],
            "mock": True
        })
        return state
        
    try:
        # Construct messages context
        messages_for_llm = [
            {
                "role": "system",
                "content": f"""You are a life-science CRM AI sales assistant helping field reps log and manage interactions with Healthcare Professionals (HCPs).
You are managing the "Log Interaction" screen. You have access to a set of tools to query and modify the current screen state or the CRM database.

CRITICAL RULES:
1. Always use 'log_interaction' when the user describes a new interaction or meeting details.
2. Always use 'edit_interaction' when the user requests updates to the ACTIVE FORM state (currently: {json.dumps(state['current_state'])}).
3. Do not assume values; extract them precisely.
4. If the user mentions a drug (like Prodo-X or CardioShield), look up information using 'get_product_info'.
5. If the user wants to check details of an HCP, use 'search_hcp'.
6. If the user wants to schedule a follow-up visit, use 'schedule_followup'.
7. If no tool is required, reply politely and concisely, helping the representative.
"""
            }
        ]
        
        # Append history
        for msg in state["messages"]:
            messages_for_llm.append({"role": msg["role"], "content": msg["content"]})
            
        # LLM Call with Tool schema
        response = client.chat.completions.create(
            model="gemma2-9b-it", # standard fallback
            messages=messages_for_llm,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            temperature=0.1
        )
        
        response_message = response.choices[0].message
        
        if response_message.tool_calls:
            # We have tool calls
            for tool_call in response_message.tool_calls:
                state["tools_called"].append({
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "args": json.loads(tool_call.function.arguments)
                })
            state["reply"] = response_message.content or "Let me process that request using our tools..."
        else:
            state["reply"] = response_message.content or "How can I help you log this interaction?"
            
    except Exception as e:
        print(f"Error calling Groq: {e}. Falling back to Mock agent.")
        result = mock_agent_call(latest_message, state["current_state"])
        state["reply"] = f" [Mock Fallback] {result['reply']}"
        state["tools_called"].append({
            "name": result["tool"],
            "args": result["args"],
            "mock": True
        })
        
    return state


def tools_node(state: AgentState) -> AgentState:
    """
    Tools Execution Node: Executes database actions or form state mutations.
    """
    state["steps"].append("Tools Executor")
    
    db: Session = SessionLocal()
    try:
        # Loop through tools called by the agent
        for tc in state["tools_called"]:
            # If already processed in this turn or skipped
            if "status" in tc:
                continue
                
            tool_name = tc["name"]
            args = tc["args"]
            
            print(f"Executing Tool: {tool_name} with args: {args}")
            
            if tool_name == "log_interaction":
                # Create/populate the interaction form state
                updated = {**state["current_state"]}
                for key in ["hcp_name", "interaction_type", "date", "time", "attendees", "topics_discussed", "sentiment", "materials_shared", "summary"]:
                    if key in args:
                        updated[key] = args[key]
                
                # Default empty list fields if not present
                if "attendees" not in updated or updated["attendees"] is None:
                    updated["attendees"] = []
                if "materials_shared" not in updated or updated["materials_shared"] is None:
                    updated["materials_shared"] = []
                    
                state["current_state"] = updated
                tc["status"] = "success"
                tc["result"] = "Form state initialized/logged successfully."
                
            elif tool_name == "edit_interaction":
                # Edit active state
                updated = {**state["current_state"]}
                for key, val in args.items():
                    if key in updated:
                        updated[key] = val
                state["current_state"] = updated
                tc["status"] = "success"
                tc["result"] = f"Fields updated: {list(args.keys())}"
                
            elif tool_name == "search_hcp":
                query = args.get("query", "")
                hcps = db.query(HCPProfile).filter(
                    (HCPProfile.name.ilike(f"%{query}%")) | 
                    (HCPProfile.specialty.ilike(f"%{query}%")) | 
                    (HCPProfile.hospital.ilike(f"%{query}%"))
                ).all()
                
                results = [
                    {
                        "id": h.id,
                        "name": h.name,
                        "specialty": h.specialty,
                        "hospital": h.hospital,
                        "email": h.email,
                        "phone": h.phone
                    } for h in hcps
                ]
                
                state["hcp_search_results"] = results
                tc["status"] = "success"
                tc["result"] = f"Found {len(results)} matching HCPs."
                
            elif tool_name == "get_product_info":
                name = args.get("product_name", "")
                prods = db.query(Product).filter(Product.name.ilike(f"%{name}%")).all()
                results = [
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "brochure_url": p.brochure_url
                    } for p in prods
                ]
                state["product_results"] = results
                tc["status"] = "success"
                tc["result"] = f"Found product details for: {', '.join([p['name'] for p in results])}"
                
            elif tool_name == "schedule_followup":
                hcp_name = args.get("hcp_name", "")
                date_val = args.get("date", "")
                notes = args.get("notes", "")
                
                # Check if HCP exists
                hcp = db.query(HCPProfile).filter(HCPProfile.name.ilike(f"%{hcp_name}%")).first()
                if hcp:
                    try:
                        parsed_date = datetime.strptime(date_val, "%Y-%m-%d").date()
                        new_followup = FollowUp(
                            hcp_id=hcp.id,
                            date=parsed_date,
                            notes=notes,
                            status="Pending"
                        )
                        db.add(new_followup)
                        db.commit()
                        state["followup_status"] = f"Follow-up scheduled with {hcp.name} on {date_val} successfully."
                        tc["status"] = "success"
                        tc["result"] = f"Follow-up registered in DB (ID: {new_followup.id})"
                    except Exception as date_err:
                        db.rollback()
                        state["followup_status"] = f"Failed to schedule follow-up: Invalid date format. Please use YYYY-MM-DD."
                        tc["status"] = "failed"
                        tc["result"] = str(date_err)
                else:
                    state["followup_status"] = f"Failed to schedule follow-up: HCP '{hcp_name}' not found."
                    tc["status"] = "failed"
                    tc["result"] = "HCP not found"
                    
    except Exception as e:
        print(f"Error executing tools node: {e}")
        db.rollback()
    finally:
        db.close()
        
    return state


def route_next(state: AgentState) -> str:
    """
    Router function to guide flow based on tool executions.
    """
    # If the agent scheduled tool calls and they are not executed yet, go to tools
    unexecuted_calls = [tc for tc in state["tools_called"] if "status" not in tc]
    if unexecuted_calls:
        return "tools"
    return END

# --- DEFINE THE LANGGRAPH STATEGRAPH ---

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tools_node)

# Set Entry Point
workflow.set_entry_point("agent")

# Add Conditional Edges
workflow.add_conditional_edges(
    "agent",
    route_next,
    {
        "tools": "tools",
        END: END
    }
)

# Add Normal Edges
workflow.add_edge("tools", "agent")

# Compile Graph
graph = workflow.compile()

# Helper execution function
def run_interaction_agent(message: str, current_state: Dict[str, Any], history: List[Dict[str, str]]) -> Dict[str, Any]:
    # Set up initial state
    initial_state: AgentState = {
        "messages": history + [{"role": "user", "content": message}],
        "current_state": current_state,
        "steps": [],
        "tools_called": [],
        "reply": "",
        "hcp_search_results": None,
        "product_results": None,
        "followup_status": None
    }
    
    # Run through LangGraph
    final_output = graph.invoke(initial_state)
    
    # Clean up results to send back
    reply = final_output.get("reply", "")
    
    # If there were search results or followups, append helpful context to the reply
    if final_output.get("hcp_search_results"):
        hcp_list = final_output["hcp_search_results"]
        if hcp_list:
            reply += "\n\n**HCP search results:**\n" + "\n".join([f"- **{h['name']}** ({h['specialty']}) at *{h['hospital']}* - Email: {h['email']}, Phone: {h['phone']}" for h in hcp_list])
        else:
            reply += "\n\nNo matching HCPs found."
            
    if final_output.get("product_results"):
        prod_list = final_output["product_results"]
        if prod_list:
            reply += "\n\n**Product Information:**\n" + "\n".join([f"- **{p['name']}**: {p['description']} (Brochure URL: {p['brochure_url']})" for p in prod_list])
        else:
            reply += "\n\nNo matching products found."
            
    if final_output.get("followup_status"):
        reply += f"\n\n**Follow-up Status:** {final_output['followup_status']}"
        
    return {
        "reply": reply,
        "updated_state": final_output["current_state"],
        "steps": final_output["steps"],
        "tools_called": final_output["tools_called"]
    }
