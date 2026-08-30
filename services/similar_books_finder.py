"""
similar_books_finder.py

Defines the SimilarBooksFinder class: suggests books similar to a
given Book, using Open Library's subject data.

This component deliberately does NOT use GeminiClient. The project's
design decision is that "similar books" should come from Open
Library's own subject/category data rather than an AI model -- it's
free, fast, doesn't risk hallucinated titles, and doesn't add another
point of API failure for a feature that doesn't need AI reasoning.

This is NOT the place to make raw Open Library HTTP requests -- all
network calls are delegated to OpenLibraryClient (specifically its
search_by_subject() method), the same as every other part of the app.

No Streamlit code and no Gemini setup belongs in this file.
"""

from typing import List, Optional

from models.book import Book
from services.openlibrary_client import OpenLibraryClient


class SimilarBooksFinder:
    """
    Finds books similar to a given Book by looking at what subjects
    it belongs to, and asking OpenLibraryClient for other books that
    share those subjects.
    """

    def __init__(self, openlibrary_client: Optional[OpenLibraryClient] = None) -> None:
        """
        Create a SimilarBooksFinder.

        Args:
            openlibrary_client: An existing OpenLibraryClient to reuse.
                If not provided, a new one is created. Accepting it as
                a parameter (rather than always creating a new one
                internally) makes this class easy to test in isolation
                later, by passing in a fake/mock client.
        """
        self.openlibrary_client: OpenLibraryClient = openlibrary_client or OpenLibraryClient()

    def find_similar_books(
        self,
        book: Book,
        limit: int = 5,
        subjects_to_try: int = 2,
    ) -> List[Book]:
        """
        Find books similar to `book`, based on shared subjects.

        Args:
            book: The Book to find similar books for.
            limit: The maximum number of similar books to return.
            subjects_to_try: How many of the book's subjects to search
                through while looking for enough candidates. Trying
                more than one subject gives better variety, since a
                single subject (e.g. "Fiction") can be too broad or
                too narrow on its own.

        Returns:
            A list of Book objects similar to `book`, never including
            `book` itself. Returns an empty list if the book has no
            known subjects, or if no similar books could be found.
        """
        if not book.subjects:
            print(f"SimilarBooksFinder: '{book.title}' has no known subjects, "
                  f"so no similar books can be found.")
            return []

        candidates: List[Book] = []
        seen_titles = {self._normalize_title(book.title)}

        for subject in book.subjects[:subjects_to_try]:
            subject_results = self.openlibrary_client.search_by_subject(subject, limit=limit + 5)

            for candidate in subject_results:
                normalized = self._normalize_title(candidate.title)

                if normalized in seen_titles:
                    continue

                seen_titles.add(normalized)
                candidates.append(candidate)

                if len(candidates) >= limit:
                    return candidates

        return candidates

    def _normalize_title(self, title: str) -> str:
        """
        Normalize a title for comparison purposes, so that things like
        "Matilda" and "matilda " are correctly treated as the same
        book when filtering out duplicates/the original book.
        """
        return title.strip().lower()


if __name__ == "__main__":

    matilda = Book(
        title="Matilda",
        authors=["Roald Dahl"],
        publication_year=1988,
        isbn="9780140328721",
        page_count=240,
        subjects=["Children's fiction", "Magic", "Family"],
    )

    print(f"Finding books similar to: {matilda}")
    print(f"Subjects being searched: {matilda.subjects[:2]}")
    print()

    finder = SimilarBooksFinder()
    similar_books = finder.find_similar_books(matilda, limit=5)

    if not similar_books:
        print("No similar books found (or a network error occurred -- "
              "see any message above).")
    else:
        print(f"Found {len(similar_books)} similar book(s):")
        for index, similar_book in enumerate(similar_books, start=1):
            print(f"  {index}. {similar_book}")

        titles = [b.title.strip().lower() for b in similar_books]
        assert "matilda" not in titles, "The original book should never be suggested to itself!"
        print("\nConfirmed: the original book was correctly excluded from its own results.")

    print("\n=== Testing a book with no subjects (expected: empty list) ===")
    mystery_book = Book(title="Untitled Notes")
    no_subject_results = finder.find_similar_books(mystery_book, limit=5)
    print("Results found:", len(no_subject_results))