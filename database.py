import os
from datetime import datetime, date, time
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, Time, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Database Connection
# By default, use SQLite local file for easy running. Can be overridden in .env with a PostgreSQL/MySQL connection string.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./crm_hcp.db")

# Use connect_args={"check_same_thread": False} only for SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class HCPProfile(Base):
    __tablename__ = "hcp_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    specialty = Column(String(100), nullable=False)
    hospital = Column(String(150), nullable=False)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20))

    interactions = relationship("Interaction", back_populates="hcp")
    follow_ups = relationship("FollowUp", back_populates="hcp")

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    hcp_id = Column(Integer, ForeignKey("hcp_profiles.id"), nullable=False)
    interaction_type = Column(String(50), nullable=False) # e.g. In-Person, Video Call, Phone Call, Email
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    attendees = Column(Text) # JSON list or Comma-separated list
    topics_discussed = Column(Text)
    sentiment = Column(String(50)) # e.g. Positive, Neutral, Negative
    materials_shared = Column(Text) # JSON list or Comma-separated list
    summary = Column(Text)
    status = Column(String(50), default="Draft") # Draft, Submitted
    created_at = Column(DateTime, default=datetime.utcnow)

    hcp = relationship("HCPProfile", back_populates="interactions")
    follow_ups = relationship("FollowUp", back_populates="interaction")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    brochure_url = Column(String(255))

class FollowUp(Base):
    __tablename__ = "follow_ups"

    id = Column(Integer, primary_key=True, index=True)
    interaction_id = Column(Integer, ForeignKey("interactions.id"), nullable=True)
    hcp_id = Column(Integer, ForeignKey("hcp_profiles.id"), nullable=False)
    date = Column(Date, nullable=False)
    notes = Column(Text)
    status = Column(String(50), default="Pending") # Pending, Completed

    hcp = relationship("HCPProfile", back_populates="follow_ups")
    interaction = relationship("Interaction", back_populates="follow_ups")

# Helper function to initialize database and seed initial mock data
def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed HCP Profiles if table is empty
        if db.query(HCPProfile).count() == 0:
            hcp_data = [
                HCPProfile(name="Dr. Sarah Jenkins", specialty="Oncology", hospital="Metro Health Cancer Center", email="sarah.jenkins@metrohealth.org", phone="+1-555-0199"),
                HCPProfile(name="Dr. Alan Smith", specialty="Cardiology", hospital="St. Jude Heart Institute", email="alan.smith@stjude.org", phone="+1-555-0143"),
                HCPProfile(name="Dr. Priya Patel", specialty="Pediatrics", hospital="Children's General Hospital", email="priya.patel@childrens.org", phone="+1-555-0177"),
                HCPProfile(name="Dr. Michael Chang", specialty="Neurology", hospital="Neuroscience Research Center", email="m.chang@neuroresearch.com", phone="+1-555-0121"),
                HCPProfile(name="Dr. Emily Ross", specialty="Endocrinology", hospital="Endocrine Clinic of Excellence", email="emily.ross@endocrineclinic.com", phone="+1-555-0185")
            ]
            db.add_all(hcp_data)
            db.commit()
            print("Seeded HCP Profiles.")

        # Seed Products if table is empty
        if db.query(Product).count() == 0:
            product_data = [
                Product(name="Prodo-X", description="A next-generation oncology therapeutic targets specific solid tumors with reduced side-effects.", brochure_url="/materials/prodo_x_brochure.pdf"),
                Product(name="CardioShield", description="An advanced ACE-inhibitor formulation for managing chronic hypertension in adult patients.", brochure_url="/materials/cardioshield_info.pdf"),
                Product(name="NeuroRelief", description="Fast-acting migraine relief spray with immediate absorption technology.", brochure_url="/materials/neurorelief_guide.pdf"),
                Product(name="InsuloSmart", description="Smart insulin sensitizing agent with 24-hour slow release profile.", brochure_url="/materials/insulosmart_sheet.pdf")
            ]
            db.add_all(product_data)
            db.commit()
            print("Seeded Products.")
            
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()
