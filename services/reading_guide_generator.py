"""
reading_guide_generator.py

Defines the ReadingGuideGenerator class: builds AI-generated reading
guides (a summary, a suggested reading level, and discussion
questions) for a Book, using GeminiClient, and saves/loads those
guides to a local JSON file so they don't need to be regenerated
every time.

This is the ONLY place in the app that should build Gemini prompts
for reading guides, parse Gemini's response into a structured guide,
or read/write data/reading_guides.json. Everything else in the app
(especially Streamlit) should call generate_guide() or
get_saved_guide() instead of doing any of that itself.

No Streamlit code and no Open Library API code belongs in this file.
"""

import json
import os
from typing import Optional

from models.book import Book
from services.gemini_client import GeminiClient


class ReadingGuideGenerator:
    """
    Generates and caches AI reading guides for books.

    Follows the same load-on-init / save-on-change pattern as
    ReadingListManager: guides are kept in memory in self._guides (a
    dict keyed by book identifier), and any change is immediately
    written back to disk.
    """

    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        filepath: str = "data/reading_guides.json",
    ) -> None:
        """
        Create a ReadingGuideGenerator.

        Args:
            gemini_client: An existing GeminiClient to reuse. If not
                provided, a new one is created automatically using the
                GEMINI_API_KEY environment variable.
            filepath: Where reading guides are saved/loaded as JSON.

        Note on the missing-API-key case: if no gemini_client is given
        AND creating one fails because GEMINI_API_KEY isn't set, we do
        NOT crash here. GeminiClient() raises ValueError in that case,
        and we catch it, print a clear message, and continue with
        self.gemini_client set to None. generate_guide() then checks
        for that and returns a clean error result instead of trying to
        use a client that doesn't exist. This means the rest of the
        app (like the reading list, or Open Library search) can keep
        working perfectly fine even if Gemini isn't configured yet.
        """
        self.filepath: str = filepath
        self._guides: dict = {}

        if gemini_client is not None:
            self.gemini_client: Optional[GeminiClient] = gemini_client
        else:
            try:
                self.gemini_client = GeminiClient()
            except ValueError as error:
                print(f"ReadingGuideGenerator warning: {error}")
                self.gemini_client = None

        self.load()

    def load(self) -> None:
        """
        Load previously saved reading guides from self.filepath into
        memory. Missing or corrupted files are handled the same way
        as ReadingListManager: fall back to an empty dict rather than
        crashing.
        """
        if not os.path.exists(self.filepath):
            self._guides = {}
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as file:
                self._guides = json.load(file)

        except json.JSONDecodeError as error:
            print(f"ReadingGuideGenerator error: could not parse {self.filepath} "
                  f"as JSON ({error}). Starting with no saved guides.")
            self._guides = {}

        except OSError as error:
            print(f"ReadingGuideGenerator error: could not read {self.filepath} "
                  f"({error}). Starting with no saved guides.")
            self._guides = {}

    def save(self) -> None:
        """
        Save the current in-memory guides to self.filepath as JSON,
        creating the containing folder if it doesn't exist yet.
        """
        try:
            directory = os.path.dirname(self.filepath)
            if directory:
                os.makedirs(directory, exist_ok=True)

            with open(self.filepath, "w", encoding="utf-8") as file:
                json.dump(self._guides, file, indent=2)

        except OSError as error:
            print(f"ReadingGuideGenerator error: could not save to {self.filepath} "
                  f"({error}). Your guide was kept in memory but not written to disk.")

    def generate_guide(self, book: Book, force_regenerate: bool = False) -> dict:
        """
        Generate a reading guide for `book` using Gemini, or return the
        already-saved guide if one exists and force_regenerate=False.

        Returns a dictionary shaped like:
            {
                "success": True,
                "guide": {"summary": "...", "reading_level": "...", "questions": [...]},
                "error": None,
                "from_cache": True or False,
            }
        or, on failure:
            {"success": False, "guide": None, "error": "some message", "from_cache": False}
        """
        key = self._key_for_book(book)

        if not force_regenerate and key in self._guides:
            return {
                "success": True,
                "guide": self._guides[key],
                "error": None,
                "from_cache": True,
            }

        if self.gemini_client is None:
            return {
                "success": False,
                "guide": None,
                "error": "Gemini is not available (no valid GEMINI_API_KEY was found).",
                "from_cache": False,
            }

        prompt = self._build_prompt(book)
        text_result = self.gemini_client.generate_text(prompt)

        if not text_result["success"]:
            return {
                "success": False,
                "guide": None,
                "error": text_result["error"],
                "from_cache": False,
            }

        guide = self._parse_response(text_result["text"])

        if guide is None:
            return {
                "success": False,
                "guide": None,
                "error": "Gemini responded, but its response could not be understood "
                         "as a reading guide.",
                "from_cache": False,
            }

        self._guides[key] = guide
        self.save()

        return {
            "success": True,
            "guide": guide,
            "error": None,
            "from_cache": False,
        }

    def get_saved_guide(self, book: Book) -> Optional[dict]:
        """
        Return a previously saved guide for `book`, or None if no
        guide has been saved for it yet. Does not call Gemini.
        """
        key = self._key_for_book(book)
        return self._guides.get(key)

    def _key_for_book(self, book: Book) -> str:
        """
        Build the dictionary key used to store/look up a book's guide.
        ISBN is preferred since it's unique; if a book has no ISBN, we
        fall back to a normalized title so guides can still be cached.
        """
        if book.isbn:
            return book.isbn
        return f"title:{book.title.strip().lower()}"

    def _build_prompt(self, book: Book) -> str:
        """
        Build the Gemini prompt for a reading guide, using the book's
        own fields. This is the ONLY place in the app that constructs
        this prompt -- Streamlit should never build prompts itself.

        We explicitly ask Gemini to respond in JSON with specific keys,
        which makes _parse_response() simple and predictable.
        """
        subjects_text = ", ".join(book.subjects) if book.subjects else "unknown"
        year_text = str(book.publication_year) if book.publication_year else "unknown"

        return (
            f"You are helping a reader understand a book before they start it.\n"
            f"Book title: {book.title}\n"
            f"Author(s): {book.authors_display()}\n"
            f"Publication year: {year_text}\n"
            f"Subjects: {subjects_text}\n\n"
            f"Respond with ONLY a JSON object (no extra text, no markdown code "
            f"fences) with exactly these keys:\n"
            f'  "summary": a short, spoiler-light summary (2-3 sentences)\n'
            f'  "reading_level": a brief suggested reading level or age range\n'
            f'  "questions": a list of exactly 3 discussion/comprehension questions\n'
        )

    def _parse_response(self, text: str) -> Optional[dict]:
        """
        Parse Gemini's raw text response into a reading guide dict.

        Gemini sometimes wraps JSON in markdown code fences even when
        asked not to, so we strip those before parsing. Returns None
        if the response can't be parsed or is missing required keys,
        so the caller can treat that as a clean failure.
        """
        cleaned_text = text.strip()

        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text.strip("`")
            if cleaned_text.startswith("json"):
                cleaned_text = cleaned_text[4:]
            cleaned_text = cleaned_text.strip()

        try:
            parsed = json.loads(cleaned_text)
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None

        summary = parsed.get("summary")
        reading_level = parsed.get("reading_level")
        questions = parsed.get("questions")

        if not summary or not reading_level or not isinstance(questions, list):
            return None

        return {
            "summary": summary,
            "reading_level": reading_level,
            "questions": questions,
        }


