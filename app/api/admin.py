from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json
from datetime import datetime
from app.services.faq_service import FAQService

router = APIRouter()
faq_service = FAQService()

class Company(BaseModel):
    name: str
    contact_email: Optional[str] = None
    language_preference: Optional[str] = "english"

class CompanyResponse(BaseModel):
    id: int
    name: str
    api_key: str
    contact_email: Optional[str]
    language_preference: str
    created_at: datetime
    is_active: bool

class FAQUpload(BaseModel):
    company_id: int
    faq_data: List[dict]

# Simple in-memory storage for companies (we'll use real DB later)
companies_db = {
    1: {
        "id": 1,
        "name": "Demo Company",
        "api_key": "test-key-123",
        "contact_email": "demo@example.com",
        "language_preference": "srpski",
        "created_at": datetime.utcnow(),
        "is_active": True
    }
}

@router.post("/companies", response_model=CompanyResponse)
async def create_company(company: Company):
    """Create a new company with API key"""
    company_id = len(companies_db) + 1
    api_key = f"cs-{uuid.uuid4().hex[:16]}"
    
    new_company = {
        "id": company_id,
        "name": company.name,
        "api_key": api_key,
        "contact_email": company.contact_email,
        "language_preference": company.language_preference,
        "created_at": datetime.utcnow(),
        "is_active": True
    }
    
    companies_db[company_id] = new_company
    
    return CompanyResponse(**new_company)

@router.get("/companies", response_model=List[CompanyResponse])
async def list_companies():
    """List all companies"""
    return [CompanyResponse(**company) for company in companies_db.values()]

@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: int):
    """Get specific company details"""
    if company_id not in companies_db:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return CompanyResponse(**companies_db[company_id])

@router.post("/companies/{company_id}/faq")
async def upload_company_faq(company_id: int, faq_upload: FAQUpload):
    """Upload FAQ data for a company"""
    if company_id not in companies_db:
        raise HTTPException(status_code=404, detail="Company not found")
    
    try:
        count = faq_service.load_faq_data(company_id, faq_data=faq_upload.faq_data)
        return {
            "message": f"Successfully uploaded {count} FAQ entries for company {company_id}",
            "company_id": company_id,
            "faq_count": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FAQ upload error: {str(e)}")

@router.get("/companies/{company_id}/faq/test")
async def test_company_faq(company_id: int, question: str):
    """Test FAQ search for a company"""
    if company_id not in companies_db:
        raise HTTPException(status_code=404, detail="Company not found")
    
    results = faq_service.search_faq(company_id, question, top_k=3)
    return {
        "question": question,
        "company_id": company_id,
        "results": results
    }

@router.delete("/companies/{company_id}")
async def delete_company(company_id: int):
    """Delete a company and its data"""
    if company_id not in companies_db:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Mark as inactive instead of deleting
    companies_db[company_id]["is_active"] = False
    
    return {
        "message": f"Company {company_id} deactivated successfully"
    }