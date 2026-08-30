"""
components.py

Reusable Streamlit rendering helpers for the Book Discovery Companion.

This module ONLY renders things and reports which button (if any) the
user clicked. It never calls Open Library, never calls Gemini, and
never reads or writes any JSON file. Deciding what to DO about a
button click (call ReadingListManager.add_book(), etc.) is app.py's
job, not this module's -- that keeps this file reusable and easy to
test/reason about on its own.

This file also owns the app's visual styling (custom CSS), per the
project's rule that any custom CSS stays contained in the UI layer.
"""

from typing import List, Optional

import streamlit as st

from models.book import Book


# ---------------------------------------------------------------------------
# Visual design
# ---------------------------------------------------------------------------
# Design concept: the sidebar reads as a book's spine/cover (dark
# forest green, brass-gold lettering) and the main content area reads
# as the page (warm paper, dark ink text) -- opening the app feels a
# little like opening a book. Book cards get a slim spine-colored left
# edge, like books standing upright on a shelf.
#
# Fonts: Fraunces (a characterful literary serif) for headings/titles,
# Source Sans 3 for body text and controls, IBM Plex Mono for
# catalog-style metadata (ISBN, page counts, dates) so numbers read a
# little like a library catalog card.
#
# NOTE: this is a plain (non-f) string on purpose -- CSS is full of
# literal curly braces, and using an f-string here would require
# escaping every single one of them.
_CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Source+Sans+3:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --bd-paper: #EEEFE4;
    --bd-card: #FBFCF6;
    --bd-ink: #262A22;
    --bd-muted: #5B5F52;
    --bd-spine: #2F4A3C;
    --bd-spine-dark: #1D2E24;
    --bd-gold: #B9924F;
    --bd-hairline: #D7D6C4;
}

/* ---- Base page ("the page") ---- */
[data-testid="stAppViewContainer"] {
    background-color: var(--bd-paper);
}
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] li,
[data-testid="stAppViewContainer"] label {
    font-family: 'Source Sans 3', sans-serif;
    color: var(--bd-ink);
}
[data-testid="stAppViewContainer"] h1,
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3 {
    font-family: 'Fraunces', serif;
    color: var(--bd-spine-dark);
    font-weight: 600;
}
[data-testid="stCaptionContainer"] {
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.02em;
    color: var(--bd-muted);
}
hr {
    border: none;
    border-top: 1px solid var(--bd-hairline);
    margin: 0.6rem 0;
}

/* ---- Sidebar ("the spine") ---- */
[data-testid="stSidebar"] {
    background-color: var(--bd-spine-dark) !important;
    border-right: 3px solid var(--bd-gold);
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] label {
    color: #EFE9D8 !important;
    font-family: 'Source Sans 3', sans-serif !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-family: 'Fraunces', serif !important;
    color: var(--bd-gold) !important;
}
[data-testid="stSidebar"] hr {
    border-top: 1px solid rgba(239, 233, 216, 0.25);
}

/* ---- Inputs ---- */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    border-radius: 8px !important;
    border: 1px solid var(--bd-hairline) !important;
    background-color: var(--bd-card) !important;
    font-family: 'Source Sans 3', sans-serif !important;
}

/* ---- Buttons ---- */
[data-testid="stBaseButton-primary"] {
    background-color: var(--bd-spine) !important;
    border: 1px solid var(--bd-spine) !important;
    color: #FBFCF6 !important;
    border-radius: 8px !important;
    font-family: 'Source Sans 3', sans-serif !important;
    font-weight: 600 !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background-color: var(--bd-spine-dark) !important;
    border-color: var(--bd-spine-dark) !important;
}
[data-testid="stBaseButton-secondary"] {
    background-color: transparent !important;
    border: 1px solid var(--bd-spine) !important;
    color: var(--bd-spine) !important;
    border-radius: 8px !important;
    font-family: 'Source Sans 3', sans-serif !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background-color: rgba(47, 74, 60, 0.08) !important;
    border-color: var(--bd-spine-dark) !important;
    color: var(--bd-spine-dark) !important;
}

/* ---- Book cards ---- */
/* Targets containers created with st.container(border=True, key="bookcard_...")
   via Streamlit's stable "st-key-<key>" class convention, matched by
   substring so every book card picks up this rule regardless of its
   own unique key suffix. */
div[class*="st-key-bookcard"] {
    background-color: var(--bd-card) !important;
    border: 1px solid var(--bd-hairline) !important;
    border-left: 5px solid var(--bd-spine) !important;
    border-radius: 10px !important;
    padding: 1.1rem 1.3rem !important;
    margin-bottom: 1.1rem !important;
    box-shadow: 0 1px 3px rgba(38, 42, 34, 0.06);
}

