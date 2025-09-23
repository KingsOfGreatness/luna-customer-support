import openai
import io
import logging
from typing import Optional, Tuple, Dict
from elevenlabs.client import ElevenLabs
import tempfile
import os
from app.core.config import settings
import hashlib
import json

logger = logging.getLogger(__name__)

class VoiceService:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.voice_cache = {}  # Cache for generated audio
        self.cache_max_size = 100  # Maximum cache entries
        
        # Initialize ElevenLabs
        self.voice_available = False
        self.elevenlabs_client = None
        
        if settings.ELEVENLABS_API_KEY and settings.ELEVENLABS_API_KEY != "your-elevenlabs-key-here":
            try:
                self.elevenlabs_client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
                self.voice_available = True
                logger.info("ElevenLabs client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize ElevenLabs: {e}")
        else:
            logger.warning("ElevenLabs API key not configured")
    
    def _get_cache_key(self, text: str, language: str) -> str:
        """Generate cache key for voice output"""
        # Use first 100 chars + language for cache key
        cache_text = text[:100] if len(text) > 100 else text
        key_string = f"{cache_text}_{language}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _manage_cache_size(self):
        """Keep cache size under limit by removing oldest entries"""
        if len(self.voice_cache) > self.cache_max_size:
            # Remove oldest 20% of cache
            remove_count = int(self.cache_max_size * 0.2)
            for _ in range(remove_count):
                self.voice_cache.pop(next(iter(self.voice_cache)))
    
    async def speech_to_text(self, audio_bytes: bytes, language: Optional[str] = None) -> Tuple[str, str]:
        """Convert speech to text using OpenAI Whisper"""
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_file_path = tmp_file.name
            
            # Transcribe with Whisper
            with open(tmp_file_path, "rb") as audio_file:
                response = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language[:2] if language else None  # Use language hint if provided
                )
            
            # Clean up temp file
            os.unlink(tmp_file_path)
            
            transcribed_text = response.text
            
            # Detect language if not provided
            if not language:
                # Simple language detection based on common words
                if any(word in transcribed_text.lower() for word in ['the', 'is', 'and', 'to']):
                    detected_language = 'english'
                elif any(word in transcribed_text.lower() for word in ['je', 'da', 'ne', 'ali']):
                    detected_language = 'srpski'
                elif any(word in transcribed_text.lower() for word in ['und', 'der', 'die', 'das']):
                    detected_language = 'deutsch'
                else:
                    detected_language = 'english'  # Default
            else:
                detected_language = language
            
            return transcribed_text, detected_language
            
        except Exception as e:
            logger.error(f"Speech-to-text failed: {e}")
            raise Exception(f"Failed to convert speech to text: {str(e)}")
    
    def text_to_speech(self, text: str, language: str = "english") -> bytes:
        """Convert text to speech with caching for performance"""
        
        # Check cache first
        cache_key = self._get_cache_key(text, language)
        if cache_key in self.voice_cache:
            logger.info(f"Returning cached audio for: {text[:50]}...")
            return self.voice_cache[cache_key]
        
        # Generate new audio if not cached
        if self.voice_available and self.elevenlabs_client:
            try:
                # Language to voice mapping
                voice_map = {
                    'english': 'Rachel',
                    'deutsch': 'Rachel',
                    'français': 'Rachel',
                    'italiano': 'Rachel',
                    'español': 'Rachel',
                    'hrvatski': 'Rachel',
                    'srpski': 'Rachel',
                    'slovenski': 'Rachel',
                    'bosanski': 'Rachel'
                }
                
                voice_name = voice_map.get(language, 'Rachel')
                
                # Generate audio with ElevenLabs
                audio_generator = self.elevenlabs_client.text_to_speech.convert(
                    voice_id=voice_name,
                    text=text,
                    model_id="eleven_multilingual_v2"
                )
                
                # Collect audio chunks
                audio_chunks = []
                for chunk in audio_generator:
                    if chunk:
                        audio_chunks.append(chunk)
                
                audio_bytes = b''.join(audio_chunks)
                
                # Cache the result
                self.voice_cache[cache_key] = audio_bytes
                self._manage_cache_size()
                
                logger.info(f"Generated and cached audio for: {text[:50]}...")
                return audio_bytes
                
            except Exception as e:
                logger.error(f"ElevenLabs TTS failed: {e}, falling back to OpenAI")
                return self._openai_tts_fallback(text, language, cache_key)
        else:
            # Use OpenAI TTS as fallback
            return self._openai_tts_fallback(text, language, cache_key)
    
    def _openai_tts_fallback(self, text: str, language: str, cache_key: str) -> bytes:
        """Fallback to OpenAI TTS if ElevenLabs unavailable"""
        try:
            response = self.openai_client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text
            )
            
            audio_bytes = response.content
            
            # Cache the result
            self.voice_cache[cache_key] = audio_bytes
            self._manage_cache_size()
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"OpenAI TTS also failed: {e}")
            raise Exception(f"Failed to convert text to speech: {str(e)}")
    
    def get_available_voices(self) -> list:
        """Get list of available voices"""
        if self.voice_available and self.elevenlabs_client:
            try:
                voices = self.elevenlabs_client.voices.get_all()
                return [{"id": v.voice_id, "name": v.name} for v in voices.voices]
            except Exception as e:
                logger.error(f"Failed to get voices: {e}")
                return []
        return []
    
    def health_check(self) -> dict:
        """Check voice service health"""
        return {
            "speech_to_text": "healthy",
            "text_to_speech": "healthy" if self.voice_available else "degraded",
            "cache_size": len(self.voice_cache),
            "elevenlabs_available": self.voice_available,
            "errors": []
        }