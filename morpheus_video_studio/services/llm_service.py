# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
LLM (Large Language Model) Service - Direct OpenAI SDK implementation

Supports structured output via response_type parameter (Pydantic model).
"""

import asyncio
import json
import re
from typing import Optional, Type, TypeVar, Union

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel
from loguru import logger


T = TypeVar("T", bound=BaseModel)


async def _create_with_retry(client: AsyncOpenAI, max_attempts: int = 3, **params):
    """chat.completions.create with backoff on transient failures.

    Retries rate limits (429, common on free-tier OpenRouter models), 5xx
    provider errors, and connection drops. Client errors (4xx) fail fast —
    a bad request won't fix itself.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return await client.chat.completions.create(**params)
        except (RateLimitError, APIConnectionError, APIStatusError) as exc:
            is_client_error = (
                isinstance(exc, APIStatusError)
                and not isinstance(exc, RateLimitError)
                and exc.status_code < 500
            )
            if is_client_error or attempt == max_attempts:
                raise
            wait_seconds = 3 * attempt
            logger.warning(
                f"LLM transient error (attempt {attempt}/{max_attempts}): {exc}; "
                f"retrying in {wait_seconds}s"
            )
            await asyncio.sleep(wait_seconds)


class LLMService:
    """
    LLM (Large Language Model) service
    
    Direct implementation using OpenAI SDK. No capability layer needed.
    
    Supports all OpenAI SDK compatible providers:
    - OpenAI (gpt-4o, gpt-4o-mini, gpt-3.5-turbo)
    - Alibaba Qwen (qwen-max, qwen-plus, qwen-turbo)
    - Anthropic Claude (claude-sonnet-4-5, claude-opus-4, claude-haiku-4)
    - DeepSeek (deepseek-chat)
    - Moonshot Kimi (moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k)
    - Ollama (llama3.2, qwen2.5, mistral, codellama) - FREE & LOCAL!
    - Any custom provider with OpenAI-compatible API
    
    Usage:
        # Direct call
        answer = await morpheus_video_studio.llm("Explain atomic habits")
        
        # With parameters
        answer = await morpheus_video_studio.llm(
            prompt="Explain atomic habits in 3 sentences",
            temperature=0.7,
            max_tokens=2000
        )
    """
    
    def __init__(self, config: dict):
        """
        Initialize LLM service
        
        Args:
            config: Full application config dict (kept for backward compatibility)
        """
        # Note: We no longer cache config here to support hot reload
        # Config is read dynamically from config_manager in _get_config_value()
        self._client: Optional[AsyncOpenAI] = None
    
    def _get_config_value(self, key: str, default=None):
        """
        Get config value dynamically from config_manager (supports hot reload)
        
        Args:
            key: Config key name
            default: Default value if not found
        
        Returns:
            Config value
        """
        from morpheus_video_studio.config import config_manager
        return getattr(config_manager.config.llm, key, default)
    
    def _create_client(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> AsyncOpenAI:
        """
        Create OpenAI client
        
        Args:
            api_key: API key (optional, uses config if not provided)
            base_url: Base URL (optional, uses config if not provided)
        
        Returns:
            AsyncOpenAI client instance
        """
        # Get API key (priority: parameter > config)
        final_api_key = (
            api_key
            or self._get_config_value("api_key")
            or "dummy-key"  # Ollama doesn't need real key
        )
        
        # Get base URL (priority: parameter > config)
        final_base_url = (
            base_url
            or self._get_config_value("base_url")
        )
        
        # Create client
        client_kwargs = {"api_key": final_api_key}
        if final_base_url:
            client_kwargs["base_url"] = final_base_url
        client_kwargs["timeout"] = float(self._get_config_value("timeout_seconds", 25) or 25)
        client_kwargs["max_retries"] = 0
        
        return AsyncOpenAI(**client_kwargs)
    
    async def __call__(
        self,
        prompt: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_type: Optional[Type[T]] = None,
        **kwargs
    ) -> Union[str, T]:
        """
        Generate text using LLM
        
        Args:
            prompt: The prompt to generate from
            api_key: API key (optional, uses config if not provided)
            base_url: Base URL (optional, uses config if not provided)
            model: Model name (optional, uses config if not provided)
            temperature: Sampling temperature (0.0-2.0). Lower is more deterministic.
            max_tokens: Maximum tokens to generate
            response_type: Optional Pydantic model class for structured output.
                          If provided, returns parsed model instance instead of string.
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Generated text (str) or parsed Pydantic model instance (if response_type provided)
        
        Examples:
            # Basic text generation
            answer = await morpheus_video_studio.llm("Explain atomic habits")
            
            # Structured output with Pydantic model
            class MovieReview(BaseModel):
                title: str
                rating: int
                summary: str
            
            review = await morpheus_video_studio.llm(
                prompt="Review the movie Inception",
                response_type=MovieReview
            )
            print(review.title)  # Structured access
        """
        # Create client (new instance each time to support parameter overrides)
        client = self._create_client(api_key=api_key, base_url=base_url)
        
        # Get model (priority: parameter > config)
        final_model = (
            model
            or self._get_config_value("model")
            or "gpt-3.5-turbo"  # Default fallback
        )
        
        logger.debug(f"LLM call: model={final_model}, base_url={client.base_url}, response_type={response_type}")
        self._apply_provider_defaults(client=client, kwargs=kwargs)
        
        try:
            if response_type is not None:
                # Structured output mode - try beta.chat.completions.parse first
                return await self._call_with_structured_output(
                    client=client,
                    model=final_model,
                    prompt=prompt,
                    response_type=response_type,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            else:
                # Standard text output mode
                response = await _create_with_retry(
                    client,
                    model=final_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                choice = response.choices[0]
                result = choice.message.content
                if result is None:
                    finish_reason = getattr(choice, "finish_reason", None)
                    raise RuntimeError(
                        "LLM returned an empty response. "
                        f"Please try another model or check provider limits. finish_reason={finish_reason}"
                    )
                logger.debug(f"LLM response length: {len(result)} chars")
                
                return result
        
        except APITimeoutError as e:
            logger.error(f"LLM timeout (model={final_model}, base_url={client.base_url}): {e}")
            raise RuntimeError(
                f"LLM 请求超时（>{int(float(self._get_config_value('timeout_seconds', 25) or 25))}s）："
                f"{final_model} 暂时没有响应。请重试，或在 Settings 里切换到更稳定的模型。"
            ) from e
        except Exception as e:
            logger.error(f"LLM call error (model={final_model}, base_url={client.base_url}): {e}")
            raise

    def _apply_provider_defaults(self, client: AsyncOpenAI, kwargs: dict):
        """Apply provider-specific defaults that keep generic app calls reliable."""
        base_url = str(client.base_url)
        if "openrouter.ai" not in base_url:
            return

        extra_body = dict(kwargs.get("extra_body") or {})
        # Reasoning models on OpenRouter (gpt-oss, deepseek-r1, o-series…)
        # reject requests that disable reasoning outright ("Reasoning is
        # mandatory for this endpoint"). Lowest effort + exclude keeps those
        # endpoints happy, keeps think-text out of the output, and is ignored
        # by models without reasoning support.
        extra_body.setdefault("reasoning", {"effort": "low", "exclude": True})
        kwargs["extra_body"] = extra_body
    
    async def _call_with_structured_output(
        self,
        client: AsyncOpenAI,
        model: str,
        prompt: str,
        response_type: Type[T],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> T:
        """
        Call LLM with structured output support
        
        Uses JSON schema instruction appended to prompt for maximum compatibility
        across all OpenAI-compatible providers (Qwen, DeepSeek, etc.).
        
        Args:
            client: OpenAI client
            model: Model name
            prompt: The prompt
            response_type: Pydantic model class
            temperature: Sampling temperature
            max_tokens: Max tokens
            **kwargs: Additional parameters
        
        Returns:
            Parsed Pydantic model instance
        """
        # Build JSON schema instruction and append to prompt
        json_schema_instruction = self._get_json_schema_instruction(response_type)
        enhanced_prompt = f"{prompt}\n\n{json_schema_instruction}"
        
        # Call LLM with enhanced prompt
        response = await _create_with_retry(
            client,
            model=model,
            messages=[{"role": "user", "content": enhanced_prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        choice = response.choices[0]
        content = choice.message.content
        if content is None:
            finish_reason = getattr(choice, "finish_reason", None)
            raise RuntimeError(
                "LLM returned an empty structured response. "
                f"Please try another model or check provider limits. finish_reason={finish_reason}"
            )
        
        logger.debug(f"Structured output response length: {len(content)} chars")
        
        # Parse JSON from response content
        return self._parse_response_as_model(content, response_type)
    
    def _get_json_schema_instruction(self, response_type: Type[T]) -> str:
        """
        Generate JSON schema instruction for LLM fallback mode
        
        Args:
            response_type: Pydantic model class
        
        Returns:
            Formatted instruction string with JSON schema
        """
        try:
            # Get JSON schema from Pydantic model
            schema = response_type.model_json_schema()
            schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
            
            return f"""## IMPORTANT: JSON Output Format Required
You MUST respond with ONLY a valid JSON object (no markdown, no extra text).
The JSON must strictly follow this schema:

```json
{schema_str}
```

Output ONLY the JSON object, nothing else."""
        except Exception as e:
            logger.warning(f"Failed to generate JSON schema: {e}")
            return """## IMPORTANT: JSON Output Format Required
You MUST respond with ONLY a valid JSON object (no markdown, no extra text)."""
    
    def _parse_response_as_model(self, content: str, response_type: Type[T]) -> T:
        """
        Parse LLM response content as Pydantic model
        
        Args:
            content: Raw LLM response text
            response_type: Target Pydantic model class
        
        Returns:
            Parsed model instance
        """
        # Try direct JSON parsing first
        try:
            data = json.loads(content)
            return response_type.model_validate(data)
        except json.JSONDecodeError:
            pass
        
        # Try extracting from markdown code block
        json_pattern = r'```(?:json)?\s*([\s\S]+?)\s*```'
        match = re.search(json_pattern, content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return response_type.model_validate(data)
            except json.JSONDecodeError:
                pass
        
        # Try to find any JSON object in the text
        brace_start = content.find('{')
        brace_end = content.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            try:
                json_str = content[brace_start:brace_end + 1]
                data = json.loads(json_str)
                return response_type.model_validate(data)
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"Failed to parse LLM response as {response_type.__name__}: {content[:200]}...")
    
    @property
    def active(self) -> str:
        """
        Get active model name
        
        Returns:
            Active model name
        
        Example:
            print(f"Using model: {morpheus_video_studio.llm.active}")
        """
        return self._get_config_value("model", "gpt-3.5-turbo")
    
    def __repr__(self) -> str:
        """String representation"""
        model = self.active
        base_url = self._get_config_value("base_url", "default")
        return f"<LLMService model={model!r} base_url={base_url!r}>"