/* ---- Per-book grouping wrapper ---- */
/* Wraps ONE book's card together with that SAME book's "Similar
   Books" / "Reading Guide" expanders (see app.py's
   render_reading_list_page). The bottom border here draws a single,
   unambiguous closing line under a book's entire section -- card
   plus any expanders -- so an expander can never be visually mistaken
   for belonging to the next book instead of the one above it. */
div[class*="st-key-bookgroup"] {
    padding-bottom: 0.6rem;
    margin-bottom: 1rem;
    border-bottom: 2px solid var(--bd-hairline);
}
div[class*="st-key-bookgroup"]:last-of-type {
    border-bottom: none;
}

.bd-cover-placeholder {
    width: 100%;
    max-width: 110px;
    aspect-ratio: 2 / 3;
    border: 1px dashed var(--bd-hairline);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.8rem;
    color: var(--bd-hairline);
    background-color: var(--bd-paper);
}

.bd-byline {
    font-style: italic;
    color: var(--bd-muted);
    margin: -0.4rem 0 0.5rem 0 !important;
    font-family: 'Source Sans 3', sans-serif;
}

.bd-status-pill {
    display: inline-block;
    padding: 0.15rem 0.65rem;
    border-radius: 999px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.6rem;
}
.bd-status-pill--want {
    background-color: transparent;
    border: 1px solid var(--bd-gold);
    color: var(--bd-gold);
}
.bd-status-pill--reading {
    background-color: var(--bd-spine);
    color: #FBFCF6;
    border: 1px solid var(--bd-spine);
}
.bd-status-pill--finished {
    background-color: var(--bd-hairline);
    color: var(--bd-muted);
    border: 1px solid var(--bd-hairline);
}

.bd-subject-tag {
    display: inline-block;
    padding: 0.1rem 0.55rem;
    margin: 0 0.3rem 0.3rem 0;
    border-radius: 999px;
    border: 1px solid var(--bd-hairline);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    color: var(--bd-muted);
    background-color: var(--bd-paper);
}

