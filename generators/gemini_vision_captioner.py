"""
Gemini Vision Captioner
Standalone utility for generating image captions using Gemini Flash 2.0 vision capabilities
No hwtgenielib dependencies - uses google.genai directly (NEW SDK)
"""

import os
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types


def load_api_key() -> str:
    """
    Load Gemini API key from environment

    Returns:
        API key string

    Raises:
        ValueError: If GEMINI_API_KEY not found
    """
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found in environment. "
            "Please add it to your .env file."
        )
    return api_key


def caption_image_with_gemini(
    image_path: str,
    model: str = "gemini-2.0-flash-exp",
    custom_prompt: Optional[str] = None,
    timeout: int = 30
) -> Optional[str]:
    """
    Generate descriptive caption for image using Gemini vision

    Args:
        image_path: Path to image file (PNG, JPG, etc.)
        model: Gemini model name (must support vision)
               Supported models: gemini-2.0-flash-exp, gemini-1.5-pro, etc.
        custom_prompt: Optional custom prompt for caption generation
                      If None, uses default descriptive prompt
        timeout: Timeout in seconds for API call

    Returns:
        Generated caption string, or None on error

    Example:
        >>> caption = caption_image_with_gemini(
        ...     image_path="document_image_1.png",
        ...     model="gemini-2.0-flash-exp"
        ... )
        >>> print(caption)
        "A detailed diagram showing the architecture of a neural network..."
    """
    try:
        # Load API key and configure Gemini client
        api_key = load_api_key()
        client = genai.Client(api_key=api_key)

        # Load image using PIL
        from PIL import Image
        img = Image.open(image_path)

        # Prepare prompt
        if custom_prompt is None:
            # Default prompt for descriptive, factual captions
            prompt = (
                "Describe this image concisely in 1-2 sentences. "
                "Focus on the main subject, key details, and context. "
                "Be specific and factual."
            )
        else:
            prompt = custom_prompt

        # Generate caption with Gemini vision using new SDK
        response = client.models.generate_content(
            model=model,
            contents=[prompt, img],
            config=types.GenerateContentConfig(
                temperature=0.3,  # Lower temperature for factual descriptions
                max_output_tokens=150  # Concise captions
            )
        )

        # Extract and return caption text
        caption = response.text.strip()
        return caption if caption else None

    except FileNotFoundError:
        print(f"    ⚠️  Image file not found: {image_path}")
        return None

    except ValueError as e:
        # API key error or configuration error
        print(f"    ⚠️  Configuration error: {e}")
        return None

    except Exception as e:
        # Catch all other errors (network, timeout, model errors, etc.)
        print(f"    ⚠️  Caption generation failed: {e}")
        return None


def caption_images_batch(
    image_paths: list[str],
    model: str = "gemini-2.0-flash-exp",
    custom_prompt: Optional[str] = None,
    timeout: int = 30
) -> dict[str, Optional[str]]:
    """
    Generate captions for multiple images

    Args:
        image_paths: List of image file paths
        model: Gemini model name
        custom_prompt: Optional custom prompt
        timeout: Timeout per image

    Returns:
        Dictionary mapping image_path -> caption (or None on error)

    Example:
        >>> captions = caption_images_batch([
        ...     "image1.png",
        ...     "image2.png"
        ... ])
        >>> print(captions)
        {
            "image1.png": "A landscape photo...",
            "image2.png": "A close-up of..."
        }
    """
    results = {}

    for image_path in image_paths:
        caption = caption_image_with_gemini(
            image_path=image_path,
            model=model,
            custom_prompt=custom_prompt,
            timeout=timeout
        )
        results[image_path] = caption

    return results


# Default prompt templates for different use cases
DEFAULT_PROMPTS = {
    "descriptive": (
        "Describe this image concisely in 1-2 sentences. "
        "Focus on the main subject, key details, and context. "
        "Be specific and factual."
    ),
    "detailed": (
        "Provide a detailed description of this image. "
        "Include information about objects, people, setting, colors, mood, "
        "and any text visible in the image."
    ),
    "concise": (
        "Describe this image in one sentence. "
        "Focus only on the most important element."
    ),
    "technical": (
        "Describe this image from a technical perspective. "
        "Identify any diagrams, charts, tables, or technical content. "
        "Mention specific technical details visible."
    ),
    "dnd_campaign": (
        "Describe this image in the context of a D&D campaign. "
        "What might players see? What details would a dungeon master emphasize? "
        "Focus on atmosphere and story elements."
    )
}


def get_prompt_template(template_name: str = "descriptive") -> str:
    """
    Get a predefined prompt template

    Args:
        template_name: Name of template (descriptive, detailed, concise, technical, dnd_campaign)

    Returns:
        Prompt template string

    Example:
        >>> prompt = get_prompt_template("detailed")
        >>> caption = caption_image_with_gemini(
        ...     "image.png",
        ...     custom_prompt=prompt
        ... )
    """
    return DEFAULT_PROMPTS.get(template_name, DEFAULT_PROMPTS["descriptive"])
