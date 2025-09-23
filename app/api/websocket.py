from fastapi import APIRouter, HTTPException, Header, Depends, File, UploadFile
from fastapi.responses import Response
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
import logging
from datetime import datetime
import time
import json

from app.services.llm_service import LLMService
from app.services.faq_service import FAQService
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

def verify_api_key(api_key: str = Header(..., alias="api-key")):
    """Simple API key verification - will enhance with JWT later"""
    valid_keys = ["test-key-123", "dev-key-456"]
    if api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

# Voice Models
class VoiceToTextRequest(BaseModel):
    language: Optional[str] = None
    company_id: Optional[int] = 1

class VoiceResponse(BaseModel):
    transcribed_text: str
    detected_language: str
    ai_response: str
    response_time_ms: int
    session_id: str
    suggested_actions: List[str]

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected via WebSocket")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        logger.info(f"Client {client_id} disconnected from WebSocket")

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                self.disconnect(client_id)

    async def process_message(self, data: dict, client_id: str):
        """Process incoming message and generate response"""
        try:
            message_type = data.get("type", "text")
            session_id = data.get("session_id", str(uuid.uuid4()))
            company_id = data.get("company_id", 1)
            language = data.get("language")
            
            # Send typing indicator
            await self.send_typing_indicator(client_id, True)
            
            if message_type == "text":
                start_time = time.time()
                
                # Handle text message
                user_message = data.get("message", "")
                if not user_message:
                    await self.send_error(client_id, "Message cannot be empty")
                    return
                
                # Detect language if not provided
                if not language:
                    language = llm_service.detect_language(user_message)
                
                # Get FAQ context
                context = ""
                sources_used = []
                try:
                    faq_results = faq_service.search_faq(user_message, company_id, limit=3)
                    if faq_results:
                        context = "\n".join([f"Q: {faq['question']}\nA: {faq['answer']}" for faq in faq_results])
                        sources_used = [faq['question'] for faq in faq_results]
                except Exception as e:
                    logger.warning(f"FAQ search failed: {e}")
                
                # Generate AI response
                ai_response, suggested_actions = llm_service.generate_response(
                    message=user_message,
                    language=language,
                    context=context
                )
                
                response_time = int((time.time() - start_time) * 1000)
                
                # Stop typing indicator
                await self.send_typing_indicator(client_id, False)
                
                # Send response
                response_data = {
                    "type": "message_response",
                    "response": ai_response,
                    "session_id": session_id,
                    "language": language,
                    "timestamp": datetime.now().isoformat(),
                    "response_time_ms": response_time,
                    "suggested_actions": suggested_actions,
                    "sources_used": sources_used if sources_used else None,
                    "confidence_score": 0.85 if context else 0.7
                }
                
                await self.send_personal_message(response_data, client_id)
                
            elif message_type == "voice":
                # Handle voice message processing
                await self.send_personal_message({
                    "type": "info",
                    "message": "Voice processing via WebSocket is being implemented..."
                }, client_id)
                
            elif message_type == "ping":
                # Handle ping for connection testing
                await self.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, client_id)
                
            else:
                await self.send_error(client_id, f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error processing message for client {client_id}: {e}")
            await self.send_typing_indicator(client_id, False)
            await self.send_error(client_id, "Failed to process your message")

    async def send_typing_indicator(self, client_id: str, is_typing: bool):
        """Send typing indicator to client"""
        typing_data = {
            "type": "typing",
            "is_typing": is_typing,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal_message(typing_data, client_id)

    async def send_error(self, client_id: str, error_message: str):
        """Send error message to client"""
        error_data = {
            "type": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal_message(error_data, client_id)

    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected clients"""
        for client_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, client_id)

manager = ConnectionManager()

# WebSocket Endpoints
@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time chat"""
    await manager.connect(websocket, client_id)
    
    # Send welcome message
    welcome_message = {
        "type": "connection",
        "message": "Connected to Luna - Customer Support AI",
        "client_id": client_id,
        "timestamp": datetime.now().isoformat(),
        "luna_status": "online"
    }
    await manager.send_personal_message(welcome_message, client_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                # Parse JSON message
                message_data = json.loads(data)
                logger.info(f"Received message from {client_id}: {message_data.get('type', 'unknown')}")
                
                # Process the message
                await manager.process_message(message_data, client_id)
                
            except json.JSONDecodeError:
                await manager.send_error(client_id, "Invalid JSON format")
            except Exception as e:
                logger.error(f"Error handling message from {client_id}: {e}")
                await manager.send_error(client_id, "Failed to process message")
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)

@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket connection status"""
    return {
        "active_connections": len(manager.active_connections),
        "connected_clients": list(manager.active_connections.keys()),
        "timestamp": datetime.now().isoformat(),
        "luna_status": "online"
    }

@router.post("/ws/broadcast")
async def broadcast_message(message: dict):
    """Broadcast message to all connected clients (admin function)"""
    try:
        broadcast_data = {
            "type": "broadcast",
            "message": message.get("message", ""),
            "timestamp": datetime.now().isoformat(),
            "from": "system"
        }
        await manager.broadcast_to_all(broadcast_data)
        return {"status": "broadcasted", "clients": len(manager.active_connections)}
    except Exception as e:
        logger.error(f"Broadcast failed: {e}")
        return {"status": "failed", "error": str(e)}

@router.get("/ws/clients")
async def get_connected_clients():
    """Get list of connected clients"""
    return {
        "clients": list(manager.active_connections.keys()),
        "count": len(manager.active_connections),
        "timestamp": datetime.now().isoformat()
    }

# Voice Endpoints (Fixed)
@router.post("/voice-to-text", response_model=dict)
async def voice_to_text(
    audio_file: UploadFile = File(...),
    language: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Convert voice to text"""
    start_time = time.time()
    
    if not audio_file.content_type.startswith('audio/'):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    
    try:
        voice_service = get_voice_service()
        if voice_service is None:
            raise HTTPException(status_code=503, detail="Voice service unavailable")
        
        # Read audio file
        audio_bytes = await audio_file.read()
        
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

@router.post("/text-to-voice")
async def text_to_voice(
    request: dict,
    api_key: str = Depends(verify_api_key)
):
    """Convert text to voice"""
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
        audio_bytes = voice_service.text_to_speech(text, language)
        
        # Return audio file
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=response.mp3"}
        )
        
    except Exception as e:
        logger.error(f"Text-to-voice failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/voice-to-voice", response_model=VoiceResponse)
async def voice_to_voice(
    audio_file: UploadFile = File(...),
    language: Optional[str] = None,
    company_id: int = 1,
    api_key: str = Depends(verify_api_key)
):
    """Full voice-to-voice conversation"""
    start_time = time.time()
    session_id = str(uuid.uuid4())
    
    if not audio_file.content_type.startswith('audio/'):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    
    try:
        voice_service = get_voice_service()
        if voice_service is None:
            raise HTTPException(status_code=503, detail="Voice service unavailable")
        
        # Step 1: Convert speech to text
        audio_bytes = await audio_file.read()
        transcribed_text, detected_language = await voice_service.speech_to_text(
            audio_bytes, language
        )
        
        logger.info(f"Voice transcribed: '{transcribed_text}' (Language: {detected_language})")
        
        # Step 2: Get FAQ context
        context = ""
        try:
            faq_results = faq_service.search_faq(transcribed_text, company_id, limit=3)
            if faq_results:
                context = "\n".join([f"Q: {faq['question']}\nA: {faq['answer']}" for faq in faq_results])
        except Exception as e:
            logger.warning(f"FAQ search failed: {e}")
        
        # Step 3: Generate AI response
        ai_response, suggested_actions = llm_service.generate_response(
            message=transcribed_text,
            language=detected_language,
            context=context
        )
        
        response_time = int((time.time() - start_time) * 1000)
        
        logger.info(f"Voice-to-voice completed in {response_time}ms")
        
        return VoiceResponse(
            transcribed_text=transcribed_text,
            detected_language=detected_language,
            ai_response=ai_response,
            response_time_ms=response_time,
            session_id=session_id,
            suggested_actions=suggested_actions
        )
        
    except Exception as e:
        logger.error(f"Voice-to-voice failed: {e}")
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