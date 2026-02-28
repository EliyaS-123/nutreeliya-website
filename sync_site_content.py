"""Sync local site HTML → experiment text file.

Extracts visible text from local_site/index.html and writes it to
site_content/nutreeliya_local_homepage.txt so they stay in sync.

Usage:
  python sync_site_content.py          # Extract and write
  python sync_site_content.py --diff   # Show what would change without writing

Run this after every change to local_site/index.html.
"""

import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

HTML_PATH = Path("local_site/index.html")
TEXT_PATH = Path("site_content/nutreeliya_local_homepage.txt")


def extract_text(html_path: Path) -> str:
    """Extract visible text content from the local site HTML."""
    soup = BeautifulSoup(html_path.read_text(), "html.parser")

    # Remove elements that aren't content
    for tag in soup.find_all(["script", "style", "svg", "meta", "link", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(class_=["skip-link", "mobile-menu-toggle", "hamburger-line"]):
        tag.decompose()
    for tag in soup.find_all("nav"):
        tag.decompose()
    for tag in soup.find_all("footer"):
        tag.decompose()
    # Remove decorative elements (stat badges, recipe card images, hero visual)
    for tag in soup.find_all(class_=["hero-visual", "recipe-card-image", "about-visual",
                                      "hero-stats", "hero-cta", "hero-badge",
                                      "about-stat-card", "benefit-number"]):
        tag.decompose()
    # Remove form elements
    for tag in soup.find_all("form"):
        tag.decompose()

    main = soup.find("main")
    if not main:
        raise ValueError("Could not find <main> in HTML")

    lines = []

    for section in main.find_all("section"):
        section_lines = []

        for el in section.find_all(["h1", "h2", "h3", "p", "li", "details"]):
            # Skip nested elements we've already processed
            if el.find_parent("details") and el.name != "details":
                continue

            text = el.get_text(separator=" ", strip=True)
            if not text:
                continue

            if el.name in ("h1", "h2"):
                section_lines.append(f"\n{text}\n")
            elif el.name == "h3":
                section_lines.append(f"\n{text}")
            elif el.name == "li":
                section_lines.append(f"- {text}")
            elif el.name == "details":
                summary = el.find("summary")
                answer_div = el.find(class_="faq-answer")
                if summary and answer_div:
                    q = summary.get_text(strip=True)
                    a = answer_div.get_text(separator=" ", strip=True)
                    section_lines.append(f"\nQ: {q}")
                    section_lines.append(f"A: {a}")
            elif el.name == "p":
                # Skip if parent is a details/faq-answer (handled above)
                if el.find_parent("details"):
                    continue
                # Skip section eyebrows and meta spans
                classes = el.get("class", [])
                if "section-eyebrow" in classes or "form-note" in classes:
                    continue
                section_lines.append(text)

        if section_lines:
            lines.extend(section_lines)
            lines.append("\n---")

    # Clean up: remove trailing separator, normalize whitespace
    text = "\n".join(lines).strip()
    if text.endswith("---"):
        text = text[:-3].strip()

    # Collapse multiple blank lines into max 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Add site URL at end
    text = f"NutreEliya — Nutritious Gluten-Free Recipes for Celiac and Gluten-Sensitive Diets\n\n{text}"
    text += "\n\nMore recipes and detailed guides available at: https://nutreeliya.com\n"

    return text


def main():
    if not HTML_PATH.exists():
        print(f"Error: {HTML_PATH} not found")
        sys.exit(1)

    new_text = extract_text(HTML_PATH)

    if "--diff" in sys.argv:
        if TEXT_PATH.exists():
            old_text = TEXT_PATH.read_text()
            if old_text.strip() == new_text.strip():
                print("No changes — files are in sync.")
            else:
                print(f"Files differ. New text: {len(new_text)} chars (was {len(old_text)} chars).")
                print("\n--- First 800 chars of new text ---")
                print(new_text[:800])
                print("\n--- Last 400 chars ---")
                print(new_text[-400:])
        else:
            print(f"{TEXT_PATH} does not exist yet. Would create it.")
        return

    TEXT_PATH.write_text(new_text)
    print(f"Synced: {HTML_PATH} -> {TEXT_PATH} ({len(new_text)} chars)")


if __name__ == "__main__":
    main()
