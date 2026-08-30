"""
validators.py

Pure validation functions for ISBN-10 and ISBN-13 numbers.

This module has NO dependency on Streamlit, requests, or any other part
of the app. That's intentional: pure functions (input in, answer out,
no side effects) are the easiest kind of code to test and reason about.

Validation happens in two layers:
    1. FORMAT check (regex)   -> "does this look like an ISBN at all?"
    2. CHECKSUM check (math)  -> "is this a mathematically valid ISBN?"

A string can pass the format check but fail the checksum check.
For example, "9780140328720" has the right shape (13 digits, starts
with 978) but the last digit is wrong, so the checksum will fail.
This is exactly how a typo would show up in real use.
"""

import re


ISBN10_REGEX = re.compile(r'^\d{9}[\dX]$')

ISBN13_REGEX = re.compile(r'^97[89]\d{10}$')


def _clean_isbn(isbn: str) -> str:
    if isbn is None:
        return ""
    return isbn.strip().replace("-", "").replace(" ", "")


def is_valid_isbn10_format(isbn: str) -> bool:
    cleaned = _clean_isbn(isbn)
    return bool(ISBN10_REGEX.fullmatch(cleaned))


def is_valid_isbn10_checksum(isbn: str) -> bool:
    cleaned = _clean_isbn(isbn)

    if not is_valid_isbn10_format(cleaned):
        return False

    total = 0
    for position, char in enumerate(cleaned):
        weight = 10 - position
        value = 10 if char == "X" else int(char)
        total += value * weight

    return total % 11 == 0


def is_valid_isbn10(isbn: str) -> bool:
    return is_valid_isbn10_format(isbn) and is_valid_isbn10_checksum(isbn)


def is_valid_isbn13_format(isbn: str) -> bool:
    cleaned = _clean_isbn(isbn)
    return bool(ISBN13_REGEX.fullmatch(cleaned))


def is_valid_isbn13_checksum(isbn: str) -> bool:
    cleaned = _clean_isbn(isbn)

    if not is_valid_isbn13_format(cleaned):
        return False

    total = 0
    for position, char in enumerate(cleaned):
        weight = 1 if position % 2 == 0 else 3
        total += int(char) * weight

    return total % 10 == 0


def is_valid_isbn13(isbn: str) -> bool:
    return is_valid_isbn13_format(isbn) and is_valid_isbn13_checksum(isbn)


def is_valid_isbn(isbn: str) -> bool:
    return is_valid_isbn10(isbn) or is_valid_isbn13(isbn)


if __name__ == "__main__":

    test_cases = [
        ("0140328726", True, "Valid ISBN-10 (Matilda by Roald Dahl)"),
        ("0-14-032872-6", True, "Same ISBN-10, with hyphens"),
        ("0140328720", False, "ISBN-10 with last digit changed (bad checksum)"),
        ("123456789X", True, "Valid-format ISBN-10 ending in X"),
        ("12345", False, "Too short to be any valid ISBN"),

        ("9780140328721", True, "Valid ISBN-13 (Matilda by Roald Dahl)"),
        ("978-0-14-032872-1", True, "Same ISBN-13, with hyphens"),
        ("9780140328720", False, "ISBN-13 with last digit changed (bad checksum)"),
        ("9990140328721", False, "ISBN-13 with invalid prefix (not 978/979)"),
        ("", False, "Empty string"),
    ]

    print(f"{'ISBN':<20} {'Expected':<10} {'Got':<10} {'Result':<6}  Note")
    print("-" * 80)

    all_passed = True
    for isbn, expected, note in test_cases:
        result = is_valid_isbn(isbn)
        passed = result == expected
        all_passed = all_passed and passed
        status = "PASS" if passed else "FAIL"
        print(f"{isbn!r:<20} {str(expected):<10} {str(result):<10} {status:<6}  {note}")

    print("-" * 80)
    print("All tests passed!" if all_passed else "Some tests FAILED — check the logic above.")