/* ---- App header ---- */
.bd-app-title {
    font-family: 'Fraunces', serif;
    font-size: 2.4rem;
    font-weight: 700;
    color: var(--bd-spine-dark);
    text-align: center;
    margin-bottom: 0.1rem;
}
.bd-app-tagline {
    font-family: 'Source Sans 3', sans-serif;
    font-style: italic;
    text-align: center;
    color: var(--bd-muted);
    margin-bottom: 0.3rem;
}
.bd-title-rule {
    border-top: 2px solid var(--bd-gold) !important;
    width: 120px;
    margin: 0.4rem auto 1.8rem auto !important;
}
"""


def inject_custom_css() -> None:
    """
    Inject the app's custom stylesheet. Safe to call on every rerun --
    Streamlit updates the same <style> element in place rather than
    stacking up duplicates, the same way st.title() doesn't duplicate
    on every rerun either.

    This is the ONLY function in the app that touches raw CSS/HTML for
    styling purposes; every other function below still renders through
    normal Streamlit widgets.
    """
    st.markdown(f"<style>{_CUSTOM_CSS}</style>", unsafe_allow_html=True)


def render_status_badge(status: str) -> None:
    """
    Render a small read-only "shelf label" pill showing a book's
    current reading status. Purely decorative/informational -- this
    does NOT let the user change the status (render_book_card's
    selectbox handles that); it just makes the current status
    glanceable at a look, separate from the control used to change it.
    """
    status_to_class = {
        "Want to Read": "bd-status-pill--want",
        "Reading": "bd-status-pill--reading",
        "Finished": "bd-status-pill--finished",
    }
    css_class = status_to_class.get(status, "bd-status-pill--want")
    st.markdown(
        f'<span class="bd-status-pill {css_class}">{status}</span>',
        unsafe_allow_html=True,
    )


def render_subject_tags(subjects: List[str], max_tags: int = 5) -> None:
    """
    Render up to `max_tags` subjects as small rounded tag pills instead
    of a plain comma-separated sentence, so categories read as
    distinct, scannable labels rather than a wall of text.
    """
    if not subjects:
        return

    tags_html = "".join(
        f'<span class="bd-subject-tag">{subject}</span>'
        for subject in subjects[:max_tags]
    )
    st.markdown(tags_html, unsafe_allow_html=True)


def render_book_card(
    book: Book,
    key_prefix: str,
    show_add: bool = False,
    show_remove: bool = False,
    show_similar: bool = False,
    show_guide: bool = False,
    show_status: bool = False,
    status_options: Optional[List[str]] = None,
) -> dict:
    """
    Render one book as a card: cover, title, author(s), and whichever
    metadata is available, followed by whichever action buttons the
    caller asked for.

    Args:
        book: The Book to display.
        key_prefix: A string that is unique to this specific card on
            the page. Streamlit requires every widget to have a unique
            key, and a page can show many book cards at once, so the
            caller is responsible for passing a prefix that won't
            collide with any other card's prefix (see app.py for how
            this is built).
        show_add: If True, show an "Add to Reading List" button.
        show_remove: If True, show a "Remove" button (only shown if
            the book actually has an ISBN -- removal isn't possible
            for books without one, since ReadingListManager removes by
            ISBN).
        show_similar: If True, show a "Find Similar Books" button.
        show_guide: If True, show a "Generate Reading Guide" button.
        show_status: If True, show a status badge plus a reading-status
            selectbox (only shown if the book actually has an ISBN --
            like Remove, status updates go through
            ReadingListManager.update_status(), which requires an ISBN
            to identify the book).
        status_options: The list of statuses to offer in the
            selectbox. The caller supplies this (rather than this
            module hard-coding it) so the allowed statuses stay
            defined in exactly one place: ReadingListManager.VALID_STATUSES.

    Returns:
        A dictionary describing what happened on THIS rerun:
            {
                "add_clicked": bool,
                "remove_clicked": bool,
                "similar_clicked": bool,
                "guide_clicked": bool,
                "selected_status": str or None,
            }
        "selected_status" is the selectbox's current value whenever
        show_status=True and the book has an ISBN (even if the user
        didn't just change it -- Streamlit selectboxes always report
        their current value). It's None whenever no status selector
        was shown at all. The caller decides what to do with it --
        this function never acts on them itself.
    """
    actions = {
        "add_clicked": False,
        "remove_clicked": False,
        "similar_clicked": False,
        "guide_clicked": False,
        "selected_status": None,
    }

    with st.container(border=True, key=f"bookcard_{key_prefix}"):
        cover_col, info_col = st.columns([1, 3], gap="medium")

        with cover_col:
            if book.cover_url:
                st.image(book.cover_url, width=110)
            else:
                st.markdown('<div class="bd-cover-placeholder">📕</div>', unsafe_allow_html=True)

        with info_col:
            st.subheader(book.title)
            st.markdown(f'<p class="bd-byline">by {book.authors_display()}</p>', unsafe_allow_html=True)

            if show_status and book.isbn:
                render_status_badge(book.status)

            meta_parts = []
            if book.publication_year:
                meta_parts.append(str(book.publication_year))
            if book.page_count:
                meta_parts.append(f"{book.page_count} pages")
            if book.isbn:
                meta_parts.append(f"ISBN {book.isbn}")
            if meta_parts:
                st.caption(" · ".join(meta_parts))
            else:
                st.caption("Some details unavailable for this edition")

            render_subject_tags(book.subjects)

            if show_status:
                if book.isbn:
                    options = status_options if status_options else ["Want to Read", "Reading", "Finished"]
                    # Fall back to the first option if the book's
                    # current status somehow isn't in the allowed
                    # list, so the selectbox never crashes.
                    current_status = book.status if book.status in options else options[0]
                    selected_status = st.selectbox(
                        "Update status",
                        options,
                        index=options.index(current_status),
                        key=f"{key_prefix}_status",
                        label_visibility="collapsed",
                    )
                    actions["selected_status"] = selected_status
                else:
                    st.caption("Status can't be tracked (no ISBN)")

        show_any_action = show_add or show_remove or show_similar or show_guide

        if show_any_action:
            st.divider()
            button_cols = st.columns(4)

            if show_add:
                if button_cols[0].button(
                    "Add to List", key=f"{key_prefix}_add", type="primary",
                    icon="➕", use_container_width=True,
                ):
                    actions["add_clicked"] = True

            if show_remove:
                if book.isbn:
                    if button_cols[1].button(
                        "Remove", key=f"{key_prefix}_remove", type="secondary",
                        icon="🗑️", use_container_width=True,
                    ):
                        actions["remove_clicked"] = True
                else:
                    button_cols[1].caption("Can't remove (no ISBN)")

            if show_similar:
                if button_cols[2].button(
                    "Similar Books", key=f"{key_prefix}_similar", type="secondary",
                    icon="🔎", use_container_width=True,
                ):
                    actions["similar_clicked"] = True

            if show_guide:
                if button_cols[3].button(
                    "Reading Guide", key=f"{key_prefix}_guide", type="secondary",
                    icon="✨", use_container_width=True,
                ):
                    actions["guide_clicked"] = True

    return actions


def render_reading_guide(guide: dict) -> None:
    """
    Render an already-generated reading guide dictionary, shaped like:
        {"summary": "...", "reading_level": "...", "questions": [...]}

    This function only displays data it's given -- it never calls
    ReadingGuideGenerator or Gemini itself.
    """
    st.markdown("**📖 Summary**")
    st.write(guide["summary"])

    st.markdown("**🎯 Suggested Reading Level**")
    st.write(guide["reading_level"])

    st.markdown("**💬 Discussion Questions**")
    questions_markdown = "\n".join(f"{i}. {q}" for i, q in enumerate(guide["questions"], start=1))
    st.markdown(questions_markdown)