"""
app.py

Streamlit entry point for the Book Discovery Companion.

This file is the UI/coordination layer ONLY. It:
  - draws Streamlit widgets
  - calls into the existing service classes to do actual work
  - decides what to display based on what those services return

It does NOT:
  - make raw HTTP requests to Open Library
  - make raw calls to the Gemini SDK
  - build Gemini prompts
  - implement the similar-books algorithm
  - read or write any JSON file directly

All of that lives in services/*.py, exactly as designed.
"""

import os

import streamlit as st
from dotenv import load_dotenv

from models.book import Book
from services.openlibrary_client import OpenLibraryClient
from services.reading_list_manager import ReadingListManager
from services.similar_books_finder import SimilarBooksFinder
from services.reading_guide_generator import ReadingGuideGenerator
from utils.validators import is_valid_isbn
from ui.components import render_book_card, render_reading_guide, inject_custom_css


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
load_dotenv()  # loads GEMINI_API_KEY (and anything else) from .env, if present

st.set_page_config(
    page_title="Book Discovery Companion",
    page_icon="\U0001F4DA",
    layout="centered",
)

inject_custom_css()


def init_session_state() -> None:
    """
    Create one shared instance of each service and store it in
    st.session_state, so Streamlit's automatic reruns (which happen on
    every button click, every text input change, etc.) don't keep
    recreating them from scratch. Recreating ReadingListManager, for
    example, would mean re-reading reading_list.json from disk on
    every single interaction, which is wasteful and unnecessary.

    Each block below only runs ONCE per browser session, the first
    time this function is called -- after that, "if X not in
    st.session_state" is False and the existing object is reused.
    """
    if "openlibrary_client" not in st.session_state:
        st.session_state.openlibrary_client = OpenLibraryClient()

    if "reading_list_manager" not in st.session_state:
        st.session_state.reading_list_manager = ReadingListManager()

    if "similar_books_finder" not in st.session_state:
        # Reuses the same OpenLibraryClient instance rather than
        # letting SimilarBooksFinder create its own second one.
        st.session_state.similar_books_finder = SimilarBooksFinder(
            openlibrary_client=st.session_state.openlibrary_client
        )

    if "reading_guide_generator" not in st.session_state:
        # ReadingGuideGenerator creates its own GeminiClient internally
        # and already handles a missing GEMINI_API_KEY gracefully (it
        # falls back to gemini_client=None rather than raising), so
        # app.py doesn't need to duplicate any of that logic here.
        st.session_state.reading_guide_generator = ReadingGuideGenerator()

    if "search_results" not in st.session_state:
        st.session_state.search_results = []

    # Keyed by a book identifier (see get_book_key below) so that
    # similar-books results and reading guides for MULTIPLE different
    # books on the reading list page can all stay visible at once,
    # instead of the latest click overwriting everything else.
    if "similar_books_cache" not in st.session_state:
        st.session_state.similar_books_cache = {}

    if "guide_results" not in st.session_state:
        st.session_state.guide_results = {}


def get_book_key(book: Book) -> str:
    """
    Build a stable string identifier for a book, for use as a
    Streamlit widget key suffix and as a dictionary key in
    st.session_state caches (similar_books_cache, guide_results).

    This is a UI-layer convenience only -- it does not build prompts,
    does not talk to any API, and does not touch any file.

    ISBN is preferred since it's unique. Books without one fall back to
    a normalized "title + author" combination rather than title alone.
    This matters: ReadingListManager's duplicate check only rejects a
    new book when BOTH its title AND author match an existing one, so
    two different ISBN-less books that happen to share a title but
    have different authors are legitimately allowed to sit side by
    side on the reading list. A title-only fallback key would collapse
    those two distinct books into the same cache entry, causing one
    book's "Similar Books" or "Reading Guide" results to incorrectly
    appear under the other. Combining title + author mirrors the exact
    uniqueness rule the reading list itself already enforces, so this
    key is guaranteed collision-free for anything actually stored on
    the list.
    """
    if book.isbn:
        return book.isbn

    normalized_title = "-".join(book.title.strip().lower().split())
    normalized_author = "-".join(book.authors_display().strip().lower().split())
    return f"title-{normalized_title}-by-{normalized_author}"


# ---------------------------------------------------------------------------
# Search Books page
# ---------------------------------------------------------------------------
def render_search_page() -> None:
    st.header("Search Books")
    st.caption("Look up a title, an author, or a specific ISBN.")

    with st.form("search_form"):
        form_cols = st.columns([1, 2])
        search_type = form_cols[0].selectbox("Search by", ["Title", "Author", "ISBN"])
        query = form_cols[1].text_input("Enter your search", placeholder="e.g. Matilda")
        submitted = st.form_submit_button("🔍 Search", type="primary", use_container_width=True)

    if submitted:
        cleaned_query = query.strip()

        if not cleaned_query:
            st.warning("Please enter something to search for.")
        elif search_type == "ISBN" and not is_valid_isbn(cleaned_query):
            st.error("That doesn't look like a valid ISBN-10 or ISBN-13. "
                      "Please check the number and try again.")
        else:
            client = st.session_state.openlibrary_client

            with st.spinner("Searching Open Library..."):
                if search_type == "Title":
                    results = client.search_by_title(cleaned_query)
                elif search_type == "Author":
                    results = client.search_by_author(cleaned_query)
                else:  # ISBN
                    single_result = client.search_by_isbn(cleaned_query)
                    results = [single_result] if single_result else []

            st.session_state.search_results = results

            if not results:
                st.info("No books found for that search. Try a different title, "
                         "author, or ISBN.")

    if st.session_state.search_results:
        st.subheader(f"Results ({len(st.session_state.search_results)})")

        for index, book in enumerate(st.session_state.search_results):
            key_prefix = f"search_{index}_{get_book_key(book)}"
            actions = render_book_card(book, key_prefix=key_prefix, show_add=True)

            if actions["add_clicked"]:
                added = st.session_state.reading_list_manager.add_book(book)
                if added:
                    st.success(f"Added '{book.title}' to your reading list.")
                else:
                    st.info(f"'{book.title}' is already on your reading list.")


