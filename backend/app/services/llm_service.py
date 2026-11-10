import logging
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base class for pluggable LLM inference providers."""

    @abstractmethod
    async def generate_completion(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 250,
    ) -> str:
        """Generates conversational text completion given system instruction and chat history."""
        pass


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini API provider implementation using official v1beta REST endpoints.
    Endpoint: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
    """

    def __init__(self, api_key: str, model: str = "gemini-3.5-flash-lite", timeout_seconds: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.timeout = httpx.Timeout(connect=15.0, read=timeout_seconds, write=15.0, pool=15.0)

    async def generate_completion(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 250,
    ) -> str:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        # Transform chat turns to Gemini content structure
        contents = []
        for msg in messages:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}]
            })

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        # Header and query param for auth per Gemini REST documentation
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        params = {"key": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, headers=headers, params=params, json=payload)
        except httpx.ConnectTimeout:
            logger.error("Connection timeout reaching Gemini LLM API.")
            raise ConnectionError("Connection timed out while reaching Gemini API.")
        except httpx.ReadTimeout:
            logger.error("Read timeout waiting for Gemini LLM response.")
            raise TimeoutError("Gemini reasoning request timed out.")
        except httpx.RequestError as exc:
            logger.error("Network error during Gemini request: %s", type(exc).__name__)
            raise ConnectionError(f"Network error communicating with Gemini API: {str(exc)}")

        if response.status_code == 400:
            error_msg = response.text[:200]
            logger.warning("Gemini API rejected request (HTTP 400): %s", error_msg)
            raise ValueError(f"Gemini API bad request: {error_msg}")
        elif response.status_code in (401, 403):
            logger.error("Gemini API authentication failure (HTTP %d).", response.status_code)
            raise PermissionError("Gemini API authentication failed. Verify LLM_API_KEY.")
        elif response.status_code in (402, 429):
            logger.error("Gemini API quota or rate limit exceeded (HTTP %d).", response.status_code)
            raise RuntimeError("Gemini API quota or rate limit exceeded.")
        elif response.status_code >= 500:
            logger.error("Gemini upstream service error (HTTP %d).", response.status_code)
            raise RuntimeError(f"Gemini upstream server error (HTTP {response.status_code}).")
        elif response.status_code != 200:
            raise RuntimeError(f"Gemini API returned unexpected status {response.status_code}.")

        try:
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("Gemini returned empty candidate list.")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise ValueError("Gemini returned empty content parts.")
            return parts[0].get("text", "").strip()
        except Exception as e:
            logger.error("Failed to parse Gemini response: %s", e)
            raise ValueError(f"Failed to parse Gemini response: {str(e)}")


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    OpenAI-compatible chat completions provider.
    Supports OpenAI, Gnani Evon (OpenAI-compatible mode), Groq, Together, etc.
    Endpoint: {base_url}/chat/completions
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(connect=10.0, read=timeout_seconds, write=10.0, pool=10.0)

    async def generate_completion(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 250,
    ) -> str:
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        openai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            role = "user" if msg.get("role") == "user" else "assistant"
            openai_messages.append({"role": role, "content": msg.get("content", "")})

        payload = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
        except httpx.ConnectTimeout:
            logger.error("Connection timeout reaching LLM provider API.")
            raise ConnectionError("Connection timed out while reaching LLM provider.")
        except httpx.ReadTimeout:
            logger.error("Read timeout waiting for LLM response.")
            raise TimeoutError("LLM reasoning request timed out.")
        except httpx.RequestError as exc:
            logger.error("Network error during LLM request: %s", type(exc).__name__)
            raise ConnectionError(f"Network error communicating with LLM provider: {str(exc)}")

        if response.status_code in (401, 403):
            logger.error("LLM provider authentication failure (HTTP %d).", response.status_code)
            raise PermissionError("LLM provider authentication failed. Verify LLM_API_KEY.")
        elif response.status_code in (402, 429):
            logger.error("LLM provider rate limit exceeded (HTTP %d).", response.status_code)
            raise RuntimeError("LLM provider rate limit or quota exceeded.")
        elif response.status_code >= 500:
            logger.error("LLM upstream service error (HTTP %d).", response.status_code)
            raise RuntimeError(f"LLM upstream server error (HTTP {response.status_code}).")
        elif response.status_code != 200:
            raise RuntimeError(f"LLM provider returned unexpected status {response.status_code}.")

        try:
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("LLM provider returned empty choices list.")
            text = choices[0].get("message", {}).get("content", "")
            return text.strip()
        except Exception as e:
            logger.error("Failed to parse LLM response: %s", e)
            raise ValueError(f"Failed to parse LLM response: {str(e)}")


