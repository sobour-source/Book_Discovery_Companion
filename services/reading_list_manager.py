"""
reading_list_manager.py

Defines the ReadingListManager class: manages the user's personal
reading list and saves/loads it to a local JSON file.

This is the ONLY place in the app that should read or write
data/reading_list.json. Everything else in the app should go through
this class's methods instead of touching the file directly.

No Streamlit code and no Open Library API code belongs in this file --
this class only knows about Book objects and the JSON file that stores
them.
"""

import json
import os
from typing import List, Optional

from models.book import Book


class ReadingListManager:
    """
    Manages a collection of Book objects representing the user's
    personal reading list, backed by a JSON file on disk.

    Books are kept in memory in self._books (a list), and every method
    that changes that list also saves it straight back to disk. For a
    small student project, "save on every change" is much simpler and
    safer than trying to track when data is "dirty" and needs saving.
    """

    VALID_STATUSES: List[str] = ["Want to Read", "Reading", "Finished"]

    def __init__(self, filepath: str = "data/reading_list.json") -> None:
        """
        Create a ReadingListManager backed by the JSON file at
        `filepath`. The file (and its containing folder) will be
        created automatically the first time we save, if they don't
        already exist.
        """
        self.filepath: str = filepath
        self._books: List[Book] = []

        self.load()

    def load(self) -> None:
        """
        Load the reading list from self.filepath into memory.

        If the file doesn't exist yet, that's not an error -- we just
        start with an empty list. If the file exists but contains
        invalid JSON, we also fall back to an empty list rather than
        crashing the whole app.
        """
        if not os.path.exists(self.filepath):
            self._books = []
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as file:
                raw_data = json.load(file)

            self._books = [Book.from_dict(book_dict) for book_dict in raw_data]

        except json.JSONDecodeError as error:
            print(f"ReadingListManager error: could not parse {self.filepath} "
                  f"as JSON ({error}). Starting with an empty reading list.")
            self._books = []

        except OSError as error:
            print(f"ReadingListManager error: could not read {self.filepath} "
                  f"({error}). Starting with an empty reading list.")
            self._books = []

    def save(self) -> None:
        """
        Save the current in-memory reading list to self.filepath as
        JSON, creating the containing folder if it doesn't exist yet.
        """
        try:
            directory = os.path.dirname(self.filepath)
            if directory:
                os.makedirs(directory, exist_ok=True)

            book_dicts = [book.to_dict() for book in self._books]

            with open(self.filepath, "w", encoding="utf-8") as file:
                json.dump(book_dicts, file, indent=2)

        except OSError as error:
            print(f"ReadingListManager error: could not save to {self.filepath} "
                  f"({error}). Your changes were kept in memory but not written to disk.")

    def add_book(self, book: Book) -> bool:
        """
        Add a Book to the reading list and save. Returns True if the
        book was added, or False if it was skipped as a duplicate.

        A book is considered a duplicate in TWO ways:
          1. Same ISBN as a book already on the list (the original,
             cheap check).
          2. Same normalized title AND same normalized author(s) as a
             book already on the list, even if the ISBN is different.
             This catches the common real-world case of two different
             editions/printings of the same book having different
             ISBNs -- Open Library treats them as separate records,
             but a reader doesn't want "Matilda" showing up twice on
             their list just because they searched twice and picked a
             different edition.

        Books with a missing ISBN are still allowed through the ISBN
        check (nothing to compare), but they ARE still checked against
        the title+author rule.
        """
        if book.isbn is not None and self.contains(book.isbn):
            print(f"ReadingListManager: '{book.title}' (ISBN {book.isbn}) "
                  f"is already on the reading list -- not adding a duplicate.")
            return False

        if self._is_duplicate_by_title_and_author(book):
            print(f"ReadingListManager: '{book.title}' by {book.authors_display()} "
                  f"appears to already be on the reading list under a different "
                  f"ISBN -- not adding a duplicate.")
            return False

        self._books.append(book)
        self.save()
        return True

    def _is_duplicate_by_title_and_author(self, book: Book) -> bool:
        """
        Return True if a book with the same normalized title AND the
        same normalized author(s) is already on the list.

        This is what lets two different ISBNs for the same underlying
        book (different editions/printings) be recognized as
        duplicates, while still allowing:
          - the same title by a genuinely different author, and
          - different titles by the same author.
        """
        target_title = self._normalize_text(book.title)
        target_authors = self._normalize_text(book.authors_display())

        for existing_book in self._books:
            existing_title = self._normalize_text(existing_book.title)
            existing_authors = self._normalize_text(existing_book.authors_display())

            if existing_title == target_title and existing_authors == target_authors:
                return True

        return False

    @staticmethod
    def _normalize_text(text: Optional[str]) -> str:
        """
        Normalize a string for duplicate-comparison purposes: lowercase,
        strip leading/trailing whitespace, and collapse any internal
        run of whitespace down to a single space. This is what makes
        "Matilda", "matilda", and "Matilda  " all compare as equal.
        """
        if not text:
            return ""
        return " ".join(text.strip().lower().split())

    def remove_book(self, isbn: str) -> bool:
        """
        Remove the book with the given ISBN from the reading list and
        save. Returns True if a book was removed, False if no book
        with that ISBN was found.
        """
        original_count = len(self._books)
        self._books = [book for book in self._books if book.isbn != isbn]

        removed = len(self._books) < original_count
        if removed:
            self.save()
        return removed

    def update_status(self, isbn: str, status: str) -> bool:
        """
        Update the reading status of the book with the given ISBN, and
        save. Returns True if the status was changed, or False if
        either the status isn't one of VALID_STATUSES or no book with
        that ISBN was found on the list.
        """
        if status not in self.VALID_STATUSES:
            print(f"ReadingListManager: '{status}' is not a valid status. "
                  f"Valid statuses are: {', '.join(self.VALID_STATUSES)}.")
            return False

        if not isbn:
            return False

        for book in self._books:
            if book.isbn == isbn:
                book.status = status
                self.save()
                return True

        print(f"ReadingListManager: no book with ISBN {isbn} was found to update.")
        return False

    def contains(self, isbn: str) -> bool:
        """
        Return True if a book with the given ISBN is already on the
        reading list. A None or empty isbn always returns False.
        """
        if not isbn:
            return False
        return any(book.isbn == isbn for book in self._books)

    def get_all_books(self) -> List[Book]:
        """
        Return all books currently on the reading list (a copy of the
        internal list, so callers can't mutate it directly).
        """
        return list(self._books)

    def clear(self) -> None:
        """
        Remove every book from the reading list and save the (now
        empty) list to disk.
        """
        self._books = []
        self.save()

    def __len__(self) -> int:
        """
        Allows len(manager) to work directly.
        """
        return len(self._books)


