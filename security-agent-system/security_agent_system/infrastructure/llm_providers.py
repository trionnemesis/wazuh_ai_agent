"""LLM 供應商實作。"""
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
    """OpenAI LLM 供應商實作。"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("未提供 OpenAI API 金鑰")
            
        self.client = openai.AsyncOpenAI(api_key=self.api_key)
        
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """從 OpenAI 產生回應。"""
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
            logger.error("OpenAI 生成失敗", error=str(e))
            raise
            
    async def embed(self, text: str) -> List[float]:
        """使用 OpenAI 產生嵌入。"""
        try:
            response = await self.client.embeddings.create(
                model=settings.embedding_model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error("OpenAI 嵌入失敗", error=str(e))
            raise


class AnthropicProvider(ILLMProvider):
    """Anthropic Claude LLM 供應商實作。"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("未提供 Anthropic API 金鑰")
            
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """從 Claude 產生回應。"""
        try:
            message = await self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "您是一位有幫助的 AI 助理。",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error("Anthropic 生成失敗", error=str(e))
            raise
            
    async def embed(self, text: str) -> List[float]:
        """產生嵌入（Anthropic 原生不支援）。"""
        # 後備使用 OpenAI 進行嵌入
        logger.warning("Anthropic 不支援嵌入，後備使用 OpenAI")
        openai_provider = OpenAIProvider()
        return await openai_provider.embed(text)


class GoogleProvider(ILLMProvider):
    """Google Gemini LLM 供應商實作。"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.google_api_key
        if not self.api_key:
            raise ValueError("未提供 Google API 金鑰")
            
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """從 Gemini 產生回應。"""
        try:
            # 將系統提示與使用者提示結合
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
            logger.error("Google 生成失敗", error=str(e))
            raise
            
    async def embed(self, text: str) -> List[float]:
        """使用 Google 產生嵌入。"""
        try:
            # 使用嵌入模型
            embed_model = genai.GenerativeModel('models/embedding-001')
            response = await asyncio.to_thread(
                embed_model.embed_content,
                content=text,
                task_type="retrieval_document"
            )
            
            return response['embedding']
            
        except Exception as e:
            logger.error("Google 嵌入失敗", error=str(e))
            # 後備使用 OpenAI
            logger.warning("Google 嵌入失敗，後備使用 OpenAI")
            openai_provider = OpenAIProvider()
            return await openai_provider.embed(text)