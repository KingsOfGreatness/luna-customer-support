from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging
from datetime import datetime

# Import configuration first
from app.core.config import settings

# Import API routes
from app.api import chat, websocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    version="1.0.0"
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(websocket.router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Customer Support AI API",
        "version": "1.0.0",
        "status": "active",
        "supported_languages": settings.SUPPORTED_LANGUAGES,
        "timestamp": datetime.now(),
        "interfaces": {
            "luna_chat": "Visit /luna for the professional chat widget",
            "admin_panel": "Visit /admin for company management",
            "websocket_test": "Visit /test for WebSocket testing"
        },
        "api_endpoints": {
            "chat": "/api/v1/chat",
            "voice": "/api/v1/text-to-voice",
            "websocket": "/api/v1/ws/{client_id}",
            "health": "/api/v1/health/detailed"
        }
    }

@app.get("/test")
async def websocket_test_page():
    """Serve the WebSocket test page"""
    return FileResponse('websocket_test.html')

@app.get("/luna")
async def luna_chat_widget():
    """Serve the professional Luna chat widget"""
    return FileResponse('luna_chat.html')

@app.get("/admin")
async def admin_panel():
    """Serve the admin panel for company management"""
    return FileResponse('admin_panel.html')

@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now()
    }

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info(f"Starting {settings.PROJECT_NAME}")
    logger.info(f"Supported languages: {settings.SUPPORTED_LANGUAGES}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info(f"Shutting down {settings.PROJECT_NAME}")