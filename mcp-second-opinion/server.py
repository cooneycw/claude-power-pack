#!/usr/bin/env python3
"""
Second Opinion MCP Server

An MCP server that provides LLM-powered second opinions on challenging coding issues.
Powered by Google Gemini with streaming support.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from fastmcp import FastMCP
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import Config
from prompts import build_code_review_prompt, scan_for_secrets

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
    logger.warning("GEMINI_API_KEY not set - server will fail on requests")

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
    Check if the MCP server and Gemini API are properly configured.

    Returns:
        dict with server status, configuration status, and version info
    """
    status = {
        "server_name": Config.SERVER_NAME,
        "server_version": Config.SERVER_VERSION,
        "gemini_configured": bool(Config.GEMINI_API_KEY),
        "gemini_model_primary": Config.GEMINI_MODEL_PRIMARY,
        "gemini_model_fallback": Config.GEMINI_MODEL_FALLBACK,
        "gemini_model_image": Config.GEMINI_MODEL_IMAGE,
        "status": "healthy" if Config.GEMINI_API_KEY else "api_key_missing",
    }

    if not Config.GEMINI_API_KEY:
        status["message"] = (
            "GEMINI_API_KEY environment variable is not set. "
            "Get your API key from https://aistudio.google.com/apikey"
        )

    return status


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
