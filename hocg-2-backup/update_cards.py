#!/usr/bin/env python3
"""
Incrementally updates card_database.json with new cards and downloads their images.

Usage:
    python3 update_cards.py              # Auto-detect new cards after last known ID
    python3 update_cards.py --max-id 2000  # Scan up to a specific max ID
    python3 update_cards.py --from-id 1787 # Start scanning from a specific ID
    python3 update_cards.py --redownload   # Re-download images for cards missing local files
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# Reuse parsing logic from scrape_cards
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_cards import (
    parse_card,
    build_image_index,
    fetch_page,
    BASE_URL,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CARDS_DIR = os.path.join(SCRIPT_DIR, "cards")
DB_PATH = os.path.join(SCRIPT_DIR, "card_database.json")
SITE_BASE = "https://hololive-official-cardgame.com"
CONCURRENCY = 10
EMPTY_PAGE_THRESHOLD = 20  # Stop after this many consecutive empty pages


def load_database():
    """Load existing card_database.json. Returns list of card dicts."""
    if not os.path.exists(DB_PATH):
        print(f"  No existing database found at {DB_PATH}, starting fresh.")
        return []
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_database(cards):
    """Save card list to card_database.json."""
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)


def download_image(image_url, cards_dir):
    """Download a card image using wget. Returns the local filename or None."""
    if not image_url:
        return None

    # Build full URL
    if image_url.startswith('/'):
        full_url = SITE_BASE + image_url
    elif image_url.startswith('http'):
        full_url = image_url
    else:
        full_url = SITE_BASE + '/' + image_url

    # Extract filename from URL
    filename = os.path.basename(image_url)
    local_path = os.path.join(cards_dir, filename)

    # Skip if already exists
    if os.path.exists(local_path):
        return filename

    # Download using wget
    try:
        result = subprocess.run(
            ['wget', '-q', '-O', local_path, full_url],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and os.path.exists(local_path):
            # Verify it's not an empty/error file
            if os.path.getsize(local_path) > 100:
                return filename
            else:
                os.remove(local_path)
                return None
        else:
            # Clean up partial download
            if os.path.exists(local_path):
                os.remove(local_path)
            return None
    except Exception as e:
        print(f"    [WARN] Failed to download {filename}: {e}", file=sys.stderr)
        if os.path.exists(local_path):
            os.remove(local_path)
        return None


def find_new_card_ids(existing_ids, from_id, max_id=None):
    """Scan for new card IDs beyond existing ones.
    
    Stops after EMPTY_PAGE_THRESHOLD consecutive empty pages,
    or at max_id if specified.
    """
    new_ids = []
    consecutive_empty = 0
    current_id = from_id

    print(f"  Scanning for new cards starting from ID {from_id}...")

    while True:
        if max_id and current_id > max_id:
            break

        if consecutive_empty >= EMPTY_PAGE_THRESHOLD:
            print(f"  Reached {EMPTY_PAGE_THRESHOLD} consecutive empty pages, stopping scan.")
            break

        # Fetch in small batches
        batch_end = current_id + CONCURRENCY
        if max_id:
            batch_end = min(batch_end, max_id + 1)
        batch_ids = list(range(current_id, batch_end))

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
            futures = {executor.submit(fetch_page, cid): cid for cid in batch_ids}
            results = {}
            for future in as_completed(futures):
                cid, html = future.result()
                results[cid] = html

        batch_had_card = False
        for cid in batch_ids:
            html = results.get(cid)
            if html and 'cardlist-Detail_Box_Inner' in html:
                if cid not in existing_ids:
                    new_ids.append(cid)
                    batch_had_card = True
                    consecutive_empty = 0
                else:
                    consecutive_empty = 0
            else:
                consecutive_empty += 1

        current_id = batch_end
        time.sleep(0.3)

    return new_ids


def update_cards(from_id=None, max_id=None, redownload=False):
    """Main update logic."""
    # Load existing database
    print("Loading existing database...")
    existing_cards = load_database()
    existing_ids = {c['id'] for c in existing_cards}
    max_existing_id = max(existing_ids) if existing_ids else 0
    print(f"  Found {len(existing_cards)} existing cards (max ID: {max_existing_id})")

    # Build image index
    print("Building local image index...")
    os.makedirs(CARDS_DIR, exist_ok=True)
    image_index = build_image_index(CARDS_DIR)
    print(f"  Found {sum(len(v) for v in image_index.values())} images for {len(image_index)} card numbers")

    # Determine scan range
    if from_id is None:
        from_id = max_existing_id + 1

    # Find new card IDs
    print(f"\nScanning for new cards (from ID {from_id})...")
    new_card_ids = find_new_card_ids(existing_ids, from_id, max_id)

    if not new_card_ids:
        print("\nNo new cards found.")
        if not redownload:
            return
    else:
        print(f"\nFound {len(new_card_ids)} new card(s): IDs {min(new_card_ids)}..{max(new_card_ids)}")

    # Fetch and parse new cards
    new_cards = []
    if new_card_ids:
        print(f"\nFetching and parsing {len(new_card_ids)} new cards...")
        for i, cid in enumerate(new_card_ids):
            cid_result, html = fetch_page(cid)
            if html and 'cardlist-Detail_Box_Inner' in html:
                card = parse_card(html, cid, image_index)
                if card:
                    new_cards.append(card)
                    print(f"  [{i+1}/{len(new_card_ids)}] ID {cid}: {card.get('card_number', '?')} {card.get('card_name', '?')}")
                else:
                    print(f"  [{i+1}/{len(new_card_ids)}] ID {cid}: Failed to parse")
            else:
                print(f"  [{i+1}/{len(new_card_ids)}] ID {cid}: Empty page")

            if (i + 1) % 10 == 0:
                time.sleep(0.5)

    # Download images for new cards
    if new_cards:
        print(f"\nDownloading images for {len(new_cards)} new cards...")
        downloaded = 0
        for card in new_cards:
            image_url = card.get('image_url', '')
            if image_url:
                filename = download_image(image_url, CARDS_DIR)
                if filename:
                    downloaded += 1
                    print(f"  Downloaded: {filename}")
                else:
                    print(f"  [SKIP] Could not download: {os.path.basename(image_url)}")

        print(f"  Downloaded {downloaded} images")

        # Rebuild image index after downloads
        image_index = build_image_index(CARDS_DIR)

        # Update local_images for new cards
        for card in new_cards:
            card_num = card.get('card_number', '')
            if card_num and card_num in image_index:
                card['local_images'] = sorted(image_index[card_num])
            else:
                card['local_images'] = []

    # Handle --redownload: download missing images for existing cards
    if redownload:
        print("\nChecking for missing images in existing cards...")
        missing_count = 0
        for card in existing_cards:
            image_url = card.get('image_url', '')
            if not image_url:
                continue
            filename = os.path.basename(image_url)
            local_path = os.path.join(CARDS_DIR, filename)
            if not os.path.exists(local_path):
                result = download_image(image_url, CARDS_DIR)
                if result:
                    missing_count += 1
                    print(f"  Downloaded missing: {result}")

        if missing_count:
            print(f"  Downloaded {missing_count} missing images")
            # Rebuild and update local_images
            image_index = build_image_index(CARDS_DIR)
            for card in existing_cards:
                card_num = card.get('card_number', '')
                if card_num and card_num in image_index:
                    card['local_images'] = sorted(image_index[card_num])
        else:
            print("  All images present")

    # Merge and save
    if new_cards:
        all_cards = existing_cards + new_cards
        # Sort by ID
        all_cards.sort(key=lambda c: c['id'])
        save_database(all_cards)
        print(f"\nSaved {len(all_cards)} total cards to {DB_PATH}")
        print(f"  Added {len(new_cards)} new cards")
    elif redownload:
        save_database(existing_cards)
        print(f"\nUpdated {DB_PATH} with refreshed local_images")
    else:
        print("\nNothing to update.")


def main():
    parser = argparse.ArgumentParser(
        description="Incrementally update card_database.json with new cards and download images."
    )
    parser.add_argument(
        '--from-id', type=int, default=None,
        help='Start scanning from this card ID (default: last known ID + 1)'
    )
    parser.add_argument(
        '--max-id', type=int, default=None,
        help='Maximum card ID to scan up to (default: auto-detect by scanning until empty pages)'
    )
    parser.add_argument(
        '--redownload', action='store_true',
        help='Re-download images that are missing locally for existing cards'
    )
    args = parser.parse_args()

    update_cards(
        from_id=args.from_id,
        max_id=args.max_id,
        redownload=args.redownload,
    )


if __name__ == '__main__':
    main()