class LLMService:
    """
    VoiceBridge LLM reasoning service.
    Orchestrates contextual conversational understanding for multilingual Indian voice input.
    """

    def __init__(
        self,
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider_name = (provider_name or settings.LLM_PROVIDER).strip().lower()
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.base_url = base_url or settings.OPENAI_BASE_URL
        self._provider = self._init_provider()

    def _init_provider(self) -> Optional[BaseLLMProvider]:
        """Instantiates the configured LLM backend provider."""
        if not self.api_key or self.api_key == "your_llm_api_key_here":
            return None

        if self.provider_name == "gemini":
            return GeminiProvider(api_key=self.api_key, model=self.model)
        elif self.provider_name in ("openai", "gnani_evon", "evon", "custom"):
            return OpenAICompatibleProvider(
                api_key=self.api_key,
                model=self.model,
                base_url=self.base_url,
            )
        else:
            # Fallback to OpenAI-compatible provider for custom LLMs
            return OpenAICompatibleProvider(
                api_key=self.api_key,
                model=self.model,
                base_url=self.base_url,
            )

    def is_configured(self) -> bool:
        """Returns True if a valid API key is present and provider is initialized."""
        return bool(self.api_key and self.api_key != "your_llm_api_key_here" and self._provider is not None)

    def _build_system_prompt(self, target_language: str, detected_language: Optional[str] = None) -> str:
        """
        Builds system prompt enforcing natural, concise Indian voice assistant persona.
        Optimized specifically for Text-to-Speech synthesis.
        """
        prompt = (
            "You are VoiceBridge, a warm, intelligent, and context-aware multilingual voice assistant "
            "designed specifically for Indian users. Your response will be directly synthesized into spoken voice.\n\n"
            "Critical Response Rules:\n"
            "1. Answer concisely in strictly 1 to 3 short conversational sentences (under 40 words).\n"
            "2. Never use bullet points, numbered lists, emojis, asterisks (*), hashtags (#), or Markdown formatting.\n"
            f"3. Target Spoken Language: Respond in {target_language}.\n"
        )

        lang_lower = target_language.lower()
        if lang_lower in ("tanglish", "tamil+english", "ta-en"):
            prompt += "4. Use natural colloquial Tanglish (Tamil spoken with everyday English words written in Latin script).\n"
        elif lang_lower in ("hinglish", "hindi+english", "hi-en"):
            prompt += "4. Use natural colloquial Hinglish (Hindi spoken with everyday English words written in Latin script).\n"
        elif lang_lower in ("tamil", "ta", "ta-in"):
            prompt += "4. Respond in natural, polite Tamil script.\n"
        elif lang_lower in ("hindi", "hi", "hi-in"):
            prompt += "4. Respond in clear, natural Hindi Devanagari script.\n"
        elif lang_lower in ("english", "en", "en-in"):
            prompt += "4. Respond in polite, friendly Indian English.\n"

        prompt += "5. If you cannot reliably understand the input, politely ask for clarification in 1 brief sentence."
        return prompt

    @staticmethod
    def _sanitize_for_tts(text: str) -> str:
        """Removes Markdown characters and symbols so speech synthesis sounds natural."""
        clean = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)  # keep anchor text, remove url
        clean = re.sub(r"[\*#_~`>]", "", clean)
        clean = re.sub(r"\s+([.,!?;:])", r"\1", clean)  # fix spacing before punctuation
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    async def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        target_language: str = "Tamil",
        detected_language: Optional[str] = None,
    ) -> str:
        """
        Generates contextual conversational assistant reply.

        Args:
            user_message: Latest user transcript.
            conversation_history: Previous turns [{"role": "user"|"assistant", "content": ...}].
            target_language: Requested response language.
            detected_language: Language code detected by STT.

        Returns:
            Concise conversational string ready for TTS speech synthesis.
        """
        if not self.is_configured():
            logger.error("LLMService called but provider is not configured.")
            raise ValueError(
                f"LLM provider '{self.provider_name}' is not configured. Please set LLM_API_KEY in backend/.env"
            )

        if not user_message or not user_message.strip():
            raise ValueError("User message for LLM reasoning cannot be empty.")

        system_prompt = self._build_system_prompt(
            target_language=target_language,
            detected_language=detected_language,
        )

        # Prepare messages payload including history
        messages = []
        for turn in conversation_history:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # Append current user prompt
        messages.append({"role": "user", "content": user_message.strip()})

        logger.info(
            "Calling LLM (%s:%s) with %d history turns for target_language='%s'",
            self.provider_name,
            self.model,
            len(conversation_history),
            target_language,
        )

        raw_response = await self._provider.generate_completion(
            system_prompt=system_prompt,
            messages=messages,
        )

        clean_response = self._sanitize_for_tts(raw_response)
        logger.info("LLM generated response (%d chars)", len(clean_response))
        return clean_response
