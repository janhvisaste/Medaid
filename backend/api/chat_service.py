"""
Chat service for managing persistent conversations with context memory
Includes AI-powered title generation and token management
"""

import logging
import os
from typing import Dict, List, Optional
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None
from dotenv import load_dotenv
from .triage_engine_v2 import TriageEngineV2

load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')


class ChatService:
    """Service for managing chat conversations with AI"""
    
    # Token limits for context management
    MAX_CONTEXT_TOKENS = 3000  # Max tokens to include in context
    MAX_TOTAL_TOKENS = 8000    # Total token limit before suggesting new chat
    
    def __init__(self):
        self.client = (
            genai.Client(api_key=GOOGLE_API_KEY)
            if GOOGLE_API_KEY and genai is not None
            else None
        )
    
    def generate_chat_title(self, first_user_message: str) -> str:
        """
        Generate a concise, descriptive title for a chat based on the first message
        
        Args:
            first_user_message: The user's first message in the conversation
            
        Returns:
            A short, descriptive title (max 50 characters)
        """
        if not self.client:
            # Fallback: use first few words
            words = first_user_message.split()[:5]
            return ' '.join(words) + ('...' if len(words) >= 5 else '')
        
        try:
            prompt = f"""Generate a very short, descriptive title (max 5 words) for a medical chat conversation that starts with this message:

"{first_user_message}"

Return ONLY the title, nothing else. Make it specific and informative.
Examples:
- "Fever and Body Pain"
- "Chest Pain Consultation"
- "Diabetes Management"
- "Child's Cough Symptoms"
"""
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=20,
                ),
            )
            
            title = response.text.strip()
            # Remove quotes if present
            title = title.strip('"\'')
            
            # Limit to 50 characters
            if len(title) > 50:
                title = title[:47] + '...'
            
            return title
            
        except Exception as e:
            # Title text is derived from patient message content, so log only
            # the error type - never the message or the model's output.
            logger.warning(
                "chat.title_generation_failed",
                extra={"error_type": type(e).__name__},
            )
            # Fallback
            words = first_user_message.split()[:5]
            return ' '.join(words) + ('...' if len(words) >= 5 else '')
    
    def build_context_messages(self, messages: List[Dict], max_tokens: int = MAX_CONTEXT_TOKENS) -> List[Dict]:
        """
        Build context messages from conversation history with token management
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to include in context
            
        Returns:
            List of messages to include in context
        """
        if not messages:
            return []
        
        context = []
        tokens_estimate = 0
        
        # Start from the most recent messages
        for msg in reversed(messages):
            # Estimate tokens (rough: ~4 chars per token)
            msg_tokens = (len(msg['content']) + len(msg['role'])) // 4
            
            if tokens_estimate + msg_tokens > max_tokens:
                # If we're over limit, stop adding messages
                break
            
            context.insert(0, {
                'role': msg['role'],
                'content': msg['content']
            })
            tokens_estimate += msg_tokens
        
        # Always include at least the last message pair (user + assistant)
        if len(context) < 2 and len(messages) >= 2:
            context = [
                {'role': messages[-2]['role'], 'content': messages[-2]['content']},
                {'role': messages[-1]['role'], 'content': messages[-1]['content']}
            ]
        
        return context
    
    def should_suggest_new_chat(self, total_tokens: int) -> bool:
        """
        Determine if we should suggest starting a new chat based on token usage
        
        Args:
            total_tokens: Total tokens used in the conversation
            
        Returns:
            True if a new chat should be suggested
        """
        return total_tokens >= self.MAX_TOTAL_TOKENS
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a piece of text
        Rough estimation: ~4 characters per token
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def generate_ai_response(
        self,
        user_message: str,
        context_messages: List[Dict],
        user_data: Optional[Dict] = None,
        model_id: Optional[str] = None,
    ) -> Dict:
        """
        Generate AI response using TriageEngineV2
        
        Args:
            user_message: Current user message
            context_messages: Previous conversation messages for context
            user_data: Optional user profile data (age, gender, past_history)
            
        Returns:
            Dict with response content and metadata
        """
        # STEP 1: Normalize inputs at ENTRY POINT (MANDATORY)
        user_message = user_message or ""
        context_messages = context_messages or []
        
        try:
            # STEP 2: SANITIZE context replay (THIS IS THE BIG ONE)
            context_text = ""
            for msg in context_messages:
                role = "Patient" if msg.get('role') == 'user' else "AI"
                content = msg.get('content') or ""  # <-- FIX: Prevent None concatenation
                context_text += f"{role}: {content}\n"
            
            context_text += f"Patient: {user_message}"
            
            # Use TriageEngineV2 for the assessment
            engine = TriageEngineV2()
            assessment = engine.assess(
                symptoms_text=context_text,
                user_data=user_data or {},
                report_summary="",
                location="",
                model_id=model_id,
                # chat_send_message already ran contains_emergency_keyword() on
                # the raw current-turn user_message before calling here.
                # context_text additionally carries prior "AI: ..." turns -
                # including any clarifying question the assistant itself
                # asked, which routinely names the symptom it's asking about
                # (e.g. "Are you experiencing chest pain?"). Re-scanning that
                # merged text would trigger on the assistant's own wording.
                skip_emergency_recheck=True,
            )
            
            # Format the structured assessment into the requested readability format
            if assessment.get('degraded') or assessment.get('assessment_source') == 'llm_fallback':
                response_text = "⚠️ Degraded response: We couldn't complete a full AI analysis for this request.\n\n"
            else:
                response_text = ""

            provider_label = assessment.get('model_provider') or 'unknown provider'
            model_label = assessment.get('model_id') or 'default model'
            response_text += f"Model used: {model_label} ({provider_label})\n\n"

            response_text += f"1. Assessment: {assessment.get('reasoning')}\n\n"
            
            # Extract symptoms for patient
            response_text += f"2. Patient: {user_message}\n\n"
            
            response_text += "3. Possible Causes:\n"
            if assessment.get('possible_conditions'):
                for condition in assessment['possible_conditions']:
                    conf = int(condition.get('confidence', 0) * 100)
                    response_text += f"• {condition.get('disease')} ({conf}% match)\n"
            else:
                response_text += "• No specific causes identified.\n"
            response_text += "\n"
            
            response_text += "4. Recommendations:\n"
            if assessment.get('recommendations'):
                for rec in assessment['recommendations']:
                    response_text += f"• {rec}\n"
            else:
                response_text += "• No specific recommendations provided.\n"
            response_text += "\n"
                
            response_text += f"5. When to seek care:\n{assessment.get('when_to_seek_care', 'If symptoms worsen, please consult a healthcare professional.')}\n\n"
                
            disclaimer = assessment.get('disclaimer', 'This is an AI-generated assessment. Please consult a qualified healthcare provider for accurate diagnosis and treatment.')
            if assessment.get('risk_level') == 'emergency':
                disclaimer = "🚨 EMERGENCY 🚨 Please seek immediate medical attention! " + disclaimer
                
            response_text += f"6. INFORMATIONAL:\n{disclaimer}"

            tokens_used = self.estimate_tokens(user_message + response_text)

            return {
                'content': response_text,
                'tokens_used': tokens_used,
                'model_id': assessment.get('model_id'),
                'model_provider': assessment.get('model_provider'),
                'degraded': bool(assessment.get('degraded')),
                'assessment_source': assessment.get('assessment_source'),
                # Full structured result, passed through so the caller can
                # persist a TriageRecord and the frontend can render a rich
                # assessment card (risk badge, conditions, PDF, facilities)
                # instead of just the formatted text above. generate_ai_response
                # already ran the same TriageEngineV2.assess() call underneath -
                # this exposes what was already computed rather than discarding it.
                'risk_level': assessment.get('risk_level'),
                'reasoning': assessment.get('reasoning', ''),
                'risk_probability': assessment.get('risk_probability', 0.0),
                'confidence': assessment.get('confidence', 0.0),
                'possible_conditions': assessment.get('possible_conditions', []),
                'recommendations': assessment.get('recommendations', []),
                'when_to_seek_care': assessment.get('when_to_seek_care', ''),
                'requires_human_review': bool(assessment.get('requires_human_review')),
                'is_degraded': bool(assessment.get('is_degraded') or assessment.get('degraded')),
            }
            
        except Exception as e:
            logger.exception(
                "chat.ai_response_failed",
                extra={"error_type": type(e).__name__},
            )
            return {
                'content': (
                    "⚠️ Degraded response: We couldn't complete a full AI analysis because the request failed. "
                    "Please try again or select another model."
                ),
                'tokens_used': 0,
                'degraded': True,
                'assessment_source': 'llm_fallback',
                'model_error': str(e),
            }


# Singleton instance
_chat_service = None

def get_chat_service() -> ChatService:
    """Get singleton instance of ChatService"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