if __name__ == "__main__":

    TEST_FILEPATH = "data/test_reading_list.json"

    if os.path.exists(TEST_FILEPATH):
        os.remove(TEST_FILEPATH)

    manager = ReadingListManager(filepath=TEST_FILEPATH)
    print("Starting book count:", len(manager))

    matilda = Book(
        title="Matilda",
        authors=["Roald Dahl"],
        publication_year=1988,
        isbn="9780140328721",
        page_count=240,
    )

    the_hobbit = Book(
        title="The Hobbit",
        authors=["J.R.R. Tolkien"],
        publication_year=1937,
        isbn="9780547928227",
        page_count=310,
    )

    mystery_book = Book(title="Untitled Notes", isbn=None)

    print("\n--- Adding books ---")
    manager.add_book(matilda)
    manager.add_book(the_hobbit)
    manager.add_book(mystery_book)
    print("Book count after adding 3 books:", len(manager))

    print("\n--- Attempting to add a duplicate ISBN ---")
    duplicate_matilda = Book(title="Matilda (different edition)", isbn="9780140328721")
    added = manager.add_book(duplicate_matilda)
    print("Duplicate was added:", added)
    print("Book count should still be 3:", len(manager))

    print("\n--- Same book, DIFFERENT ISBN (different edition) -- should be rejected ---")
    matilda_different_edition = Book(
        title="matilda ",
        authors=["Roald Dahl"],
        isbn="1111111111",
    )
    added_different_edition = manager.add_book(matilda_different_edition)
    print("Different-edition duplicate was added (expected False):", added_different_edition)
    print("Book count should still be 3:", len(manager))

    print("\n--- Same title, DIFFERENT author -- should be allowed ---")
    different_author_same_title = Book(
        title="Matilda",
        authors=["Someone Else Entirely"],
        isbn="2222222222",
    )
    added_different_author = manager.add_book(different_author_same_title)
    print("Same-title-different-author book was added (expected True):", added_different_author)
    print("Book count should now be 4:", len(manager))

    print("\n--- Different title, SAME author -- should be allowed ---")
    same_author_different_title = Book(
        title="Charlie and the Chocolate Factory",
        authors=["Roald Dahl"],
        isbn="3333333333",
    )
    added_same_author = manager.add_book(same_author_different_title)
    print("Different-title-same-author book was added (expected True):", added_same_author)
    print("Book count should now be 5:", len(manager))

    print("\n--- contains() checks ---")
    print("Contains Matilda's ISBN:", manager.contains("9780140328721"))
    print("Contains a random ISBN:", manager.contains("0000000000"))
    print("Contains None:", manager.contains(None))

    print("\n--- Reloading from disk into a fresh manager ---")
    reloaded_manager = ReadingListManager(filepath=TEST_FILEPATH)
    print("Book count after reload:", len(reloaded_manager))
    for book in reloaded_manager.get_all_books():
        print("-", book)

    print("\n--- Removing a book ---")
    removed = reloaded_manager.remove_book("9780547928227")
    print("The Hobbit was removed:", removed)
    print("Book count after removal:", len(reloaded_manager))

    print("\n--- Removing a book that isn't on the list ---")
    removed_again = reloaded_manager.remove_book("1234567890")
    print("Nonexistent ISBN removal returned:", removed_again)

    print("\n--- Testing reading status ---")
    matilda_isbn = "9780140328721"

    print("Matilda's status right after adding (expected 'Want to Read'):",
          next(b.status for b in reloaded_manager.get_all_books() if b.isbn == matilda_isbn))

    changed_to_reading = reloaded_manager.update_status(matilda_isbn, "Reading")
    print("Changed to 'Reading':", changed_to_reading)

    changed_to_finished = reloaded_manager.update_status(matilda_isbn, "Finished")
    print("Changed to 'Finished':", changed_to_finished)

    print("\n--- Rejecting an invalid status ---")
    rejected = reloaded_manager.update_status(matilda_isbn, "Currently Napping")
    print("Invalid status was accepted (expected False):", rejected)

    print("\n--- Updating status for a nonexistent ISBN ---")
    missing_isbn_result = reloaded_manager.update_status("0000000000", "Reading")
    print("Nonexistent ISBN update returned (expected False):", missing_isbn_result)

    print("\n--- Confirming the status persisted to disk ---")
    reloaded_again_manager = ReadingListManager(filepath=TEST_FILEPATH)
    matilda_after_reload = next(
        (b for b in reloaded_again_manager.get_all_books() if b.isbn == matilda_isbn), None
    )
    if matilda_after_reload:
        print("Matilda's status after fresh reload (expected 'Finished'):",
              matilda_after_reload.status)
        assert matilda_after_reload.status == "Finished"
    else:
        print("Matilda was not found after reload (unexpected).")

    print("\n--- Clearing the list ---")
    reloaded_manager.clear()
    print("Book count after clear():", len(reloaded_manager))

    if os.path.exists(TEST_FILEPATH):
        os.remove(TEST_FILEPATH)
    print("\nTest file cleaned up.")