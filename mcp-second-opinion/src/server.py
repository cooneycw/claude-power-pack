#!/usr/bin/env python3
"""
Second Opinion MCP Server

An MCP server that provides LLM-powered second opinions on challenging coding issues.
Powered by Google Gemini and OpenAI (Codex + GPT-5.2) with streaming support.
Supports multi-model consultation for comparing responses from different LLMs.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import openai
from fastmcp import FastMCP
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import Config
from prompts import build_code_review_prompt, scan_for_secrets
from sessions import get_session_manager, Session
from tools import (
    web_search,
    fetch_url,
    WEB_SEARCH_DECLARATION,
    FETCH_URL_DECLARATION,
    approve_domain,
    revoke_domain,
    get_approved_domains,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(Config.SERVER_NAME)

# Configure Gemini
if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)
    logger.info("Gemini API configured successfully")
else:
    logger.warning("GEMINI_API_KEY not set - Gemini models will be unavailable")

# Configure OpenAI
_openai_client: Optional[openai.AsyncOpenAI] = None
if Config.OPENAI_API_KEY:
    _openai_client = openai.AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
    logger.info("OpenAI API configured successfully")
else:
    logger.warning("OPENAI_API_KEY not set - OpenAI/Codex models will be unavailable")

# Global model instance cache (reuse across requests to avoid cold starts)
_gemini_models: Dict[str, genai.GenerativeModel] = {}
_model_lock: asyncio.Lock = asyncio.Lock()

# Gemini context cache storage (maps cache_name -> cache_object)
_context_caches: Dict[str, Dict[str, Any]] = {}
_cache_lock: asyncio.Lock = asyncio.Lock()


async def get_or_create_context_cache(
    system_instruction: str,
    model_name: str,
    cache_key: str,
) -> Optional[str]:
    """
    Get or create a Gemini context cache for system instructions.

    Context caching reduces latency and cost for repeated prompts with the same
    system instructions (like code review templates).

    Args:
        system_instruction: The system instruction to cache
        model_name: Model to use for the cache
        cache_key: Unique identifier for this cache

    Returns:
        Cache name if caching is enabled and successful, None otherwise
    """
    if not Config.ENABLE_CONTEXT_CACHING:
        return None

    try:
        async with _cache_lock:
            # Check if we have a valid cached version
            if cache_key in _context_caches:
                cached = _context_caches[cache_key]
                # Check if cache is still valid (not expired)
                created_at = cached.get("created_at")
                ttl_minutes = cached.get("ttl_minutes", Config.CACHE_TTL_MINUTES)

                if created_at and created_at + timedelta(minutes=ttl_minutes) < datetime.now():
                    logger.info(f"Context cache expired, removing: {cache_key}")
                    del _context_caches[cache_key]
                else:
                    logger.info(f"Using existing context cache: {cache_key}")
                    return cached.get("name")

            # Create new context cache
            # Note: Gemini requires minimum token count (2048+ for most models)
            if len(system_instruction) < 2048 * 4:  # ~2048 tokens minimum
                logger.debug("System instruction too short for context caching")
                return None

            logger.info(f"Creating new context cache: {cache_key}")

            # Use Gemini's caching API
            cache = genai.caching.CachedContent.create(
                model=model_name,
                system_instruction=system_instruction,
                ttl=timedelta(minutes=Config.CACHE_TTL_MINUTES),
            )

            _context_caches[cache_key] = {
                "name": cache.name,
                "created_at": datetime.now(),
                "ttl_minutes": Config.CACHE_TTL_MINUTES,
            }

            logger.info(f"Context cache created: {cache.name}")
            return cache.name

    except Exception as e:
        logger.warning(f"Failed to create context cache: {e}")
        return None


async def get_gemini_streaming_response(
    prompt: str,
    model_name: str,
    has_image: bool = False,
) -> tuple[str, str]:
    """
    Get streaming response from Gemini with retry logic and model fallback.

    Args:
        prompt: The prompt to send to Gemini
        model_name: The model to use
        has_image: Whether the request includes image data (uses image model)

    Returns:
        Tuple of (response text, model used)

    Raises:
        Exception: If all retries and fallbacks fail
    """
    # Determine which model to use
    if has_image:
        model_to_use = Config.GEMINI_MODEL_IMAGE
        fallback_model = None  # No fallback for image models
    else:
        model_to_use = model_name
        fallback_model = Config.GEMINI_MODEL_FALLBACK if model_name != Config.GEMINI_MODEL_FALLBACK else None

    # Try primary model
    try:
        return await _try_gemini_model(prompt, model_to_use)
    except Exception as e:
        logger.warning(f"Primary model {model_to_use} failed: {e}")

        # Try fallback if available
        if fallback_model:
            logger.info(f"Trying fallback model {fallback_model}")
            try:
                return await _try_gemini_model(prompt, fallback_model)
            except Exception as fallback_error:
                logger.error(f"Fallback model {fallback_model} also failed: {fallback_error}")
                raise
        else:
            raise


@retry(
    stop=stop_after_attempt(Config.MAX_RETRIES),
    wait=wait_exponential(
        min=Config.RETRY_MIN_WAIT,
        max=Config.RETRY_MAX_WAIT,
    ),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _try_gemini_model(prompt: str, model_name: str) -> tuple[str, str]:
    """
    Attempt to get a response from a specific Gemini model.

    Args:
        prompt: The prompt to send
        model_name: The model to use

    Returns:
        Tuple of (response text, model used)

    Raises:
        Exception: If the request fails after retries
    """
    try:
        # Reuse model instance from cache (thread-safe)
        async with _model_lock:
            if model_name not in _gemini_models:
                logger.info(f"Creating new model instance for {model_name}")
                _gemini_models[model_name] = genai.GenerativeModel(model_name)
            model = _gemini_models[model_name]

        # Configure generation parameters
        generation_config = genai.GenerationConfig(
            max_output_tokens=Config.MAX_TOKENS,
            temperature=Config.TEMPERATURE,
            top_p=Config.TOP_P,
            top_k=Config.TOP_K,
        )

        # Generate content with streaming
        logger.info(f"Sending request to {model_name}")
        response = await model.generate_content_async(
            prompt,
            generation_config=generation_config,
            stream=True,
        )

        # Collect streaming chunks
        full_response = []
        async for chunk in response:
            if chunk.text:
                full_response.append(chunk.text)
                logger.debug(f"Received chunk: {len(chunk.text)} chars")

        result = "".join(full_response)
        logger.info(f"Completed streaming response from {model_name}: {len(result)} chars")
        return result, model_name

    except Exception as e:
        logger.error(f"Error getting Gemini response from {model_name}: {e}")
        raise


# =============================================================================
# OpenAI Streaming Functions
# =============================================================================


async def get_openai_streaming_response(
    prompt: str,
    model_name: str,
) -> tuple[str, str]:
    """
    Get streaming response from OpenAI with retry logic and model fallback.

    Args:
        prompt: The prompt to send to OpenAI
        model_name: The model to use (e.g., gpt-5-codex, gpt-5.2)

    Returns:
        Tuple of (response text, model used)

    Raises:
        Exception: If all retries and fallbacks fail
    """
    if not _openai_client:
        raise ValueError("OpenAI API key not configured")

    # Determine fallback model based on primary
    fallback_model = Config.OPENAI_MODEL_FALLBACK

    # Try primary model
    try:
        return await _try_openai_model(prompt, model_name)
    except Exception as e:
        logger.warning(f"Primary OpenAI model {model_name} failed: {e}")

        # Try fallback if available
        if fallback_model and fallback_model != model_name:
            logger.info(f"Trying fallback model {fallback_model}")
            try:
                return await _try_openai_model(prompt, fallback_model)
            except Exception as fallback_error:
                logger.error(f"Fallback model {fallback_model} also failed: {fallback_error}")
                raise
        else:
            raise


@retry(
    stop=stop_after_attempt(Config.MAX_RETRIES),
    wait=wait_exponential(
        min=Config.RETRY_MIN_WAIT,
        max=Config.RETRY_MAX_WAIT,
    ),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _try_openai_model(prompt: str, model_name: str) -> tuple[str, str]:
    """
    Attempt to get a response from a specific OpenAI model.

    Supports both Chat Completions API and Responses API (for Codex models).

    Args:
        prompt: The prompt to send
        model_name: The model to use

    Returns:
        Tuple of (response text, model used)

    Raises:
        Exception: If the request fails after retries
    """
    if not _openai_client:
        raise ValueError("OpenAI API key not configured")

    try:
        logger.info(f"Sending request to OpenAI {model_name}")

        # Codex and o3 models use the Responses API
        uses_responses_api = any(x in model_name.lower() for x in ["codex", "o3"])

        if uses_responses_api:
            # Use Responses API for Codex models
            return await _try_openai_responses_api(prompt, model_name)
        else:
            # Use Chat Completions API for other models
            return await _try_openai_chat_api(prompt, model_name)

    except Exception as e:
        logger.error(f"Error getting OpenAI response from {model_name}: {e}")
        raise


async def _try_openai_chat_api(prompt: str, model_name: str) -> tuple[str, str]:
    """Use Chat Completions API for standard models."""
    # Newer models (gpt-5.x, o1, o3) use max_completion_tokens
    # Older models (gpt-4, gpt-4o, gpt-3.5) use max_tokens
    uses_new_tokens_param = any(x in model_name.lower() for x in ["gpt-5", "o1", "o3"])

    # Build request parameters
    request_params = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": Config.TEMPERATURE,
        "top_p": Config.TOP_P,
        "stream": True,
    }

    # Use appropriate token parameter based on model
    if uses_new_tokens_param:
        request_params["max_completion_tokens"] = Config.MAX_TOKENS
    else:
        request_params["max_tokens"] = Config.MAX_TOKENS

    # Generate content with streaming
    response = await _openai_client.chat.completions.create(**request_params)

    # Collect streaming chunks
    full_response = []
    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            full_response.append(content)
            logger.debug(f"Received chunk: {len(content)} chars")

    result = "".join(full_response)
    logger.info(f"Completed streaming response from {model_name}: {len(result)} chars")
    return result, model_name


async def _try_openai_responses_api(prompt: str, model_name: str) -> tuple[str, str]:
    """Use Responses API for Codex models."""
    logger.info(f"Using Responses API for {model_name}")

    # Responses API uses a different endpoint and format
    # Note: As of late 2024, this requires openai>=1.50.0
    response = await _openai_client.responses.create(
        model=model_name,
        input=prompt,
    )

    # Extract the output text from the Responses API format
    # Response structure: response.output is a list containing:
    #   - ResponseReasoningItem (content=None, has reasoning summary)
    #   - ResponseOutputMessage (content=[ResponseOutputText with .text])
    result = ""
    if response.output:
        for item in response.output:
            # Skip items without content or with None content
            if hasattr(item, 'content') and item.content is not None:
                for content_item in item.content:
                    if hasattr(content_item, 'text') and content_item.text:
                        result += content_item.text

    if not result:
        # Fallback: try to get any text representation
        result = str(response.output) if response.output else "No response generated"

    logger.info(f"Completed response from {model_name}: {len(result)} chars")
    return result, model_name


# =============================================================================
# Multi-Model Consultation Functions
# =============================================================================


async def get_single_model_response(
    prompt: str,
    model_key: str,
) -> Dict[str, Any]:
    """
    Get response from a single model by its key.

    Args:
        prompt: The prompt to send
        model_key: The model key from Config.AVAILABLE_MODELS

    Returns:
        Dict with response, model info, tokens, cost, and success status
    """
    model_info = Config.AVAILABLE_MODELS.get(model_key)
    if not model_info:
        return {
            "model_key": model_key,
            "success": False,
            "error": f"Unknown model key: {model_key}",
        }

    provider = model_info["provider"]
    model_id = model_info["model_id"]

    try:
        # Route to appropriate provider
        if provider == "gemini":
            if not Config.GEMINI_API_KEY:
                return {
                    "model_key": model_key,
                    "model_id": model_id,
                    "display_name": model_info["display_name"],
                    "success": False,
                    "error": "Gemini API key not configured",
                }
            response, model_used = await get_gemini_streaming_response(prompt, model_id)

        elif provider == "openai":
            if not Config.OPENAI_API_KEY:
                return {
                    "model_key": model_key,
                    "model_id": model_id,
                    "display_name": model_info["display_name"],
                    "success": False,
                    "error": "OpenAI API key not configured",
                }
            response, model_used = await get_openai_streaming_response(prompt, model_id)

        else:
            return {
                "model_key": model_key,
                "success": False,
                "error": f"Unknown provider: {provider}",
            }

        # Calculate tokens and cost
        input_tokens = len(prompt) // Config.CHARS_PER_TOKEN
        output_tokens = len(response) // Config.CHARS_PER_TOKEN
        pricing = Config.get_pricing(model_used)
        cost = (input_tokens / 1_000_000) * pricing["input"] + \
               (output_tokens / 1_000_000) * pricing["output"]

        return {
            "model_key": model_key,
            "model_id": model_used,
            "display_name": model_info["display_name"],
            "provider": provider,
            "response": response,
            "success": True,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            "cost": round(cost, 5),
        }

    except Exception as e:
        logger.error(f"Error getting response from {model_key}: {e}")
        return {
            "model_key": model_key,
            "model_id": model_id,
            "display_name": model_info["display_name"],
            "provider": provider,
            "success": False,
            "error": str(e),
        }


async def get_multi_model_responses(
    prompt: str,
    model_keys: List[str],
) -> Dict[str, Any]:
    """
    Get responses from multiple models in parallel.

    Args:
        prompt: The prompt to send to all models
        model_keys: List of model keys to consult

    Returns:
        Dict with responses from all models, summary, and total cost
    """
    if not model_keys:
        model_keys = Config.DEFAULT_MODELS

    # Filter to only available models
    available_keys = Config.get_available_model_keys()
    valid_keys = [k for k in model_keys if k in available_keys]
    invalid_keys = [k for k in model_keys if k not in available_keys]

    if not valid_keys:
        return {
            "success": False,
            "error": "No valid models available. Check API key configuration.",
            "invalid_models": invalid_keys,
        }

    # Run all model requests in parallel
    tasks = [get_single_model_response(prompt, key) for key in valid_keys]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    responses = []
    total_cost = 0.0
    successful_count = 0

    for result in results:
        if isinstance(result, Exception):
            responses.append({
                "success": False,
                "error": str(result),
            })
        else:
            responses.append(result)
            if result.get("success"):
                successful_count += 1
                total_cost += result.get("cost", 0)

    return {
        "success": successful_count > 0,
        "responses": responses,
        "models_consulted": len(valid_keys),
        "models_successful": successful_count,
        "invalid_models": invalid_keys if invalid_keys else None,
        "total_cost": round(total_cost, 5),
    }


# =============================================================================
# Agentic Tool Use Functions
# =============================================================================

# Map of available tools for Gemini to call
AVAILABLE_TOOLS = {
    "web_search": web_search,
    "fetch_url": fetch_url,
}

# Tool declarations for Gemini function calling
TOOL_DECLARATIONS = [
    WEB_SEARCH_DECLARATION,
    FETCH_URL_DECLARATION,
]


async def get_agentic_response(
    prompt: str,
    model_name: str,
    tools_enabled: list[str],
    max_tool_calls: int = 5,
) -> tuple[str, str, list[dict]]:
    """
    Get a response from Gemini with tool use (function calling) support.

    Gemini can call tools like web_search and fetch_url to gather information
    needed to answer the question. This function handles the tool call loop.

    Args:
        prompt: The prompt to send to Gemini
        model_name: The model to use
        tools_enabled: List of tool names Gemini can use
        max_tool_calls: Maximum number of tool calls in one turn (default: 5)

    Returns:
        Tuple of (response text, model used, list of tool calls made)
    """
    tool_calls_made = []

    # Filter tool declarations to only enabled tools
    enabled_declarations = [
        decl for decl in TOOL_DECLARATIONS
        if decl.name in tools_enabled
    ]

    if not enabled_declarations:
        # No tools enabled, fall back to regular response
        response, model_used = await get_gemini_streaming_response(prompt, model_name)
        return response, model_used, []

    try:
        # Get or create model with tool support
        async with _model_lock:
            tool_model_key = f"{model_name}_tools"
            if tool_model_key not in _gemini_models:
                logger.info(f"Creating tool-enabled model instance for {model_name}")
                _gemini_models[tool_model_key] = genai.GenerativeModel(
                    model_name,
                    tools=enabled_declarations,
                )
            model = _gemini_models[tool_model_key]

        generation_config = genai.GenerationConfig(
            max_output_tokens=Config.MAX_TOKENS,
            temperature=Config.TEMPERATURE,
            top_p=Config.TOP_P,
            top_k=Config.TOP_K,
        )

        # Start the conversation
        chat = model.start_chat()

        logger.info(f"Starting agentic request to {model_name} with tools: {tools_enabled}")

        # Initial request
        response = await chat.send_message_async(
            prompt,
            generation_config=generation_config,
        )

        # Tool call loop
        tool_call_count = 0
        while tool_call_count < max_tool_calls:
            # Check if Gemini wants to call a tool
            if not response.candidates or not response.candidates[0].content.parts:
                break

            function_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if hasattr(part, "function_call") and part.function_call.name
            ]

            if not function_calls:
                # No more tool calls, we have the final response
                break

            # Execute each function call
            function_responses = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args)

                logger.info(f"Gemini calling tool: {tool_name}({tool_args})")

                if tool_name in AVAILABLE_TOOLS and tool_name in tools_enabled:
                    try:
                        # Execute the tool
                        tool_func = AVAILABLE_TOOLS[tool_name]
                        result = await tool_func(**tool_args)

                        tool_calls_made.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "success": result.get("success", True),
                        })

                        # Create function response for Gemini
                        function_responses.append(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"result": str(result)},
                                )
                            )
                        )

                        logger.info(f"Tool {tool_name} executed successfully")

                    except Exception as e:
                        logger.error(f"Tool {tool_name} failed: {e}")
                        tool_calls_made.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "success": False,
                            "error": str(e),
                        })

                        function_responses.append(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"error": str(e)},
                                )
                            )
                        )
                else:
                    logger.warning(f"Tool {tool_name} not available or not enabled")
                    function_responses.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tool_name,
                                response={"error": f"Tool {tool_name} not available"},
                            )
                        )
                    )

                tool_call_count += 1

            # Send tool results back to Gemini
            if function_responses:
                response = await chat.send_message_async(
                    function_responses,
                    generation_config=generation_config,
                )

        # Extract final text response
        final_text = ""
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    final_text += part.text

        if not final_text:
            final_text = "I was unable to generate a response after using the available tools."

        logger.info(
            f"Agentic response complete: {len(final_text)} chars, "
            f"{len(tool_calls_made)} tool calls"
        )

        return final_text, model_name, tool_calls_made

    except Exception as e:
        logger.error(f"Agentic response failed: {e}")
        # Fall back to non-tool response
        try:
            response, model_used = await get_gemini_streaming_response(prompt, model_name)
            return response, model_used, []
        except Exception:
            raise e


@mcp.tool()
async def get_code_second_opinion(
    code: str,
    language: str,
    image_data: Optional[str] = None,
    context: str = "",
    error_messages: Optional[List[str]] = None,
    issue_description: str = "",
    verbosity: str = "detailed",
) -> dict:
    """
    Provides an LLM-powered second opinion on challenging coding issues.

    This tool analyzes code, identifies issues, and suggests improvements using
    Google Gemini. It provides comprehensive analysis including root cause,
    severity assessment, specific recommendations, alternative approaches,
    best practices, and security considerations.

    Uses Gemini 3 Pro Preview by default, with automatic fallback to Gemini 2.5 Pro
    if the primary model fails. For image/visual analysis (e.g., Playwright screenshots),
    uses Gemini 3 Pro Image Preview.

    Args:
        code: The code to review (required)
        language: Programming language of the code, e.g., "python", "javascript", "rust" (required)
        image_data: Base64 encoded image data for visual analysis (e.g., Playwright screenshots)
        context: Additional context about the code, such as what it's supposed to do
        error_messages: List of error messages you're encountering
        issue_description: Description of the specific issue or challenge you're facing
        verbosity: "brief" for quick feedback, "detailed" for comprehensive analysis (default: "detailed")

    Returns:
        dict with analysis, model_used, success status, token counts, cost estimate, and optional error

    Example:
        {
            "analysis": "# Root Cause Analysis\\n...",
            "model_used": "gemini-3-pro-preview",
            "success": true,
            "tokens_used": {"input": 2100, "output": 2207, "total": 4307},
            "cost_estimate": 0.027,
            "error": null
        }
    """
    try:
        # Handle mutable default argument
        if error_messages is None:
            error_messages = []

        # Determine if we have image data
        has_image = bool(image_data)

        logger.info(f"Received code review request for {language}, verbosity={verbosity}, has_image={has_image}")

        # Scan for potential secrets before sending to API
        potential_secrets = scan_for_secrets(code)
        if potential_secrets:
            logger.warning(f"Potential secrets detected in code: {', '.join(potential_secrets)}")
            # Note: We still proceed but log the warning for security audit

        # Build the prompt with verbosity control
        prompt = build_code_review_prompt(
            code=code,
            language=language,
            context=context if context else None,
            error_messages=error_messages if error_messages else None,
            issue_description=issue_description if issue_description else None,
            verbosity=verbosity,
        )

        # Estimate input tokens using configured chars-per-token ratio
        input_tokens = len(prompt) // Config.CHARS_PER_TOKEN

        # Get streaming response from Gemini with fallback support
        analysis, model_used = await get_gemini_streaming_response(
            prompt,
            model_name=Config.GEMINI_MODEL_PRIMARY,
            has_image=has_image,
        )

        # Estimate output tokens and cost
        output_tokens = len(analysis) // Config.CHARS_PER_TOKEN
        total_tokens = input_tokens + output_tokens

        # Calculate cost using configured pricing for the model used
        pricing = Config.GEMINI_PRICING.get(
            model_used,
            Config.GEMINI_PRICING.get(Config.GEMINI_MODEL_PRIMARY)
        )
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        return {
            "analysis": analysis,
            "model_used": model_used,
            "success": True,
            "tokens_used": {
                "input": input_tokens,
                "output": output_tokens,
                "total": total_tokens,
            },
            "cost_estimate": round(total_cost, 5),
            "error": None,
        }

    except Exception as e:
        error_msg = f"Failed to get second opinion: {str(e)}"
        logger.error(error_msg)
        return {
            "analysis": "",
            "model_used": "none",
            "success": False,
            "tokens_used": {"input": 0, "output": 0, "total": 0},
            "cost_estimate": 0.0,
            "error": error_msg,
        }


@mcp.tool()
async def health_check() -> dict:
    """
    Check if the MCP server and all LLM APIs are properly configured.

    Returns:
        dict with server status, configuration status, and version info
    """
    has_gemini = bool(Config.GEMINI_API_KEY)
    has_openai = bool(Config.OPENAI_API_KEY)
    available_models = Config.get_available_model_keys()

    status = {
        "server_name": Config.SERVER_NAME,
        "server_version": Config.SERVER_VERSION,
        "status": "healthy" if (has_gemini or has_openai) else "no_api_keys",
        # Gemini
        "gemini_configured": has_gemini,
        "gemini_models": {
            "primary": Config.GEMINI_MODEL_PRIMARY,
            "fallback": Config.GEMINI_MODEL_FALLBACK,
            "image": Config.GEMINI_MODEL_IMAGE,
        } if has_gemini else None,
        # OpenAI
        "openai_configured": has_openai,
        "openai_models": {
            "codex": Config.OPENAI_MODEL_CODEX,
            "codex_max": Config.OPENAI_MODEL_CODEX_MAX,
            "codex_mini": Config.OPENAI_MODEL_CODEX_MINI,
            "gpt52": Config.OPENAI_MODEL_GPT52,
            "gpt52_mini": Config.OPENAI_MODEL_GPT52_MINI,
        } if has_openai else None,
        # Available models for multi-model consultation
        "available_models": available_models,
        "default_models": Config.DEFAULT_MODELS,
    }

    messages = []
    if not has_gemini:
        messages.append(
            "GEMINI_API_KEY not set - Gemini models unavailable. "
            "Get key from https://aistudio.google.com/apikey"
        )
    if not has_openai:
        messages.append(
            "OPENAI_API_KEY not set - OpenAI/Codex models unavailable. "
            "Get key from https://platform.openai.com/api-keys"
        )

    if messages:
        status["messages"] = messages

    return status


@mcp.tool()
async def list_available_models() -> dict:
    """
    List all available models for second opinion consultation.

    Returns a list of models with their keys, display names, descriptions,
    and whether they're currently available (API key configured).

    Use this to see which models you can select for get_multi_model_second_opinion.

    Returns:
        dict with available_models list and configuration status

    Example:
        {
            "available_models": [
                {
                    "key": "gemini-3-pro",
                    "display_name": "Gemini 3 Pro",
                    "provider": "gemini",
                    "description": "Google's latest, best for comprehensive analysis",
                    "available": true
                },
                {
                    "key": "codex",
                    "display_name": "GPT-5 Codex",
                    "provider": "openai",
                    "description": "Optimized for code generation and review",
                    "available": true
                },
                ...
            ],
            "default_models": ["gemini-3-pro", "codex"]
        }
    """
    available_keys = Config.get_available_model_keys()

    models = []
    for key, info in Config.AVAILABLE_MODELS.items():
        models.append({
            "key": key,
            "display_name": info["display_name"],
            "provider": info["provider"],
            "model_id": info["model_id"],
            "description": info["description"],
            "available": key in available_keys,
        })

    return {
        "available_models": models,
        "default_models": Config.DEFAULT_MODELS,
        "gemini_configured": bool(Config.GEMINI_API_KEY),
        "openai_configured": bool(Config.OPENAI_API_KEY),
    }


@mcp.tool()
async def get_multi_model_second_opinion(
    code: str,
    language: str,
    models: List[str],
    context: str = "",
    error_messages: Optional[List[str]] = None,
    issue_description: str = "",
    verbosity: str = "detailed",
) -> dict:
    """
    Get code review opinions from multiple LLM models in parallel.

    This tool allows you to consult multiple models simultaneously and compare
    their analyses. Select 2 or more models to get diverse perspectives on your code.

    Available models (use list_available_models to see current availability):
    - Gemini: "gemini-3-pro", "gemini-2.5-pro"
    - OpenAI Codex: "codex", "codex-max", "codex-mini"
    - OpenAI GPT-5.2: "gpt-5.2", "gpt-5.2-mini"

    Args:
        code: The code to review (required)
        language: Programming language, e.g., "python", "javascript", "rust" (required)
        models: List of model keys to consult, e.g., ["gemini-3-pro", "codex", "gpt-5.2"]
        context: Additional context about the code
        error_messages: List of error messages you're encountering
        issue_description: Description of the specific issue
        verbosity: "brief" for quick feedback, "detailed" for comprehensive analysis

    Returns:
        dict with responses from each model, comparison summary, and total cost

    Example:
        {
            "success": true,
            "responses": [
                {
                    "model_key": "gemini-3-pro",
                    "display_name": "Gemini 3 Pro",
                    "response": "# Analysis\\n...",
                    "success": true,
                    "tokens": {...},
                    "cost": 0.012
                },
                {
                    "model_key": "codex",
                    "display_name": "GPT-5 Codex",
                    "response": "# Analysis\\n...",
                    "success": true,
                    "tokens": {...},
                    "cost": 0.025
                }
            ],
            "models_consulted": 2,
            "models_successful": 2,
            "total_cost": 0.037
        }
    """
    try:
        # Validate we have at least 1 model (preferably 2+)
        if not models:
            return {
                "success": False,
                "error": "No models specified. Use list_available_models to see options.",
            }

        if len(models) < 2:
            logger.warning("Only 1 model selected - consider using 2+ for comparison")

        # Handle mutable default argument
        if error_messages is None:
            error_messages = []

        logger.info(f"Multi-model code review for {language}, models={models}, verbosity={verbosity}")

        # Scan for potential secrets before sending to API
        potential_secrets = scan_for_secrets(code)
        if potential_secrets:
            logger.warning(f"Potential secrets detected in code: {', '.join(potential_secrets)}")

        # Build the prompt
        prompt = build_code_review_prompt(
            code=code,
            language=language,
            context=context if context else None,
            error_messages=error_messages if error_messages else None,
            issue_description=issue_description if issue_description else None,
            verbosity=verbosity,
        )

        # Get responses from all models in parallel
        result = await get_multi_model_responses(prompt, models)

        return result

    except Exception as e:
        error_msg = f"Failed to get multi-model second opinion: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
        }


# =============================================================================
# Session Management Tools (Multi-turn Conversations)
# =============================================================================


@mcp.tool()
async def create_session(
    purpose: str = "code_review",
    max_turns: int = 10,
    cost_limit: float = 0.50,
    tools_enabled: Optional[List[str]] = None,
) -> dict:
    """
    Create a new consultation session with Gemini for multi-turn conversations.

    Sessions allow you to have back-and-forth discussions with Gemini,
    maintaining conversation history and tracking costs.

    Args:
        purpose: Session type - "code_review", "architecture", "debugging", or "brainstorm"
        max_turns: Maximum conversation turns (default: 10)
        cost_limit: Maximum spend for this session in dollars (default: $0.50)
        tools_enabled: List of tools Gemini can use (default: ["web_search", "fetch_url"])

    Returns:
        dict with session_id, purpose, limits, tools_available, and status

    Example:
        {
            "session_id": "uuid-xxx",
            "purpose": "code_review",
            "max_turns": 10,
            "cost_limit": 0.50,
            "tools_available": ["web_search", "fetch_url"],
            "created_at": "2025-01-25T...",
            "status": "active"
        }
    """
    try:
        manager = get_session_manager()

        if tools_enabled is None:
            tools_enabled = ["web_search", "fetch_url"]

        session = await manager.create(
            purpose=purpose,
            max_turns=max_turns,
            cost_limit=cost_limit,
            tools_enabled=tools_enabled,
        )

        return {
            "session_id": session.id,
            "purpose": session.purpose,
            "max_turns": session.max_turns,
            "cost_limit": session.cost_limit,
            "tools_available": session.tools_enabled,
            "created_at": session.created_at.isoformat(),
            "status": session.status,
        }

    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        return {
            "session_id": None,
            "error": str(e),
            "status": "failed",
        }


@mcp.tool()
async def consult(
    session_id: str,
    message: str,
    code: Optional[str] = None,
    language: Optional[str] = None,
) -> dict:
    """
    Send a message to Gemini within an existing session.

    Maintains conversation history for context. Use this for follow-up questions,
    clarifications, or iterative problem-solving.

    Args:
        session_id: Session ID from create_session
        message: Your message or question to Gemini
        code: Optional code snippet to discuss (if any)
        language: Programming language of the code (if provided)

    Returns:
        dict with response, tool_calls_made, turn info, and cost tracking

    Example:
        {
            "response": "Based on our discussion...",
            "tool_calls_made": [],
            "turn_number": 3,
            "session_cost_so_far": 0.12,
            "tokens_this_turn": {"input": 1500, "output": 800},
            "remaining_turns": 7,
            "remaining_budget": 0.38,
            "warning": false
        }
    """
    try:
        manager = get_session_manager()
        session = await manager.get(session_id)

        if not session:
            return {
                "response": "",
                "error": f"Session {session_id} not found",
                "success": False,
            }

        if not session.can_continue():
            return {
                "response": "",
                "error": f"Session cannot continue. Status: {session.status}",
                "success": False,
                "session_cost_so_far": session.total_cost,
                "remaining_turns": session.remaining_turns,
                "remaining_budget": session.remaining_budget,
            }

        # Build the prompt with context
        history_context = ""
        for msg in session.messages:
            role_label = "You" if msg.role == "user" else "Gemini"
            history_context += f"\n{role_label}: {msg.content[:500]}...\n" if len(msg.content) > 500 else f"\n{role_label}: {msg.content}\n"

        prompt_parts = [
            f"This is turn {session.turn_count + 1} in a {session.purpose} session.",
            "",
            "Previous conversation:" if history_context else "",
            history_context,
            "",
            "Current message from user:",
            message,
        ]

        if code and language:
            prompt_parts.extend([
                "",
                f"Code ({language}):",
                f"```{language}",
                code,
                "```",
            ])

        prompt = "\n".join(prompt_parts)

        # Add user message to session
        await manager.add_message(session_id, "user", message)

        # Get response from Gemini (with tool use if enabled)
        input_tokens = len(prompt) // Config.CHARS_PER_TOKEN

        # Use agentic response if tools are enabled for this session
        if session.tools_enabled:
            analysis, model_used, tool_calls = await get_agentic_response(
                prompt,
                model_name=Config.GEMINI_MODEL_PRIMARY,
                tools_enabled=session.tools_enabled,
            )
        else:
            analysis, model_used = await get_gemini_streaming_response(
                prompt,
                model_name=Config.GEMINI_MODEL_PRIMARY,
            )
            tool_calls = []

        output_tokens = len(analysis) // Config.CHARS_PER_TOKEN

        # Calculate cost
        pricing = Config.GEMINI_PRICING.get(
            model_used,
            Config.GEMINI_PRICING.get(Config.GEMINI_MODEL_PRIMARY)
        )
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        turn_cost = input_cost + output_cost

        # Add assistant response to session
        await manager.add_message(
            session_id,
            "assistant",
            analysis,
            tool_calls=tool_calls if tool_calls else None,
            tokens={"input": input_tokens, "output": output_tokens},
            cost=turn_cost,
        )

        # Refresh session to get updated stats
        session = await manager.get(session_id)

        return {
            "response": analysis,
            "model_used": model_used,
            "tool_calls_made": tool_calls,
            "turn_number": session.turn_count,
            "session_cost_so_far": round(session.total_cost, 5),
            "tokens_this_turn": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            "remaining_turns": session.remaining_turns,
            "remaining_budget": round(session.remaining_budget, 5),
            "warning": session.should_warn(),
            "success": True,
        }

    except Exception as e:
        logger.error(f"Consult failed: {e}")
        return {
            "response": "",
            "error": str(e),
            "success": False,
        }


@mcp.tool()
async def get_session_history(
    session_id: str,
    include_tool_calls: bool = True,
) -> dict:
    """
    Get the full conversation history for a session.

    Useful for reviewing what was discussed or resuming a conversation.

    Args:
        session_id: Session ID to retrieve history for
        include_tool_calls: Whether to include tool call details (default: True)

    Returns:
        dict with session info and message history
    """
    try:
        manager = get_session_manager()
        session = await manager.get(session_id)

        if not session:
            return {
                "error": f"Session {session_id} not found",
                "success": False,
            }

        history = await manager.get_history(session_id, include_tool_calls)

        return {
            "session_id": session_id,
            "purpose": session.purpose,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "turn_count": session.turn_count,
            "total_cost": round(session.total_cost, 5),
            "messages": history,
            "success": True,
        }

    except Exception as e:
        logger.error(f"Failed to get session history: {e}")
        return {
            "error": str(e),
            "success": False,
        }


@mcp.tool()
async def close_session(
    session_id: str,
    generate_summary: bool = True,
) -> dict:
    """
    Close a session and get a detailed cost breakdown.

    Optionally generates a summary of the key findings from the conversation.

    Args:
        session_id: Session ID to close
        generate_summary: Whether to generate a summary of key findings (default: True)

    Returns:
        dict with session summary, token breakdown, and detailed cost analysis

    Example:
        {
            "session_id": "uuid-xxx",
            "total_turns": 5,
            "duration_minutes": 12.5,
            "status": "closed",
            "tokens": {...},
            "cost": {...},
            "summary": "Key findings: ..."
        }
    """
    try:
        manager = get_session_manager()
        session = await manager.get(session_id)

        if not session:
            return {
                "error": f"Session {session_id} not found",
                "success": False,
            }

        # Generate summary if requested
        summary = None
        summary_cost = 0.0

        if generate_summary and session.messages:
            # Build summary prompt from conversation
            conversation_text = "\n".join([
                f"{'User' if m.role == 'user' else 'Assistant'}: {m.content[:300]}..."
                if len(m.content) > 300 else f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}"
                for m in session.messages
            ])

            summary_prompt = f"""Summarize the key findings and conclusions from this {session.purpose} session in 2-3 bullet points:

