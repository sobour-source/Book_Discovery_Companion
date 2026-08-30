"""
openlibrary_client.py

Defines the OpenLibraryClient class: handles all communication with the
Open Library API (https://openlibrary.org).

This is the ONLY place in the app that should make network requests to
Open Library. Every method here returns Book objects (from models/book.py)
or None/[] when nothing is found -- callers never have to deal with raw
Open Library JSON directly.

No Streamlit code, no Gemini code, and no file storage code belongs in
this file. Its only job is: take a search request, talk to the API,
hand back Book objects.
"""

from typing import List, Optional

import requests

from models.book import Book


class OpenLibraryClient:
    """
    A small wrapper around the Open Library Search API.

    Open Library's search.json endpoint is used for all three search
    types (title, author, ISBN) so that the response-parsing logic only
    has to be written once, in _doc_to_book().
    """

    SEARCH_URL = "https://openlibrary.org/search.json"

    COVER_URL_TEMPLATE = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"

    SUBJECTS_URL = "https://openlibrary.org/subjects"

    REQUEST_TIMEOUT = 5

    HEADERS = {
        "User-Agent": "BookDiscoveryCompanion/1.0 (student project)"
    }

    def search_by_title(self, title: str, limit: int = 10) -> List[Book]:
        """
        Search for books by title. Returns a list of Book objects
        (possibly empty if nothing matches or an error occurs).
        """
        if not title or not title.strip():
            return []

        params = {
            "title": title.strip(),
            "limit": limit,
            "fields": self._fields_to_request(),
        }
        return self._search(params)

    def search_by_author(self, author: str, limit: int = 10) -> List[Book]:
        """
        Search for books by author name. Returns a list of Book objects
        (possibly empty if nothing matches or an error occurs).
        """
        if not author or not author.strip():
            return []

        params = {
            "author": author.strip(),
            "limit": limit,
            "fields": self._fields_to_request(),
        }
        return self._search(params)

    def search_by_isbn(self, isbn: str) -> Optional[Book]:
        """
        Search for a single book by ISBN. Returns a Book object, or
        None if nothing matches or an error occurs.
        """
        if not isbn or not isbn.strip():
            return None

        cleaned_isbn = isbn.strip().replace("-", "").replace(" ", "")

        params = {
            "q": f"isbn:{cleaned_isbn}",
            "limit": 1,
            "fields": self._fields_to_request(),
        }
        results = self._search(params)
        return results[0] if results else None

    def search_by_subject(self, subject: str, limit: int = 10) -> List[Book]:
        """
        Search for books that share a given subject/category, using
        Open Library's subjects endpoint. This is used to power
        "similar books" suggestions elsewhere in the app.

        This endpoint returns a DIFFERENT JSON shape than search.json,
        so it is parsed separately by _subject_work_to_book() rather
        than reusing _doc_to_book().
        """
        if not subject or not subject.strip():
            return []

        subject_slug = self._slugify_subject(subject)
        url = f"{self.SUBJECTS_URL}/{subject_slug}.json"
        params = {"limit": limit}

        try:
            response = requests.get(
                url,
                params=params,
                headers=self.HEADERS,
                timeout=self.REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            data = response.json()
            works = data.get("works", [])
            return [self._subject_work_to_book(work) for work in works]

        except requests.exceptions.Timeout:
            print("OpenLibraryClient error: the subject request timed out.")
            return []

        except requests.exceptions.ConnectionError:
            print("OpenLibraryClient error: could not connect to Open Library. "
                  "Check your internet connection.")
            return []

        except requests.exceptions.HTTPError as error:
            print(f"OpenLibraryClient error: Open Library returned an error response ({error}).")
            return []

        except requests.exceptions.RequestException as error:
            print(f"OpenLibraryClient error: subject request failed ({error}).")
            return []

        except ValueError as error:
            print(f"OpenLibraryClient error: could not parse subject response as JSON ({error}).")
            return []

    def _slugify_subject(self, subject: str) -> str:
        """
        Turn a human-readable subject like "Children's fiction" into
        the URL-friendly slug Open Library expects, e.g.
        "children's_fiction" -- lowercase, with spaces replaced by
        underscores.
        """
        return subject.strip().lower().replace(" ", "_")

    def _subject_work_to_book(self, work: dict) -> Book:
        """
        Convert one "work" entry from the subjects endpoint into a
        Book object. Uses .get() with defaults throughout, since this
        endpoint's entries are often missing fields (in particular,
        it does not provide an ISBN or a subject list per work).
        """
        title = work.get("title", "Unknown Title")

        author_entries = work.get("authors", [])
        authors = [entry.get("name") for entry in author_entries if entry.get("name")]

        publication_year = work.get("first_publish_year")

        cover_id = work.get("cover_id")
        cover_url = self.COVER_URL_TEMPLATE.format(cover_id=cover_id) if cover_id else None

        return Book(
            title=title,
            authors=authors,
            publication_year=publication_year,
            isbn=None,
            page_count=None,
            subjects=[],
            cover_url=cover_url,
        )

    def _fields_to_request(self) -> str:
        """
        The specific Open Library fields we want back. Requesting only
        what we need keeps responses smaller and faster.
        """
        return "title,author_name,first_publish_year,isbn,number_of_pages_median,subject,cover_i"

    def _search(self, params: dict) -> List[Book]:
        """
        Shared logic for calling search.json and turning the response
        into a list of Book objects. All three public search_* methods
        funnel through here.
        """
        try:
            response = requests.get(
                self.SEARCH_URL,
                params=params,
                headers=self.HEADERS,
                timeout=self.REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            data = response.json()
            docs = data.get("docs", [])
            return [self._doc_to_book(doc) for doc in docs]

        except requests.exceptions.Timeout:
            print("OpenLibraryClient error: the request timed out.")
            return []

        except requests.exceptions.ConnectionError:
            print("OpenLibraryClient error: could not connect to Open Library. "
                  "Check your internet connection.")
            return []

        except requests.exceptions.HTTPError as error:
            print(f"OpenLibraryClient error: Open Library returned an error response ({error}).")
            return []

        except requests.exceptions.RequestException as error:
            print(f"OpenLibraryClient error: request failed ({error}).")
            return []

        except ValueError as error:
            print(f"OpenLibraryClient error: could not parse response as JSON ({error}).")
            return []

    def _doc_to_book(self, doc: dict) -> Book:
        """
        Convert one raw Open Library search result ("doc") into a Book
        object. Uses .get() with defaults everywhere, because Open
        Library entries are frequently missing fields.
        """
        title = doc.get("title", "Unknown Title")
        authors = doc.get("author_name", [])
        publication_year = doc.get("first_publish_year")
        page_count = doc.get("number_of_pages_median")
        subjects = doc.get("subject", [])

        isbn_list = doc.get("isbn", [])
        isbn = isbn_list[0] if isbn_list else None

        cover_id = doc.get("cover_i")
        cover_url = self.COVER_URL_TEMPLATE.format(cover_id=cover_id) if cover_id else None

        return Book(
            title=title,
            authors=authors,
            publication_year=publication_year,
            isbn=isbn,
            page_count=page_count,
            subjects=subjects,
            cover_url=cover_url,
        )


if __name__ == "__main__":

    client = OpenLibraryClient()

    print("=== Searching by title: 'Matilda' ===")
    title_results = client.search_by_title("Matilda", limit=3)
    if not title_results:
        print("No results found (or a network error occurred -- see any message above).")
    for book in title_results:
        print("-", book)

    print("\n=== Searching by author: 'Roald Dahl' ===")
    author_results = client.search_by_author("Roald Dahl", limit=3)
    if not author_results:
        print("No results found (or a network error occurred -- see any message above).")
    for book in author_results:
        print("-", book)

    print("\n=== Searching by ISBN: 9780140328721 (Matilda) ===")
    isbn_result = client.search_by_isbn("9780140328721")
    if isbn_result:
        print("-", isbn_result)
        print("  Cover URL:", isbn_result.cover_url)
        print("  Subjects:", isbn_result.subjects[:5], "..." if len(isbn_result.subjects) > 5 else "")
    else:
        print("No result found for that ISBN (or a network error occurred).")

    print("\n=== Searching by subject: 'magic' ===")
    subject_results = client.search_by_subject("magic", limit=3)
    if not subject_results:
        print("No results found (or a network error occurred -- see any message above).")
    for book in subject_results:
        print("-", book)

    print("\n=== Searching for a nonsense title (expected: no results) ===")
    empty_results = client.search_by_title("asdkjfhalksjdhflkajshdflkjashdf")
    print("Results found:", len(empty_results))