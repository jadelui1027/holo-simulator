#!/usr/bin/env python3
"""
Scrapes all card details from hololive-official-cardgame.com/cardlist/?id=1..1786
and outputs a JSON file with all card fields, plus maps local card images.
"""

import json
import os
import re
import sys
import time
import glob
import urllib.request
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://hololive-official-cardgame.com/cardlist/?id={}"
CARDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cards")
OUTPUT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "card_database.json")
MAX_ID = 1786
CONCURRENCY = 10
RETRY_LIMIT = 3
DELAY_BETWEEN_BATCHES = 0.5  # seconds between batch starts


def replace_null_color(color_text):
    """Replace ◇ with 無 in color values."""
    return color_text.replace('◇', '無')

# Build local image index: card_number_base -> list of image files
# e.g. "hSD01-001" -> ["hSD01-001_OSR.png"]
def build_image_index(cards_dir):
    index = {}
    if not os.path.isdir(cards_dir):
        return index
    for fname in os.listdir(cards_dir):
        if not fname.endswith('.png'):
            continue
        # Extract the card number base (e.g., "hBP01-009" from "hBP01-009_C.png")
        # Pattern: everything before the first underscore followed by rarity/variant
        base = fname.rsplit('.', 1)[0]  # remove .png
        # The card number is the prefix before rarity suffix
        # e.g. hSD01-001_OSR -> hSD01-001
        # e.g. hBP01-032_02_C -> hBP01-032
        # e.g. hBP01-007_P_01 -> hBP01-007
        parts = base.split('_')
        card_num = parts[0]
        if card_num not in index:
            index[card_num] = []
        index[card_num].append(fname)
    return index


def fetch_page(card_id):
    """Fetch HTML for a single card page. Returns (card_id, html_string) or (card_id, None)."""
    url = BASE_URL.format(card_id)
    for attempt in range(RETRY_LIMIT):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'ja,en;q=0.9',
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                return (card_id, resp.read().decode('utf-8', errors='replace'))
        except Exception as e:
            if attempt < RETRY_LIMIT - 1:
                wait = (attempt + 1) * 2
                time.sleep(wait)
            else:
                print(f"  [FAIL] id={card_id}: {e}", file=sys.stderr)
                return (card_id, None)


def parse_oshi_skill(p_tag):
    """Parse oshi/sp oshi skill from the <p> tag into structured data.
    
    HTML format: [ホロパワー：-1]<span>skill_name</span>[timing]effect_text
    Returns dict with ホロパワー, name, effect or None.
    """
    if not p_tag:
        return None

    # Get full text for ホロパワー extraction
    full_text = p_tag.get_text(strip=True)
    
    # Extract ホロパワー cost
    hp_match = re.search(r'\[ホロパワー：-([^\]]+)\]', full_text)
    holo_power = None
    if hp_match:
        cost_str = hp_match.group(1)
        try:
            holo_power = int(cost_str)
        except ValueError:
            holo_power = cost_str  # e.g., "X" for variable cost

    # Extract skill name from <span> (direct child, not tokkou)
    span = p_tag.find('span', recursive=False)
    skill_name = span.get_text(strip=True) if span else ''

    # Extract effect: everything after the skill name span in the text
    # Remove the [ホロパワー：-X] prefix and skill name to get the rest
    effect = full_text
    if hp_match:
        effect = effect[hp_match.end():]
    if skill_name and skill_name in effect:
        effect = effect[effect.index(skill_name) + len(skill_name):]
    effect = effect.strip()

    if not skill_name and not effect:
        return None

    result = {}
    if holo_power is not None:
        result['ホロパワー'] = holo_power
    result['name'] = skill_name
    result['effect'] = effect
    return result