{conversation_text}

Provide a concise summary focusing on:
1. Main issues identified
2. Recommended solutions
3. Key decisions made"""

            try:
                summary_response, _ = await get_gemini_streaming_response(
                    summary_prompt,
                    model_name=Config.GEMINI_MODEL_PRIMARY,
                )
                summary = summary_response

                # Calculate summary cost
                summary_input = len(summary_prompt) // Config.CHARS_PER_TOKEN
                summary_output = len(summary_response) // Config.CHARS_PER_TOKEN
                pricing = Config.GEMINI_PRICING.get(Config.GEMINI_MODEL_PRIMARY)
                summary_cost = (summary_input / 1_000_000) * pricing["input"] + (summary_output / 1_000_000) * pricing["output"]
            except Exception as e:
                logger.warning(f"Failed to generate summary: {e}")
                summary = "Summary generation failed"

        # Close the session
        session = await manager.close(session_id, summary)

        # Calculate duration
        duration_minutes = (datetime.now() - session.created_at).total_seconds() / 60

        # Build per-turn breakdown and count tool calls
        turns_breakdown = []
        total_tool_calls = 0
        tool_call_summary = {}

        for i, msg in enumerate(session.messages):
            if msg.role == "user":
                # Find the corresponding assistant response
                assistant_msg = session.messages[i + 1] if i + 1 < len(session.messages) else None
                if assistant_msg and assistant_msg.role == "assistant":
                    turn_tool_calls = len(assistant_msg.tool_calls) if assistant_msg.tool_calls else 0
                    turns_breakdown.append({
                        "turn": len(turns_breakdown) + 1,
                        "input": assistant_msg.tokens.get("input", 0) if assistant_msg.tokens else 0,
                        "output": assistant_msg.tokens.get("output", 0) if assistant_msg.tokens else 0,
                        "cost": round(assistant_msg.cost, 5),
                        "tool_calls": turn_tool_calls,
                    })
                    total_tool_calls += turn_tool_calls

                    # Count by tool name
                    if assistant_msg.tool_calls:
                        for tc in assistant_msg.tool_calls:
                            tool_name = tc.get("tool", "unknown")
                            tool_call_summary[tool_name] = tool_call_summary.get(tool_name, 0) + 1

        # Get pricing info for the model used
        pricing = Config.GEMINI_PRICING.get(Config.GEMINI_MODEL_PRIMARY)

        total_cost = session.total_cost + summary_cost

        return {
            "session_id": session.id,
            "total_turns": session.turn_count,
            "duration_minutes": round(duration_minutes, 1),
            "status": session.status,

            "tokens": {
                "input": session.total_input_tokens,
                "output": session.total_output_tokens,
                "total": session.total_tokens,
                "by_turn": turns_breakdown,
            },

            "cost": {
                "conversation_cost": round(session.total_cost, 5),
                "summary_cost": round(summary_cost, 5),
                "total_cost": round(total_cost, 5),
                "model_used": Config.GEMINI_MODEL_PRIMARY,
                "pricing": {
                    "input_per_million": pricing["input"],
                    "output_per_million": pricing["output"],
                },
            },

            "tool_usage": {
                "total_tool_calls": total_tool_calls,
                "by_tool": tool_call_summary,
                "tools_enabled": session.tools_enabled,
            },

            "summary": summary,

            "budget_used": f"{session.budget_used_percent:.1f}%",
            "turns_used": f"{session.turns_used_percent:.1f}%",
            "success": True,
        }

    except Exception as e:
        logger.error(f"Failed to close session: {e}")
        return {
            "error": str(e),
            "success": False,
        }


@mcp.tool()
async def list_sessions(
    status: str = "all",
    limit: int = 10,
) -> dict:
    """
    List recent consultation sessions.

    Args:
        status: Filter by status - "active", "closed", or "all" (default: "all")
        limit: Maximum number of sessions to return (default: 10)

    Returns:
        dict with list of sessions and daily usage stats
    """
    try:
        manager = get_session_manager()
        sessions = await manager.list_sessions(status=status, limit=limit)

        sessions_list = [
            {
                "session_id": s.id,
                "purpose": s.purpose,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "turn_count": s.turn_count,
                "total_cost": round(s.total_cost, 5),
            }
            for s in sessions
        ]

        daily_stats = manager.get_daily_stats()

        return {
            "sessions": sessions_list,
            "count": len(sessions_list),
            "daily_stats": daily_stats,
            "success": True,
        }

    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        return {
            "error": str(e),
            "success": False,
        }


# =============================================================================
# Domain Approval Tools (SSRF Protection for fetch_url)
# =============================================================================


@mcp.tool()
async def approve_fetch_domain(domain: str) -> dict:
    """
    Approve a domain for URL fetching within this server session.

    When Gemini's fetch_url tool encounters an unknown domain (not in the
    auto-approved list), it returns needs_approval=True. Use this tool to
    approve the domain, then retry the fetch_url call.

    The approval lasts for the duration of the server session (until restart).
    Auto-approved domains (like github.com, docs.python.org) don't need approval.

    Args:
        domain: The domain to approve (e.g., "example.com", "api.service.io")

    Returns:
        dict with approval status, domain, and list of currently approved domains

    Example:
        {
            "approved": true,
            "domain": "mysite.com",
            "message": "Domain 'mysite.com' approved for this session",
            "session_approved_domains": ["mysite.com", "other.com"]
        }
    """
    try:
        # Validate domain format (basic check)
        domain = domain.lower().strip()
        if not domain or " " in domain or "/" in domain:
            return {
                "approved": False,
                "domain": domain,
                "error": "Invalid domain format. Provide just the domain (e.g., 'example.com')",
            }

        # Block attempts to approve internal domains
        if domain in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return {
                "approved": False,
                "domain": domain,
                "error": "Cannot approve localhost or internal IP addresses",
            }

        if domain.endswith(".local") or domain.endswith(".internal"):
            return {
                "approved": False,
                "domain": domain,
                "error": "Cannot approve internal hostnames (.local, .internal)",
            }

        was_new = approve_domain(domain)

        return {
            "approved": True,
            "domain": domain,
            "was_new": was_new,
            "message": f"Domain '{domain}' approved for this session" if was_new else f"Domain '{domain}' was already approved",
            "session_approved_domains": get_approved_domains(),
        }

    except Exception as e:
        logger.error(f"Failed to approve domain: {e}")
        return {
            "approved": False,
            "domain": domain,
            "error": str(e),
        }


@mcp.tool()
async def revoke_fetch_domain(domain: str) -> dict:
    """
    Revoke approval for a previously approved domain.

    This removes a domain from the session-approved list, meaning future
    fetch_url calls to that domain will require re-approval.

    Args:
        domain: The domain to revoke (e.g., "example.com")

    Returns:
        dict with revocation status and updated domain list
    """
    try:
        domain = domain.lower().strip()
        was_approved = revoke_domain(domain)

        return {
            "revoked": was_approved,
            "domain": domain,
            "message": f"Domain '{domain}' revoked" if was_approved else f"Domain '{domain}' was not in the approved list",
            "session_approved_domains": get_approved_domains(),
        }

    except Exception as e:
        logger.error(f"Failed to revoke domain: {e}")
        return {
            "revoked": False,
            "domain": domain,
            "error": str(e),
        }


@mcp.tool()
async def list_fetch_domains() -> dict:
    """
    List all approved domains for URL fetching.

    Shows both the auto-approved domains (configured in the server) and
    session-approved domains (approved by the user during this session).

    Returns:
        dict with auto_approved_domains, session_approved_domains, and total count
    """
    try:
        return {
            "auto_approved_domains": Config.FETCH_URL_AUTO_APPROVED_DOMAINS,
            "session_approved_domains": get_approved_domains(),
            "require_approval_for_unknown": Config.FETCH_URL_REQUIRE_APPROVAL,
            "total_auto_approved": len(Config.FETCH_URL_AUTO_APPROVED_DOMAINS),
            "total_session_approved": len(get_approved_domains()),
            "success": True,
        }

    except Exception as e:
        logger.error(f"Failed to list domains: {e}")
        return {
            "error": str(e),
            "success": False,
        }


def main():
    """Main entry point for the MCP server."""
    logger.info(f"Starting {Config.SERVER_NAME} v{Config.SERVER_VERSION}")
    logger.info(f"Transport: SSE on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
    logger.info(f"Context caching: {'enabled' if Config.ENABLE_CONTEXT_CACHING else 'disabled'}")

    if not Config.GEMINI_API_KEY:
        logger.warning(
            "GEMINI_API_KEY not set. "
            "Server will start but requests will fail. "
            "Get your API key from https://aistudio.google.com/apikey"
        )

    # Run the MCP server with SSE transport
    # This keeps the server running continuously, eliminating cold starts
    mcp.run(
        transport="sse",
        host=Config.SERVER_HOST,
        port=Config.SERVER_PORT,
    )


if __name__ == "__main__":
    main()