if __name__ == "__main__":

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    TEST_FILEPATH = "data/test_reading_guides.json"

    if os.path.exists(TEST_FILEPATH):
        os.remove(TEST_FILEPATH)

    matilda = Book(
        title="Matilda",
        authors=["Roald Dahl"],
        publication_year=1988,
        isbn="9780140328721",
        page_count=240,
        subjects=["Children's fiction", "Magic", "Family"],
    )

    generator = ReadingGuideGenerator(filepath=TEST_FILEPATH)

    if generator.gemini_client is None:
        print("No GEMINI_API_KEY found, so this test cannot call the real Gemini API.")
        print("(See services/gemini_client.py's test section for setup instructions.)")
        print()

        print("--- Calling generate_guide() anyway (expected: clean failure, no crash) ---")
        result = generator.generate_guide(matilda)
        print("success:", result["success"])
        print("error:", result["error"])

        print()
        print("--- Proving save/load still works, using a manually-created guide ---")
        fake_guide = {
            "summary": "A gifted girl outsmarts her neglectful family and a fearsome headmistress.",
            "reading_level": "Ages 8-12",
            "questions": [
                "Why does Matilda use her intelligence the way she does?",
                "How does Miss Honey's character change over the story?",
                "What role does kindness play in the story's ending?",
            ],
        }
        key = generator._key_for_book(matilda)
        generator._guides[key] = fake_guide
        generator.save()

    else:
        print("GEMINI_API_KEY found. Generating a real reading guide for Matilda...")
        print()

        result = generator.generate_guide(matilda)

        if result["success"]:
            guide = result["guide"]
            print("Summary:", guide["summary"])
            print("Reading level:", guide["reading_level"])
            print("Discussion questions:")
            for index, question in enumerate(guide["questions"], start=1):
                print(f"  {index}. {question}")
        else:
            print("Guide generation failed:", result["error"])

    print()
    print("--- Confirming the guide can be retrieved without calling Gemini again ---")
    saved_guide = generator.get_saved_guide(matilda)
    if saved_guide:
        print("Retrieved from cache successfully:")
        print(saved_guide)
    else:
        print("No saved guide was found (unexpected).")

    print()
    print("--- Reloading from disk into a fresh ReadingGuideGenerator ---")
    reloaded_generator = ReadingGuideGenerator(filepath=TEST_FILEPATH)
    reloaded_guide = reloaded_generator.get_saved_guide(matilda)
    if reloaded_guide:
        print("Guide successfully persisted and reloaded from disk.")
    else:
        print("Guide was NOT found after reloading (unexpected).")

    if os.path.exists(TEST_FILEPATH):
        os.remove(TEST_FILEPATH)
    print("\nTest file cleaned up.")