def parse_arts_entry(arts_div):
    """Parse a single arts div into structured data.
    
    Returns a list of art dicts with エール, name, damage, and optional effect/tokkou.
    """
    results = []
    ps = arts_div.find_all('p')
    if len(ps) < 2:
        return results

    art_p = ps[1]
    spans = art_p.find_all('span', recursive=False)
    
    for span in spans:
        art = {}
        
        # Extract エール colors from img tags (direct children, not in tokkou)
        tokkou_span = span.find('span', class_='tokkou')
        
        # Get color imgs (exclude those inside tokkou)
        all_imgs = span.find_all('img', recursive=False)
        colors = []
        for img in all_imgs:
            alt = img.get('alt', '')
            colors.append(replace_null_color(alt))
        art['エール'] = colors
        
        # Extract tokkou (bonus damage condition)
        tokkou_data = None
        if tokkou_span:
            tokkou_imgs = tokkou_span.find_all('img')
            if tokkou_imgs:
                tokkou_parts = []
                for img in tokkou_imgs:
                    alt = img.get('alt', '')
                    tokkou_parts.append(replace_null_color(alt))
                tokkou_data = '+'.join(tokkou_parts) if tokkou_parts else tokkou_span.get_text(strip=True)
            else:
                tokkou_text = tokkou_span.get_text(strip=True)
                if tokkou_text:
                    tokkou_data = tokkou_text
            tokkou_span.decompose()
        
        # Get remaining text (name + damage)
        art_text = span.get_text(strip=True)
        
        # Split name and damage - damage is the trailing number (possibly with +)
        # Use full-width space (\u3000) or regular space as separator, damage is at the end
        damage_match = re.search(r'[\s\u3000](\d+\+?)\s*$', art_text)
        if damage_match:
            art_name = art_text[:damage_match.start()].strip()
            damage_str = damage_match.group(1)
            # Convert damage to int, handle trailing +
            if damage_str.endswith('+'):
                art['damage'] = damage_str  # Keep as string with + sign
            else:
                art['damage'] = int(damage_str)
        else:
            art_name = art_text.strip()
            art['damage'] = None
        
        art['name'] = art_name
        
        if tokkou_data:
            art['tokkou'] = tokkou_data
        
        # Extract effect text after the span (condition text)
        results.append(art)
    
    # Get effect text that appears after the spans (outside <span> but inside <p>)
    # This is text content of art_p that's not inside any span
    effect_parts = []
    for child in art_p.children:
        if isinstance(child, str):
            text = child.strip()
            if text:
                effect_parts.append(text)
    
    effect_text = ' '.join(effect_parts).strip()
    if effect_text and results:
        # Attach effect to the last art entry (it describes a condition)
        results[-1]['effect'] = effect_text
    
    return results


def parse_keywords(detail_box):
    """Parse keyword abilities from keyword divs.
    
    Each keyword div has:
    - img with alt = keyword type (e.g., コラボエフェクト)
    - text after img in span = keyword name
    - text after span = keyword effect
    
    Returns list of dicts with name, type, effect.
    """
    keywords = []
    keyword_divs = detail_box.find_all('div', class_='keyword')
    
    for kw_div in keyword_divs:
        ps = kw_div.find_all('p')
        if len(ps) < 2:
            continue
        
        kw_p = ps[1]
        
        # Find all spans (each is a keyword entry)
        spans = kw_p.find_all('span', recursive=False)
        
        for span in spans:
            kw = {}
            
            # Extract keyword type from img alt
            imgs = span.find_all('img')
            if imgs:
                kw['type'] = imgs[0].get('alt', '')
            else:
                kw['type'] = ''
            
            # Extract keyword name (text in span after img)
            # Get text content excluding img
            name_text = span.get_text(strip=True)
            kw['name'] = name_text
            
            keywords.append(kw)
        
        # Get effect text (everything after the spans in the p tag)
        effect_parts = []
        found_span = False
        for child in kw_p.children:
            if hasattr(child, 'name') and child.name == 'span':
                found_span = True
                continue
            if found_span:
                if isinstance(child, str):
                    text = child.strip()
                    if text:
                        effect_parts.append(text)
                elif hasattr(child, 'get_text'):
                    text = child.get_text(strip=True)
                    if text:
                        effect_parts.append(text)
        
        effect_text = ' '.join(effect_parts).strip()
        if effect_text and keywords:
            # Attach to the last keyword from this div
            keywords[-1]['effect'] = effect_text
    
    return keywords if keywords else None


