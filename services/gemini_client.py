"""
gemini_client.py

Defines the GeminiClient class: handles all communication with the
Google Gemini API.

This is the ONLY place in the app that should talk to Gemini. It
provides one simple method -- generate_text() -- that sends a prompt
and returns the generated text (or a clear error), so the rest of the
app never has to deal with the Gemini SDK directly.

No Streamlit code, no Open Library code, and no JSON/file-storage code
belongs in this file. Its only job is: take a prompt, call Gemini,
hand back the result.
"""

import os
from typing import Optional

from google import genai


class GeminiClient:
    """
    A small wrapper around the Gemini API for generating text from a
    prompt.

    The API key is never hard-coded in this file. Instead, it is
    either passed in directly when creating a GeminiClient, or read
    from the GEMINI_API_KEY environment variable. This keeps secrets
    out of your source code (and out of anything you might commit to
    Git).
    """

    DEFAULT_MODEL_NAME = "gemini-3.6-flash"

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None) -> None:
        """
        Create a GeminiClient.

        Args:
            api_key: Your Gemini API key. If not provided, this will
                fall back to reading the GEMINI_API_KEY environment
                variable instead.
            model_name: Which Gemini model to use. If not provided,
                DEFAULT_MODEL_NAME is used.

        Raises:
            ValueError: if no API key was provided AND none was found
                in the environment. This fails fast and loudly at
                setup time, rather than failing confusingly later when
                you try to generate text.
        """
        resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not resolved_api_key:
            raise ValueError(
                "No Gemini API key was provided. Either pass api_key= "
                "directly, or set the GEMINI_API_KEY environment variable "
                "(for example, in a .env file loaded with python-dotenv)."
            )

        self.model_name: str = model_name or self.DEFAULT_MODEL_NAME

        self._client = genai.Client(api_key=resolved_api_key)

    def generate_text(self, prompt: str) -> dict:
        """
        Send `prompt` to Gemini and return the generated text.

        Rather than raising an exception on failure (which would force
        every caller to wrap every call in try/except), this method
        always returns a dictionary describing what happened:

            {"success": True,  "text": "...",  "error": None}
            {"success": False, "text": None,   "error": "some message"}

        This makes it easy for calling code (like the Streamlit UI) to
        check result["success"] and show either the text or a friendly
        error message, without needing to know anything about Gemini's
        specific exception types.
        """
        if not prompt or not prompt.strip():
            return {
                "success": False,
                "text": None,
                "error": "Cannot generate text from an empty prompt.",
            }

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )

            generated_text = getattr(response, "text", None)

            if not generated_text:
                return {
                    "success": False,
                    "text": None,
                    "error": "Gemini returned an empty response. It may have "
                             "been blocked or filtered.",
                }

            return {
                "success": True,
                "text": generated_text,
                "error": None,
            }

        except Exception as error:
            error_message = str(error)

            if "API key" in error_message or "API_KEY" in error_message:
                friendly_error = "Gemini rejected the API key. Double-check GEMINI_API_KEY."
            elif "quota" in error_message.lower() or "rate" in error_message.lower():
                friendly_error = "Gemini rate limit or quota was exceeded. Try again shortly."
            else:
                friendly_error = f"Gemini request failed: {error_message}"

            return {
                "success": False,
                "text": None,
                "error": friendly_error,
            }


if __name__ == "__main__":

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key_from_env = os.getenv("GEMINI_API_KEY")

    if not api_key_from_env:
        print("GEMINI_API_KEY is not set, so this test cannot call the real API.")
        print()
        print("To fix this:")
        print("  1. Get a Gemini API key from https://aistudio.google.com/apikey")
        print("  2. Create a file named .env in your project root (if you don't")
        print("     already have one) containing this line:")
        print("         GEMINI_API_KEY=your-actual-key-here")
        print("  3. Run this test again.")
    else:
        print(f"Found GEMINI_API_KEY in the environment (starts with "
              f"{api_key_from_env[:4]}...). Sending a test prompt to Gemini...")

        client = GeminiClient()

        result = client.generate_text(
            "In two sentences, explain what a personal reading list app does."
        )

        print()
        if result["success"]:
            print("Success! Gemini responded:")
            print(result["text"])
        else:
            print("Gemini call failed:")
            print(result["error"])

        print()
        print("--- Testing the empty-prompt guard ---")
        empty_result = client.generate_text("")
        print(empty_result)

        print()
        print("--- Testing GeminiClient() with no key at all (expected: ValueError) ---")
        real_key = os.environ.pop("GEMINI_API_KEY")
        try:
            GeminiClient()
        except ValueError as error:
            print("Got the expected error:", error)
        finally:
            os.environ["GEMINI_API_KEY"] = real_key