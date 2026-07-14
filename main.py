import os
from datetime import datetime, date, time
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Load env variables
load_dotenv()

from .database import init_db, SessionLocal, HCPProfile, Product, FollowUp, Interaction
from .schemas import (
    ChatRequest, ChatResponse, 
    HCPResponse, ProductResponse, 
    FollowUpResponse, InteractionResponse, InteractionCreate
)
from .agent import run_interaction_agent

# Initialize database tables and seed data
init_db()

app = FastAPI(title="AI-First CRM HCP Module Backend", version="1.0.0")

# Enable CORS for the React frontend (running on http://localhost:5173 or http://localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development ease
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "AI-First CRM HCP Module API is running."}

@app.post("/api/chat", response_model=ChatResponse)
def handle_chat(payload: ChatRequest):
    """
    Endpoint that feeds user chat messages, history, and active form state
    to the LangGraph agent. Returns the reply, updated form state, and step logs.
    """
    try:
        # Pydantic dict serialization
        current_state_dict = payload.current_state.model_dump()
        history_list = [h for h in payload.history]
        
        # Run agent
        result = run_interaction_agent(
            message=payload.message,
            current_state=current_state_dict,
            history=history_list
        )
        
        return ChatResponse(
            reply=result["reply"],
            updated_state=result["updated_state"],
            steps=result["steps"],
            tools_called=result["tools_called"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")

@app.get("/api/hcps", response_model=List[HCPResponse])
def get_all_hcps(db: Session = Depends(get_db)):
    """
    Get all HCP profiles.
    """
    return db.query(HCPProfile).all()

@app.get("/api/products", response_model=List[ProductResponse])
def get_all_products(db: Session = Depends(get_db)):
    """
    Get all products.
    """
    return db.query(Product).all()

@app.get("/api/followups", response_model=List[FollowUpResponse])
def get_all_followups(db: Session = Depends(get_db)):
    """
    Get all follow-ups.
    """
    return db.query(FollowUp).all()

@app.get("/api/interactions", response_model=List[InteractionResponse])
def get_all_interactions(db: Session = Depends(get_db)):
    """
    Get all logged interactions.
    """
    interactions = db.query(Interaction).order_by(Interaction.created_at.desc()).all()
    
    # Map attendees and materials_shared back from comma-separated/JSON string to list
    res = []
    for inter in interactions:
        att = inter.attendees.split(",") if inter.attendees else []
        mat = inter.materials_shared.split(",") if inter.materials_shared else []
        res.append(
            InteractionResponse(
                id=inter.id,
                hcp_id=inter.hcp_id,
                interaction_type=inter.interaction_type,
                date=inter.date,
                time=inter.time,
                attendees=[a.strip() for a in att if a.strip()],
                topics_discussed=inter.topics_discussed,
                sentiment=inter.sentiment,
                materials_shared=[m.strip() for m in mat if m.strip()],
                summary=inter.summary,
                status=inter.status,
                created_at=inter.created_at
            )
        )
    return res

@app.post("/api/interactions", response_model=InteractionResponse)
def create_interaction(payload: InteractionCreate, db: Session = Depends(get_db)):
    """
    Persist logged interaction details in the DB.
    """
    # Verify HCP exists
    hcp = db.query(HCPProfile).filter(HCPProfile.id == payload.hcp_id).first()
    if not hcp:
        raise HTTPException(status_code=404, detail="HCP profile not found")
        
    try:
        att_str = ",".join(payload.attendees) if payload.attendees else ""
        mat_str = ",".join(payload.materials_shared) if payload.materials_shared else ""
        
        new_inter = Interaction(
            hcp_id=payload.hcp_id,
            interaction_type=payload.interaction_type,
            date=payload.date,
            time=payload.time,
            attendees=att_str,
            topics_discussed=payload.topics_discussed,
            sentiment=payload.sentiment,
            materials_shared=mat_str,
            summary=payload.summary,
            status="Submitted"
        )
        db.add(new_inter)
        db.commit()
        db.refresh(new_inter)
        
        # Link any pending follow ups for this HCP to this interaction
        pending_followups = db.query(FollowUp).filter(
            FollowUp.hcp_id == hcp.id,
            FollowUp.interaction_id == None,
            FollowUp.status == "Pending"
        ).all()
        for f in pending_followups:
            f.interaction_id = new_inter.id
        db.commit()
        
        return InteractionResponse(
            id=new_inter.id,
            hcp_id=new_inter.hcp_id,
            interaction_type=new_inter.interaction_type,
            date=new_inter.date,
            time=new_inter.time,
            attendees=payload.attendees,
            topics_discussed=new_inter.topics_discussed,
            sentiment=new_inter.sentiment,
            materials_shared=payload.materials_shared,
            summary=new_inter.summary,
            status=new_inter.status,
            created_at=new_inter.created_at
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database insertion failed: {str(e)}")
