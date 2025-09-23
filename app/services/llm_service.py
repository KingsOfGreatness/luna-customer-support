import openai
import json
import logging
from typing import Dict, List, Optional, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"  # Cost-effective, fast, multilingual
        
    def detect_language(self, text: str) -> str:
        """Detect language from user message with improved accuracy"""
        language_map = {
            'english': 'english',
            'croatian': 'hrvatski', 
            'slovenian': 'slovenski',
            'german': 'deutsch',
            'italian': 'italiano',
            'french': 'français',
            'spanish': 'español',
            'serbian': 'srpski',
            'bosnian': 'bosanski'
        }
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": """Detect the language of the user's message. Pay special attention to language switching requests like "speak English", "talk in German", "respond in French", etc. 

If the user is asking to switch languages, respond with the target language they want.
If they're just writing in a language, respond with that language.

Respond with only one word: english, croatian, slovenian, german, italian, french, spanish, serbian, or bosnian."""
                    },
                    {"role": "user", "content": text}
                ],
                max_tokens=10,
                temperature=0
            )
            
            detected = response.choices[0].message.content.strip().lower()
            return language_map.get(detected, 'english')
            
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return 'english'
    
    def generate_response(self, message: str, language: str, context: str = "") -> Tuple[str, List[str]]:
        """Generate response using OpenAI with context"""
        
        # Language-specific prompts for WWin gambling platform
        prompts = {
            'english': "You are Luna, a helpful customer support assistant for WWin gambling platform. Answer questions about account issues, betting, bonuses, payments, and technical problems. Be professional and helpful. Answer in English.",
            'hrvatski': "Ti si Luna, korisna asistentka za korisničku podršku WWin platforme za klađenje. Odgovaraj na pitanja o računima, klađenju, bonusima, plaćanjima. Odgovori na hrvatskom.",
            'slovenski': "Ti si Luna, uporabna asistentka za stranke WWin platforme. Odgovori na vprašanja o računih, stavi, bonusih. Odgovori v slovenščini.",
            'deutsch': "Du bist Luna, Kundenbetreuungsassistentin für die WWin Wett-Plattform. Beantworte Fragen zu Konten, Wetten, Boni. Antworte auf Deutsch.",
            'italiano': "Sei Luna, assistente clienti per la piattaforma di scommesse WWin. Rispondi a domande su account, scommesse, bonus. Rispondi in italiano.",
            'français': "Tu es Luna, assistante clientèle pour la plateforme de paris WWin. Réponds aux questions sur les comptes, paris, bonus. Réponds en français.",
            'español': "Eres Luna, asistente de atención al cliente para la plataforma de apuestas WWin. Responde preguntas sobre cuentas, apuestas, bonos. Responde en español.",
            'srpski': "Ti si Luna, korisna asistentka za korisničku podršku WWin platforme za klađenje. Odgovaraj na pitanja o računima, klađenju, bonusima, uplatama, isplatama i tehničkim problemima. Budi profesionalna i korisna. Odgovori na srpskom.",
            'bosanski': "Ti si Luna, korisna asistentka za korisničku podršku WWin platforme za klađenje. Odgovaraj na pitanja o računima, klađenju, bonusima. Odgovori na bosanskom."
        }
        
        # WWin-specific quick reply suggestions by language
        quick_replies = {
            'english': ["Can't login?", "Reset password?", "Activation email?", "Account blocked?", "Bonus info?"],
            'hrvatski': ["Ne mogu se prijaviti?", "Reset lozinke?", "Aktivacijski email?", "Blokiran račun?", "Info o bonusu?"],
            'slovenski': ["Ne morem se prijaviti?", "Ponastavi geslo?", "Aktivacijski email?", "Blokiran račun?"],
            'deutsch': ["Kann nicht einloggen?", "Passwort zurücksetzen?", "Aktivierungs-E-Mail?", "Konto gesperrt?"],
            'italiano': ["Non riesco ad accedere?", "Reset password?", "Email attivazione?", "Account bloccato?"],
            'français': ["Impossible de me connecter?", "Réinitialiser mot de passe?", "Email d'activation?", "Compte bloqué?"],
            'español': ["¿No puedo conectarme?", "¿Restablecer contraseña?", "¿Email de activación?", "¿Cuenta bloqueada?"],
            'srpski': ["Ne mogu se prijaviti?", "Resetuj lozinku?", "Aktivacijski email?", "Blokiran račun?", "Bonus info?"],
            'bosanski': ["Ne mogu se prijaviti?", "Reset lozinke?", "Aktivacijski email?", "Blokiran račun?"]
        }
        
        system_prompt = prompts.get(language, prompts['english'])
        
        # Add context if available
        if context:
            system_prompt += f"\n\nUse this FAQ context to help answer: {context}"
            
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content.strip()
            suggested_actions = quick_replies.get(language, quick_replies['english'])
            
            return ai_response, suggested_actions
            
        except Exception as e:
            logger.error(f"OpenAI API failed: {e}")
            
            # Fallback responses by language
            fallbacks = {
                'english': "I'm having technical difficulties. Please contact our support team.",
                'hrvatski': "Imam tehničke poteškoće. Molimo kontaktirajte našu podršku.",
                'slovenski': "Imam tehnične težave. Prosim, kontaktirajte našo podporo.",
                'deutsch': "Ich habe technische Schwierigkeiten. Bitte kontaktieren Sie unser Support-Team.",
                'italiano': "Sto avendo difficoltà tecniche. Contatta il nostro team di supporto.",
                'français': "J'ai des difficultés techniques. Veuillez contacter notre équipe de support.",
                'español': "Tengo dificultades técnicas. Contacta a nuestro equipo de soporte.",
                'srpski': "Imam tehničke probleme. Molim vas kontaktirajte našu podršku.",
                'bosanski': "Imam tehničke probleme. Molim vas kontaktirajte našu podršku."
            }
            
            fallback_msg = fallbacks.get(language, fallbacks['english'])
            return fallback_msg, quick_replies.get(language, quick_replies['english'])