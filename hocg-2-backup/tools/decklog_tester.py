#!/usr/bin/env python3
"""Standalone decklog parsing tester.
Fetches deck pages from decklog.bushiroad.com and parses card numbers using
heuristics similar to playmat_manager._parse_deck_html. Also parses local
sample HTML files in sample_web_code/ for verification.
"""
import re
import json
import urllib.request
import sys
import os
import difflib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, 'card_database.json')
SAMPLES = [
    os.path.join(ROOT, 'sample_web_code', 'decklog_page_html_sample_3P552.html'),
    os.path.join(ROOT, 'sample_web_code', 'decklog_page_html_sample_6QCNY.html'),
]


def load_db():
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        db = json.load(f)
    index_by_id = {}
    index_by_num = {}
    for cd in db:
        cid = cd.get('id')
        if cid is not None:
            index_by_id[str(cid)] = cd
        num = cd.get('card_number')
        if num:
            index_by_num[num] = cd
    return db, index_by_id, index_by_num


def _parse_deck_html(html: str, card_db) -> list:
    # prefer BeautifulSoup if available
    counts = {}
    # 1) id links
    id_matches = re.findall(r"cardlist(?:/|\\)?\\?id=(\\d+)", html)
    idx_by_id = {str(cd.get('id')): cd for cd in card_db if cd.get('id') is not None}
    if id_matches and idx_by_id:
        for mid in id_matches:
            if mid in idx_by_id:
                cn = idx_by_id[mid].get('card_number')
                if cn:
                    counts[cn] = counts.get(cn, 0) + 1

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        card_nums = {cd.get('card_number') for cd in card_db if cd.get('card_number')}
        for div in soup.find_all('div', class_=lambda c: c and 'card-item' in c):
            title = None
            img = div.find('img')
            if img and img.has_attr('title'):
                title = img['title']
            if not title:
                span_with_title = div.find(lambda tag: tag.has_attr('title'))
                if span_with_title:
                    title = span_with_title.get('title')
            if not title:
                continue
            parts = title.split(':', 1)
            if not parts:
                continue
            candidate = parts[0].strip()
            if not candidate or candidate not in card_nums:
                continue
            q = 1
            num_span = div.find('span', class_='num')
            if num_span:
                try:
                    q = int(num_span.get_text(strip=True))
                except Exception:
                    q = 1
            counts[candidate] = counts.get(candidate, 0) + q
    except Exception:
        # regex fallback
        card_nums = {cd.get('card_number') for cd in card_db if cd.get('card_number')}
        for bm in re.finditer(r'<div[^>]+class=["\'][^"\']*card-item[^"\']*["\'][^>]*>(.*?)</div>\s*</div>', html, flags=re.S):
            block = bm.group(1)
            title_m = re.search(r'<img[^>]+title=["\']([^"\']+)["\']', block)
            if not title_m:
                title_m = re.search(r'<span[^>]+title=["\']([^"\']+)["\']', block)
            if not title_m:
                continue
            t = title_m.group(1)
            parts = t.split(':', 1)
            if not parts:
                continue
            candidate = parts[0].strip()
            if not candidate or candidate not in card_nums:
                continue
            q = 1
            nm = re.search(r'<span[^>]+class=["\']num["\'][^>]*>(\d+)</span>', block)
            if nm:
                try:
                    q = int(nm.group(1))
                except Exception:
                    q = 1
            counts[candidate] = counts.get(candidate, 0) + q

    # alt text fuzzy matching
    name_to_nums = {}
    names = []
    for cd in card_db:
        name = cd.get('card_name', '')
        num = cd.get('card_number', '')
        if not name or not num:
            continue
        lname = name.strip().lower()
        name_to_nums.setdefault(lname, []).append(num)
        names.append(lname)

    alt_texts = re.findall(r'<img[^>]+alt=["\']([^"\']+)["\']', html)
    for alt in alt_texts:
        token = alt.strip().lower()
        if not token:
            continue
        for known in names:
            if known in token or token in known:
                for num in name_to_nums.get(known, []):
                    counts[num] = counts.get(num, 0) + 1
        try:
            matches = difflib.get_close_matches(token, names, n=3, cutoff=0.78)
        except Exception:
            matches = []
        for m in matches:
            for num in name_to_nums.get(m, []):
                counts[num] = counts.get(num, 0) + 1

    # direct occurrences
    for cd in card_db:
        cn = cd.get('card_number', '')
        if not cn:
            continue
        c = html.count(cn)
        if c:
            counts[cn] = counts.get(cn, 0) + c

    if not counts:
        raise ValueError('No matching card numbers or names found in provided HTML')

    deck_list = []
    for cn, c in counts.items():
        deck_list.extend([cn] * c)
    return deck_list


def load_deck_from_decklog(code, card_db):
    url = f'https://decklog.bushiroad.com/view/{code}'
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'text/html'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    deck = _parse_deck_html(html, card_db)
    return deck


if __name__ == '__main__':
    db, by_id, by_num = load_db()
    codes = ['11QBS', '2QKVA', '6QUSY', '12CS8', '7M4A4']

    print('--- Local sample parsing ---')
    for path in SAMPLES:
        if not os.path.exists(path):
            print('Missing sample', path)
            continue
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        try:
            deck = _parse_deck_html(html, db)
            from collections import Counter
            ctr = Counter(deck)
            print(f"{os.path.basename(path)}: parsed {len(deck)} entries, {len(ctr)} unique")
            for k,v in ctr.most_common(8):
                print(f"  {k} x{v}")
        except Exception as e:
            print('ERROR parsing', path, e)

    print('\n--- Remote deck codes ---')
    for c in codes:
        try:
            deck = load_deck_from_decklog(c, db)
            print(f"{c}: parsed {len(deck)} entries, unique {len(set(deck))}")
            from collections import Counter
            ctr = Counter(deck)
            for k,v in ctr.most_common(6):
                print(f"  {k} x{v}")
        except Exception as e:
            print(f"{c}: ERROR {e}")
