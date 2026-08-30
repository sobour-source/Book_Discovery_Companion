"""
book.py

Defines the Book class: a simple data container representing one book.

This class has ONE job: hold book information in a clean, predictable
shape. It does not know how to search for books, call any API, save
itself to a file, or draw anything on screen. Keeping it this focused
is what makes it reusable everywhere else in the app.
"""

from typing import List, Optional


class Book:
    """
    Represents a single book and its known details.

    All fields except `title` are optional, because real book data
    (especially from an external API) is often incomplete. Rather than
    forcing every field to exist, we give sensible defaults so a Book
    can always be created and displayed safely, even with partial data.
    """

    def __init__(
        self,
        title: str,
        authors: Optional[List[str]] = None,
        publication_year: Optional[int] = None,
        isbn: Optional[str] = None,
        page_count: Optional[int] = None,
        subjects: Optional[List[str]] = None,
        cover_url: Optional[str] = None,
        status: Optional[str] = "Want to Read",
    ) -> None:
        """
        Create a new Book.

        Note on mutable defaults: we never write `authors: list = []`
        directly in the parameter list. Default argument values in
        Python are created ONCE, when the function is defined, not
        each time it's called. If we used `[]` as the default, every
        Book that didn't specify authors would end up SHARING the same
        list object, and appending to one Book's authors would silently
        affect every other Book too. Using `None` as the default and
        creating a fresh list inside the method body avoids this trap.
        """
        self.title: str = title
        self.authors: List[str] = authors if authors is not None else []
        self.publication_year: Optional[int] = publication_year
        self.isbn: Optional[str] = isbn
        self.page_count: Optional[int] = page_count
        self.subjects: List[str] = subjects if subjects is not None else []
        self.cover_url: Optional[str] = cover_url

        # Falls back to "Want to Read" for None, empty string, or any
        # other falsy value -- this is what makes loading OLD saved
        # reading-list JSON (from before status existed) safe: those
        # dictionaries simply won't have a "status" key, from_dict()
        # will pass status=None, and it lands on the same default.
        self.status: str = status if status else "Want to Read"

    def authors_display(self) -> str:
        """
        Return the author list as a single readable string, e.g.
        "Roald Dahl" or "Roald Dahl, Quentin Blake". Falls back to
        "Unknown author" when no authors are known.
        """
        if not self.authors:
            return "Unknown author"
        return ", ".join(self.authors)

    def to_dict(self) -> dict:
        """
        Convert this Book into a plain dictionary, e.g. for saving
        to JSON later (that logic will live in ReadingListManager,
        not here — this method just describes the Book's own shape).
        """
        return {
            "title": self.title,
            "authors": self.authors,
            "publication_year": self.publication_year,
            "isbn": self.isbn,
            "page_count": self.page_count,
            "subjects": self.subjects,
            "cover_url": self.cover_url,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Book":
        """
        Rebuild a Book from a plain dictionary (e.g. one loaded back
        out of a JSON file). Using .get() everywhere means a dictionary
        missing some keys won't crash this method — missing fields
        just fall back to the Book's own defaults.
        """
        return cls(
            title=data.get("title", "Unknown Title"),
            authors=data.get("authors"),
            publication_year=data.get("publication_year"),
            isbn=data.get("isbn"),
            page_count=data.get("page_count"),
            subjects=data.get("subjects"),
            cover_url=data.get("cover_url"),
            status=data.get("status"),  # None if missing -> Book defaults it to "Want to Read"
        )

    def __str__(self) -> str:
        """
        A friendly, human-readable summary — this is what you get from
        print(book) or str(book). Meant for people to read.
        """
        year = self.publication_year if self.publication_year else "Unknown year"
        pages = f"{self.page_count} pages" if self.page_count else "Unknown length"
        return f'"{self.title}" by {self.authors_display()} ({year}, {pages})'

    def __repr__(self) -> str:
        """
        An unambiguous, developer-facing representation — this is what
        you see when a Book shows up in a list, in a debugger, or at
        the interactive Python prompt.
        """
        return (
            f"Book(title={self.title!r}, authors={self.authors!r}, "
            f"publication_year={self.publication_year!r}, isbn={self.isbn!r}, "
            f"page_count={self.page_count!r}, status={self.status!r})"
        )


if __name__ == "__main__":

    matilda = Book(
        title="Matilda",
        authors=["Roald Dahl", "Quentin Blake"],
        publication_year=1988,
        isbn="9780140328721",
        page_count=240,
        subjects=["Children's fiction", "Magic", "Family"],
        cover_url="https://covers.openlibrary.org/b/isbn/9780140328721-M.jpg",
    )

    mystery_book = Book(title="Untitled Mystery Novel")

    print("--- str() output (friendly) ---")
    print(str(matilda))
    print(str(mystery_book))

    print("\n--- repr() output (developer-facing) ---")
    print(repr(matilda))
    print(repr(mystery_book))

    print("\n--- status defaults ---")
    print("matilda.status (expected 'Want to Read'):", matilda.status)
    print("mystery_book.status (expected 'Want to Read'):", mystery_book.status)
    assert matilda.status == "Want to Read"
    assert mystery_book.status == "Want to Read"

    print("\n--- backward compatibility: old saved dict with no 'status' key ---")
    old_saved_dict = {
        "title": "Pre-Status Book",
        "authors": ["Some Author"],
        "isbn": "0000000000",
        # no "status" key at all -- simulates data saved before this feature existed
    }
    rebuilt_old_book = Book.from_dict(old_saved_dict)
    print("Rebuilt old book's status (expected 'Want to Read'):", rebuilt_old_book.status)
    assert rebuilt_old_book.status == "Want to Read"

    print("\n--- authors_display() ---")
    print(matilda.authors_display())
    print(mystery_book.authors_display())

    print("\n--- to_dict() ---")
    print(matilda.to_dict())

    print("\n--- from_dict() round trip ---")
    matilda_dict = matilda.to_dict()
    rebuilt_matilda = Book.from_dict(matilda_dict)
    print(rebuilt_matilda)
    print("Round trip successful:", rebuilt_matilda.to_dict() == matilda_dict)