# ---------------------------------------------------------------------------
# My Reading List page
# ---------------------------------------------------------------------------
def render_reading_list_page() -> None:
    st.header("My Reading List")

    manager = st.session_state.reading_list_manager
    books = manager.get_all_books()

    if not books:
        st.info("📭 Your reading list is empty. Head to **Search Books** to find "
                 "something to add.")
        return

    st.caption(f"{len(books)} book{'s' if len(books) != 1 else ''} on your list")

    for book in books:
        book_key = get_book_key(book)
        # No list index in this key: book_key alone is guaranteed
        # unique for anything on the reading list (see get_book_key's
        # docstring), so every book's widgets and cache entries stay
        # correctly attached to it even if the list is reordered or
        # shrinks after a removal.
        key_prefix = f"list_{book_key}"

        # Everything about THIS book -- its card, its status/remove
        # handling, and both of its possible expanders -- lives inside
        # ONE shared container. This is what guarantees a book's
        # "Similar Books" / "Reading Guide" expanders are visually
        # grouped with THAT book and never mistaken for belonging to
        # the next book in the list (see ui/components.py's CSS for
        # the matching "bookgroup" boundary styling).
        with st.container(key=f"bookgroup_{book_key}"):
            actions = render_book_card(
                book,
                key_prefix=key_prefix,
                show_remove=True,
                show_similar=True,
                show_guide=True,
                show_status=True,
                status_options=ReadingListManager.VALID_STATUSES,
            )

            if actions["selected_status"] is not None and actions["selected_status"] != book.status:
                status_changed = manager.update_status(book.isbn, actions["selected_status"])
                if status_changed:
                    st.success(f"Updated '{book.title}' to \"{actions['selected_status']}\".")
                    st.rerun()
                else:
                    st.error(f"Could not update the status for '{book.title}'.")

            if actions["remove_clicked"]:
                # render_book_card() only shows the Remove button when
                # book.isbn is set, so this branch only runs for books
                # that CAN actually be removed by ReadingListManager.
                removed = manager.remove_book(book.isbn)
                if removed:
                    st.success(f"Removed '{book.title}' from your reading list.")
                    st.rerun()
                else:
                    st.warning(f"Could not find '{book.title}' to remove.")

            if actions["similar_clicked"]:
                with st.spinner("Finding similar books..."):
                    similar_books = st.session_state.similar_books_finder.find_similar_books(book)
                st.session_state.similar_books_cache[book_key] = similar_books

            if book_key in st.session_state.similar_books_cache:
                similar_books = st.session_state.similar_books_cache[book_key]
                with st.expander(f"🔎 Similar to '{book.title}'", expanded=True):
                    if similar_books:
                        for similar_index, similar_book in enumerate(similar_books):
                            render_book_card(
                                similar_book,
                                key_prefix=f"similar_{book_key}_{similar_index}",
                            )
                    else:
                        st.info("No similar books were found. This can happen if the "
                                  "book has no recognized subjects, or if Open Library "
                                  "has no other books listed under its subjects.")

            if actions["guide_clicked"]:
                with st.spinner("Generating reading guide with Gemini..."):
                    result = st.session_state.reading_guide_generator.generate_guide(book)
                st.session_state.guide_results[book_key] = result

            if book_key in st.session_state.guide_results:
                result = st.session_state.guide_results[book_key]
                with st.expander(f"✨ Reading guide for '{book.title}'", expanded=True):
                    if result["success"]:
                        if result.get("from_cache"):
                            st.caption("Loaded from a previously saved guide.")
                        render_reading_guide(result["guide"])
                    else:
                        st.error(result["error"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    init_session_state()

    st.markdown('<div class="bd-app-title">\U0001F4DA Book Discovery Companion</div>', unsafe_allow_html=True)
    st.markdown('<div class="bd-app-tagline">Find your next great read, and keep track of the ones you\'re already on.</div>', unsafe_allow_html=True)
    st.markdown('<hr class="bd-title-rule">', unsafe_allow_html=True)

    st.sidebar.markdown("### \U0001F4DA The Library")
    page = st.sidebar.radio("Navigate", ["Search Books", "My Reading List"], label_visibility="collapsed")
    st.sidebar.markdown("---")
    book_count = len(st.session_state.reading_list_manager)
    st.sidebar.caption(f"{book_count} book{'s' if book_count != 1 else ''} on your shelf")

    if page == "Search Books":
        render_search_page()
    else:
        render_reading_list_page()


if __name__ == "__main__":
    main()