def parse_card(html, card_id, image_index):
    """Parse card details from HTML. Returns a dict or None if page is empty/invalid."""
    try:
        from bs4 import BeautifulSoup, NavigableString
    except ImportError:
        print("Error: bs4 (BeautifulSoup) is required. Install with: pip install beautifulsoup4", file=sys.stderr)
        sys.exit(1)

    soup = BeautifulSoup(html, 'html.parser')

    detail_box = soup.find('div', class_='cardlist-Detail_Box_Inner')
    if not detail_box:
        return None

    card = {'id': card_id}

    # Card image URL from the site
    img_tag = detail_box.find('div', class_='img')
    if img_tag:
        img = img_tag.find('img')
        if img:
            card['image_url'] = img.get('src', '')
            card['card_alt'] = img.get('alt', '')

    # Card name
    name_tag = detail_box.find('h1', class_='name')
    card['card_name'] = name_tag.get_text(strip=True) if name_tag else ''

    # Parse info <dl> sections
    info_div = detail_box.find('div', class_='info')
    if info_div:
        for dl in info_div.find_all('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True)
                # For color fields, extract from img alt, replace ◇ with 無
                if key == '色':
                    imgs = dd.find_all('img')
                    if imgs:
                        val = [replace_null_color(img.get('alt', '')) for img in imgs]
                    else:
                        text = dd.get_text(strip=True)
                        val = [replace_null_color(text)] if text else []
                elif key == 'タグ':
                    tags = dd.find_all('a')
                    val = [a.get_text(strip=True) for a in tags]
                    if not val:
                        text = dd.get_text(strip=True)
                        val = text.split() if text else []
                elif key == 'バトンタッチ':
                    # Count number of ◇ icons
                    imgs = dd.find_all('img')
                    val = len(imgs)
                elif key == '収録商品':
                    # Split into list of products
                    text = dd.get_text(separator='|', strip=True)
                    text = re.sub(r'\|+', '|', text).strip('|')
                    val = [p.strip() for p in text.split('|') if p.strip()]
                elif key == '能力テキスト':
                    val = dd.get_text(separator='\n', strip=True)
                elif key in ('HP', 'LIFE'):
                    text = dd.get_text(strip=True)
                    try:
                        val = int(text)
                    except (ValueError, TypeError):
                        val = text if text else None
                else:
                    val = dd.get_text(strip=True)

                card[key] = val

    # Parse arts (attacks) - structured format
    arts_divs = detail_box.find_all('div', class_='arts')
    arts_list = []
    for arts_div in arts_divs:
        arts_entries = parse_arts_entry(arts_div)
        arts_list.extend(arts_entries)
    if arts_list:
        card['arts'] = arts_list

    # Parse oshi skill (推しスキル) - structured format
    oshi_div = detail_box.find('div', class_='oshi')
    if oshi_div and 'skill' in (oshi_div.get('class') or []):
        ps = oshi_div.find_all('p')
        if len(ps) >= 2:
            skill_data = parse_oshi_skill(ps[1])
            if skill_data:
                card['oshi_skill'] = skill_data

    # Parse SP oshi skill - structured format
    sp_skill_divs = detail_box.find_all('div', class_='sp')
    for sp_div in sp_skill_divs:
        classes = sp_div.get('class', [])
        if 'skill' in classes and 'arts' not in classes:
            ps = sp_div.find_all('p')
            if len(ps) >= 2:
                label = ps[0].get_text(strip=True)
                skill_data = parse_oshi_skill(ps[1])
                if skill_data:
                    if 'SP' in label:
                        card['sp_oshi_skill'] = skill_data
                    elif label == '推しスキル':
                        card.setdefault('oshi_skill', skill_data)

    # Parse keyword abilities - structured format with name, type, effect
    kw_data = parse_keywords(detail_box)
    if kw_data:
        card['keyword'] = kw_data

    # Parse extra
    extra_div = detail_box.find('div', class_='extra')
    if extra_div:
        ps = extra_div.find_all('p')
        if len(ps) >= 2:
            card['extra'] = ps[1].get_text(strip=True)

    # Parse gift (ギフト)
    gift_div = detail_box.find('div', class_='gift')
    if gift_div:
        ps = gift_div.find_all('p')
        if len(ps) >= 2:
            card['gift'] = ps[1].get_text(strip=True)

    # Illustrator
    ill_tag = detail_box.find('p', class_='ill-name')
    if ill_tag:
        span = ill_tag.find('span')
        card['illustrator'] = span.get_text(strip=True) if span else ill_tag.get_text(strip=True)

    # Card number
    num_tag = detail_box.find('p', class_='number')
    if num_tag:
        span = num_tag.find('span')
        card['card_number'] = span.get_text(strip=True) if span else num_tag.get_text(strip=True)

    # Map local images
    card_num = card.get('card_number', '')
    if card_num and card_num in image_index:
        card['local_images'] = sorted(image_index[card_num])
    else:
        card['local_images'] = []

    # Parse products section for release date
    detail_div = detail_box.find_parent('div', class_='cardlist-Detail')
    if not detail_div:
        detail_div = BeautifulSoup(html, 'html.parser')
    products_div = detail_div.find('div', class_='cardlist-Detail_Products') if detail_div else None
    if products_div:
        products_items = products_div.find_all('div', class_='products')
        release_dates = []
        for pi in products_items:
            dl = pi.find('dl')
            if dl:
                dd = dl.find('dd')
                if dd:
                    release_dates.append(dd.get_text(strip=True))
        if release_dates:
            card['release_date'] = release_dates[0]

    return card


def main():
    print("Building local image index...")
    image_index = build_image_index(CARDS_DIR)
    print(f"  Found {sum(len(v) for v in image_index.values())} images for {len(image_index)} unique card numbers")

    all_cards = []
    total = MAX_ID
    completed = 0
    skipped = 0
    failed = 0

    print(f"\nScraping {total} card pages (concurrency={CONCURRENCY})...")

    # Process in batches to avoid overwhelming the server
    batch_size = CONCURRENCY
    for batch_start in range(1, total + 1, batch_size):
        batch_end = min(batch_start + batch_size, total + 1)
        batch_ids = list(range(batch_start, batch_end))

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
            futures = {executor.submit(fetch_page, cid): cid for cid in batch_ids}
            results = {}
            for future in as_completed(futures):
                cid, html = future.result()
                results[cid] = html

        # Parse results in order
        for cid in batch_ids:
            html = results.get(cid)
            if html is None:
                failed += 1
                completed += 1
                continue

            # Check if page has card content
            if 'cardlist-Detail_Box_Inner' not in html:
                skipped += 1
                completed += 1
                continue

            card = parse_card(html, cid, image_index)
            if card:
                all_cards.append(card)
            else:
                skipped += 1

            completed += 1

        # Progress
        pct = completed / total * 100
        print(f"\r  Progress: {completed}/{total} ({pct:.1f}%) - {len(all_cards)} cards found, {skipped} skipped, {failed} failed", end='', flush=True)

        # Small delay between batches
        if batch_start + batch_size <= total:
            time.sleep(DELAY_BETWEEN_BATCHES)

    print()

    # Write JSON
    print(f"\nWriting {len(all_cards)} cards to {OUTPUT_JSON}...")
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_cards, f, ensure_ascii=False, indent=2)

    print(f"Done! {len(all_cards)} cards written to card_database.json")
    print(f"  Skipped: {skipped}, Failed: {failed}")


if __name__ == '__main__':
    main()
