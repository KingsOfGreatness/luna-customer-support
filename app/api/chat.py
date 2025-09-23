from fastapi import APIRouter, HTTPException, Header, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import logging
from datetime import datetime
import time

from app.services.llm_service import LLMService
from app.services.faq_service import FAQService
from app.services.rate_limiter import rate_limiter   # ✅ Added import
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
llm_service = LLMService()
faq_service = FAQService()

def get_voice_service():
    """Get voice service instance (lazy loading to avoid import issues)"""
    try:
        from app.services.voice_service import VoiceService
        return VoiceService()
    except Exception as e:
        logger.error(f"Failed to initialize voice service: {e}")
        return None

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    language: Optional[str] = None
    company_id: Optional[int] = 1
    session_id: Optional[str] = None
    context: Optional[dict] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    language: str
    timestamp: datetime
    response_time_ms: int
    suggested_actions: List[str]
    confidence_score: Optional[float] = None
    sources_used: Optional[List[str]] = None

class ErrorResponse(BaseModel):
    error: str
    error_code: str
    timestamp: datetime
    session_id: Optional[str] = None

def verify_api_key(api_key: str = Header(None, alias="api-key")) -> str:
    """Verify API key and check rate limits"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # ✅ Check rate limit first (applies to all keys)
    if not rate_limiter.is_allowed(api_key):
        remaining = rate_limiter.get_remaining(api_key)
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. {remaining} requests remaining in current window."
        )
    
    # ✅ For testing/demo - hardcoded keys
    valid_keys = ["test-key-123", "demo-key-456", "client-test-key"]
    
    if api_key in valid_keys:
        return api_key
    
    # ✅ TODO: In production, check database here
    # if not db.verify_api_key(api_key):
    #     raise HTTPException(status_code=401, detail="Invalid API key")
    
    # ✅ For now during testing, accept any key that starts with "test-"
    if api_key.startswith("test-"):
        return api_key
    
    raise HTTPException(status_code=401, detail="Invalid API key")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key)
):
    """Main chat endpoint with professional error handling"""
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        # Validate and detect language
        detected_language = request.language
        if not detected_language:
            detected_language = llm_service.detect_language(request.message)
            
        if detected_language not in settings.SUPPORTED_LANGUAGES:
            detected_language = "english"
        
        logger.info(f"Processing chat request - Session: {session_id}, Language: {detected_language}")
        
        # Get FAQ context for the company
        context = ""
        sources_used = []
        try:
            faq_results = faq_service.search_faq(request.message, request.company_id, limit=3)
            if faq_results:
                context = "\n".join([f"Q: {faq['question']}\nA: {faq['answer']}" for faq in faq_results])
                sources_used = [faq['question'] for faq in faq_results]
        except Exception as e:
            logger.warning(f"FAQ search failed: {e}")
        
        # Generate AI response
        ai_response, suggested_actions = llm_service.generate_response(
            message=request.message,
            language=detected_language,
            context=context
        )
        
        # Calculate response time
        response_time = int((time.time() - start_time) * 1000)
        
        # Log successful interaction
        logger.info(f"Chat completed - Session: {session_id}, Response time: {response_time}ms")
        
        return ChatResponse(
            response=ai_response,
            session_id=session_id,
            language=detected_language,
            timestamp=datetime.now(),
            response_time_ms=response_time,
            suggested_actions=suggested_actions,
            confidence_score=0.85 if context else 0.7,  # Higher confidence with FAQ context
            sources_used=sources_used if sources_used else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        
        # Return professional error response
        raise HTTPException(
            status_code=500, 
            detail=f"Luna is temporarily unavailable: {str(e)}"
        )

@router.get("/languages")
async def get_supported_languages():
    """Get list of supported languages"""
    return {
        "supported_languages": settings.SUPPORTED_LANGUAGES,
        "total_count": len(settings.SUPPORTED_LANGUAGES),
        "default_language": "english"
    }

@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check for monitoring"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(),
        "services": {}
    }
    
    # Check OpenAI connection
    try:
        # Quick test call
        test_response = llm_service.detect_language("Hello")
        health_status["services"]["openai"] = "healthy"
    except Exception as e:
        health_status["services"]["openai"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check FAQ service
    try:
        faq_count = len(faq_service.search_faq("test", 1, limit=1))
        health_status["services"]["faq_service"] = "healthy"
    except Exception as e:
        health_status["services"]["faq_service"] = f"error: {str(e)}"
    
    return health_status

@router.post("/init-faq/{company_id}")
async def initialize_company_faq(
    company_id: int,
    api_key: str = Depends(verify_api_key)
):
    """Initialize FAQ data for a company (enhanced for multiple languages)"""
    try:
        # Enhanced multilingual FAQ data
        default_faqs = [
            {
                "question": "How do I reset my password?",
                "answer": "You can reset your password by clicking 'Forgot Password' on the login page and following the instructions sent to your email.",
                "language": "english",
                "category": "account"
            },
            {
                "question": "Kako mogu resetirati lozinku?",
                "answer": "Možete resetirati lozinku klikom na 'Zaboravljena lozinka' na stranici za prijavu i praćenjem instrukcija poslanih na vaš email.",
                "language": "srpski",
                "category": "account"
            },
            {
                "question": "Wie kann ich mein Passwort zurücksetzen?",
                "answer": "Sie können Ihr Passwort zurücksetzen, indem Sie auf 'Passwort vergessen' auf der Anmeldeseite klicken und den Anweisungen in der E-Mail folgen.",
                "language": "deutsch",
                "category": "account"
            },
            {
                "question": "Come posso reimpostare la mia password?",
                "answer": "Puoi reimpostare la password cliccando su 'Password dimenticata' nella pagina di accesso e seguendo le istruzioni inviate alla tua email.",
                "language": "italiano",
                "category": "account"
            },
            {
                "question": "Comment puis-je réinitialiser mon mot de passe?",
                "answer": "Vous pouvez réinitialiser votre mot de passe en cliquant sur 'Mot de passe oublié' sur la page de connexion et en suivant les instructions envoyées à votre email.",
                "language": "français",
                "category": "account"
            }
        ]
        
        # Add FAQs to the service
        added_count = 0
        for faq in default_faqs:
            try:
                faq_service.add_faq(
                    company_id=company_id,
                    question=faq["question"],
                    answer=faq["answer"],
                    language=faq["language"],
                    category=faq.get("category", "general")
                )
                added_count += 1
            except Exception as e:
                logger.warning(f"Failed to add FAQ: {e}")
        
        return {
            "message": f"Loaded {added_count} FAQ entries for company {company_id}",
            "company_id": company_id,
            "faq_count": added_count,
            "languages_supported": list(set([faq["language"] for faq in default_faqs]))
        }
        
    except Exception as e:
        logger.error(f"FAQ initialization failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize FAQ data")

# =============================================================================
# VOICE ENDPOINTS - NO DUPLICATES
# =============================================================================

@router.get("/voice/debug")
async def voice_debug(api_key: str = Depends(verify_api_key)):
    """Debug voice service setup"""
    try:
        voice_service = get_voice_service()
        if voice_service is None:
            return {"error": "Voice service failed to initialize"}
        
        # Check if ElevenLabs is available
        debug_info = {
            "voice_service_initialized": True,
            "elevenlabs_available": voice_service.voice_available,
            "elevenlabs_client": voice_service.elevenlabs_client is not None,
            "api_key_set": settings.ELEVENLABS_API_KEY != "",
            "api_key_length": len(settings.ELEVENLABS_API_KEY) if settings.ELEVENLABS_API_KEY else 0
        }
        
        return debug_info
        
    except Exception as e:
        return {"error": str(e)}

@router.post("/text-to-voice")
async def text_to_voice(
    request: dict,
    api_key: str = Depends(verify_api_key)
):
    """Convert text to voice using ElevenLabs v2.9.2+ - SINGLE DEFINITION"""
    text = request.get("text", "")
    language = request.get("language", "english")
    
    if not text or len(text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if len(text) > 1000:
        raise HTTPException(status_code=400, detail="Text too long (max 1000 characters)")
    
    try:
        voice_service = get_voice_service()
        if voice_service is None:
            raise HTTPException(status_code=503, detail="Voice service unavailable")
            
        # Generate speech
        logger.info(f"Generating speech for: '{text[:30]}...'")
        audio_bytes = voice_service.text_to_speech(text, language)
        
        # Return audio file
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=luna_response.mp3"}
        )
        
    except Exception as e:
        logger.error(f"Text-to-voice failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/voice/health")
async def voice_health_check(api_key: str = Depends(verify_api_key)):
    """Check voice service health"""
    voice_service = get_voice_service()
    if voice_service is None:
        return {
            "speech_to_text": "unavailable",
            "text_to_speech": "unavailable",
            "errors": ["Voice service initialization failed"]
        }
    return voice_service.health_check()

@router.get("/voice/available-voices")
async def get_available_voices(api_key: str = Depends(verify_api_key)):
    """Get available voices for text-to-speech"""
    voice_service = get_voice_service()
    if voice_service is None:
        return {"voices": [], "error": "Voice service unavailable"}
    return voice_service.get_available_voices()

# Voice-to-text endpoint
@router.post("/voice-to-text")
async def voice_to_text(
    audio_file: UploadFile = File(...),
    language: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Convert voice to text using OpenAI Whisper"""
    start_time = time.time()
    
    if not audio_file.content_type.startswith('audio/'):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    
    try:
        # Read audio file
        audio_bytes = await audio_file.read()
        voice_service = get_voice_service()
        
        if voice_service is None:
            raise HTTPException(status_code=503, detail="Voice service unavailable")
        
        # Convert speech to text
        transcribed_text, detected_language = await voice_service.speech_to_text(
            audio_bytes, language
        )
        
        response_time = int((time.time() - start_time) * 1000)
        
        return {
            "transcribed_text": transcribed_text,
            "detected_language": detected_language,
            "response_time_ms": response_time,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Voice-to-text failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
