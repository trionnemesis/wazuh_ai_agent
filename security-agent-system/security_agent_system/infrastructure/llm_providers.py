"""LLM provider implementations."""
import asyncio
from typing import List, Optional
import openai
import anthropic
import google.generativeai as genai
import structlog

from ..core.interfaces import ILLMProvider
from ..core.config import settings

logger = structlog.get_logger()


class OpenAIProvider(ILLMProvider):
    """OpenAI LLM provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
            
        self.client = openai.AsyncOpenAI(api_key=self.api_key)
        
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generate response from OpenAI."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"} if "json" in prompt.lower() else None
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("OpenAI generation failed", error=str(e))
            raise
            
    async def embed(self, text: str) -> List[float]:
        """Generate embedding using OpenAI."""
        try:
            response = await self.client.embeddings.create(
                model=settings.embedding_model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error("OpenAI embedding failed", error=str(e))
            raise


class AnthropicProvider(ILLMProvider):
    """Anthropic Claude LLM provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key not provided")
            
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generate response from Claude."""
        try:
            message = await self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "You are a helpful AI assistant.",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error("Anthropic generation failed", error=str(e))
            raise
            
    async def embed(self, text: str) -> List[float]:
        """Generate embedding (not natively supported by Anthropic)."""
        # Fallback to OpenAI for embeddings
        logger.warning("Anthropic doesn't support embeddings, falling back to OpenAI")
        openai_provider = OpenAIProvider()
        return await openai_provider.embed(text)


class GoogleProvider(ILLMProvider):
    """Google Gemini LLM provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.google_api_key
        if not self.api_key:
            raise ValueError("Google API key not provided")
            
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generate response from Gemini."""
        try:
            # Combine system prompt with user prompt
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
                
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            )
            
            return response.text
            
        except Exception as e:
            logger.error("Google generation failed", error=str(e))
            raise
            
    async def embed(self, text: str) -> List[float]:
        """Generate embedding using Google."""
        try:
            # Use the embedding model
            embed_model = genai.GenerativeModel('models/embedding-001')
            response = await asyncio.to_thread(
                embed_model.embed_content,
                content=text,
                task_type="retrieval_document"
            )
            
            return response['embedding']
            
        except Exception as e:
            logger.error("Google embedding failed", error=str(e))
            # Fallback to OpenAI
            logger.warning("Google embedding failed, falling back to OpenAI")
            openai_provider = OpenAIProvider()
            return await openai_provider.embed(text)
