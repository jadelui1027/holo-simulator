# hOCG Card Database Scraper

Scrapes card data from the [hololive OFFICIAL CARD GAME card list](https://hololive-official-cardgame.com/cardlist/) and saves it as structured JSON with local card images.

## Requirements

- Python 3.8+
- [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/) — `pip install beautifulsoup4`
- `wget` (for image downloads in `update_cards.py`)

## Files

| File | Description |
|---|---|
| `scrape_cards.py` | Full scrape of all cards (IDs 1–1786). Outputs `card_database.json` |
| `update_cards.py` | Incremental update — finds new cards, downloads images, appends to `card_database.json` |
| `card_database.json` | The output database (array of card objects) |
| `cards/` | Directory of locally downloaded card images (`.png`) |

## Usage

### Full Scrape

Scrapes all card pages and writes `card_database.json`:

```bash
python3 scrape_cards.py
```

This fetches every page from `https://hololive-official-cardgame.com/cardlist/?id=1` to `?id=1786` with concurrency=10. Takes several minutes.

### Incremental Update

After the initial scrape, use this to add newly released cards:

```bash
# Auto-detect new cards (scans from last known ID + 1)
python3 update_cards.py

# Scan up to a specific max ID
python3 update_cards.py --max-id 2000

# Start scanning from a specific ID
python3 update_cards.py --from-id 1787

# Also re-download any missing images for existing cards
python3 update_cards.py --redownload
```

The update script:
1. Loads the existing `card_database.json`
2. Scans new page IDs starting after the last known ID
3. Stops after 20 consecutive empty pages (or at `--max-id`)
4. Parses new cards and downloads their images to `cards/` via `wget`
5. Appends new cards to `card_database.json`

---

## JSON Schema

Each card is an object in the top-level array. Fields are **present only when applicable** — for example, a Support card won't have `arts` or `HP`.

### Common Fields (all cards)

| Field | Type | Source | Description |
|---|---|---|---|
| `id` | `number` | URL parameter `?id=N` | Internal page ID on the website |
| `card_number` | `string` | `<p class="number"><span>` | Card number (e.g. `"hSD01-001"`) |
| `card_name` | `string` | `<h1 class="name">` | Card name |
| `card_alt` | `string` | `<img alt="...">` in card image | Alt text of the card image |
| `カードタイプ` | `string` | `<dt>カードタイプ</dt><dd>` | Card type: `推しホロメン`, `ホロメン`, `Buzzホロメン`, `サポート・スタッフ・LIMITED`, etc. |
| `レアリティ` | `string` | `<dt>レアリティ</dt><dd>` | Rarity: `C`, `U`, `R`, `RR`, `OSR`, `OUR`, `UR`, `SR`, `SEC`, `HR`, etc. |
| `収録商品` | `string[]` | `<dt>収録商品</dt><dd>` | Product(s) this card appears in. Parsed from `<br>`-separated text |
| `image_url` | `string` | `<div class="img"><img src="...">` | Image path on the website (relative to `https://hololive-official-cardgame.com`) |
| `local_images` | `string[]` | Matched from `cards/` directory | Local image filenames matching this card number (may include multiple rarity variants) |

### Holo Member Fields (ホロメン / Buzzホロメン)

| Field | Type | Source | Description |
|---|---|---|---|
| `色` | `string[]` | `<dt>色</dt><dd><img alt="...">` | Colors from `<img>` alt text. `◇` is replaced with `無`. e.g. `["白"]`, `["白", "緑"]` |
| `タグ` | `string[]` | `<dt>タグ</dt><dd><a>` | Tags as array. e.g. `["#JP", "#0期生", "#歌"]` |
| `HP` | `number` | `<dt>HP</dt><dd>` | Hit points |
| `Bloomレベル` | `string` | `<dt>Bloomレベル</dt><dd>` | Bloom level: `Debut`, `1st`, `2nd`, `Spot` |
| `バトンタッチ` | `number` | `<dt>バトンタッチ</dt><dd>` | Baton pass cost — **count of `<img>` icons** (each icon = 1 colorless energy) |
| `arts` | `object[]` | `<div class="sp arts">` | Attack list (see [Arts](#arts) below) |
| `keyword` | `object[]` | `<div class="keyword">` | Keyword abilities (see [Keyword](#keyword) below) |
| `extra` | `string` | `<div class="extra"><p>` (2nd `<p>`) | Extra text (e.g. Buzz penalty) |

### Oshi Holo Member Fields (推しホロメン)

| Field | Type | Source | Description |
|---|---|---|---|
| `色` | `string[]` | `<dt>色</dt><dd><img alt="...">` | Colors (same as above) |
| `LIFE` | `number` | `<dt>LIFE</dt><dd>` | Life points |
| `oshi_skill` | `object` | `<div class="oshi skill"><p>` (2nd `<p>`) | Oshi skill (see [Oshi Skill](#oshi-skill) below) |
| `sp_oshi_skill` | `object` | `<div class="sp skill"><p>` (2nd `<p>`) | SP oshi skill (same structure) |

### Support Card Fields (サポート)

| Field | Type | Source | Description |
|---|---|---|---|
| `能力テキスト` | `string` | `<dt>能力テキスト</dt><dd>` | Ability text (newline-separated) |

### Optional Fields

| Field | Type | Source | Description |
|---|---|---|---|
| `illustrator` | `string` | `<p class="ill-name"><span>` | Illustrator name |
| `release_date` | `string` | `<div class="cardlist-Detail_Products"><dl><dd>` | Release date from the product section (if available) |
| `gift` | `string` | `<div class="gift"><p>` (2nd `<p>`) | Gift text (if present) |

---

## Structured Sub-Objects

### Arts

Each entry in the `arts` array represents one attack:

```json
{
  "エール": ["白", "無"],
  "name": "ドリームライブ",
  "damage": 50,
  "tokkou": "青+50",
  "effect": "自分のステージにホロメンの〈AZKi〉がいる時、このアーツ+50。"
}
```

| Field | Type | Source | Description |
|---|---|---|---|
| `エール` | `string[]` | `<img alt="...">` icons inside `<span>` (excluding tokkou) | Required energy colors. `◇` → `無`. Values: `白`, `赤`, `青`, `緑`, `紫`, `黄`, `無` |
| `name` | `string` | Text content inside `<span>` (before damage number) | Attack name |
| `damage` | `number` or `string` or `null` | Trailing number in `<span>` text | Damage value. Integer for fixed, string with `+` suffix (e.g. `"60+"`) for variable |
| `tokkou` | `string` | `<span class="tokkou"><img alt="...">` | *(optional)* Bonus damage condition icon alt text (e.g. `"青+50"`) |
| `effect` | `string` | Text after `</span>` inside the same `<p>` | *(optional)* Effect description text |

**How arts are parsed:** Each `<div class="sp arts">` contains a `<p>` with `<span>` elements. Inside each `<span>`:
- `<img>` tags (not inside `<span class="tokkou">`) provide the エール colors
- `<span class="tokkou">` contains bonus damage icons (extracted as `tokkou`)
- The remaining text is split into `name` (all text before the trailing number) and `damage` (the trailing number)
- Text after the `</span>` but still inside `<p>` becomes the `effect`

### Oshi Skill

Both `oshi_skill` and `sp_oshi_skill` share this structure:

```json
{
  "ホロパワー": 1,
  "name": "リプレイスメント",
  "effect": "[ターンに１回]自分のステージのエール１枚を、自分のホロメンに付け替える。"
}
```

| Field | Type | Source | Description |
|---|---|---|---|
| `ホロパワー` | `number` or `string` | `[ホロパワー：-N]` prefix in text | Holo Power cost. Integer, or string `"X"` for variable cost |
| `name` | `string` | `<span>` inside the 2nd `<p>` | Skill name |
| `effect` | `string` | Text after `</span>` in the 2nd `<p>` | Skill effect (includes timing like `[ターンに１回]` or `[ゲームに１回]`) |

**How oshi skills are parsed:** The `<div class="oshi skill">` (or `<div class="sp skill">`) has two `<p>` tags — the 1st is the label, the 2nd contains the skill. From the 2nd `<p>`:
- `[ホロパワー：-N]` is extracted via regex for the cost
- `<span>` text gives the skill name
- Everything after the name is the effect

### Keyword

Each entry in the `keyword` array:

```json
{
  "type": "コラボエフェクト",
  "name": "堕ちた天使",
  "effect": "相手のセンターホロメンに特殊ダメージ50を与える。"
}
```

| Field | Type | Source | Description |
|---|---|---|---|
| `type` | `string` | `<img alt="...">` inside `<span>` | Keyword type from the icon's alt text (e.g. `コラボエフェクト`) |
| `name` | `string` | Text content of `<span>` (after the `<img>`) | Keyword ability name |
| `effect` | `string` | Text after `</span>` inside the same `<p>` | *(optional)* Effect description |

**How keywords are parsed:** `<div class="keyword">` has a `<p>` with `<span>` elements. Inside each `<span>`, an `<img>` tag's `alt` gives the keyword type, and the text gives the name. Text after the `</span>` is the effect.

---

## Example Cards

### 推しホロメン (Oshi Holo Member)

```json
{
  "id": 1,
  "image_url": "/wp-content/images/cardlist/hSD01/hSD01-001_OSR.png",
  "card_alt": "ときのそら",
  "card_name": "ときのそら",
  "カードタイプ": "推しホロメン",
  "レアリティ": "OSR",
  "収録商品": ["スタートデッキ「ときのそら＆AZKi」"],
  "色": ["白"],
  "LIFE": 5,
  "oshi_skill": {
    "ホロパワー": 1,
    "name": "リプレイスメント",
    "effect": "[ターンに１回]自分のステージのエール１枚を、自分のホロメンに付け替える。"
  },
  "sp_oshi_skill": {
    "ホロパワー": 2,
    "name": "じゃあ敵だね？",
    "effect": "[ゲームに１回]相手のセンターホロメンとバックホロメン１人を交代させる。その後、このターンの間、自分の白センターホロメンのアーツ+50。"
  },
  "illustrator": "でいりー",
  "card_number": "hSD01-001",
  "local_images": ["hSD01-001_OSR.png"]
}
```

### ホロメン (Holo Member with Arts + Keyword + Tokkou)

```json
{
  "id": 45,
  "card_number": "hBP01-014",
  "card_name": "天音かなた",
  "カードタイプ": "ホロメン",
  "タグ": ["#JP", "#4期生", "#歌"],
  "レアリティ": "RR",
  "色": ["白"],
  "HP": 200,
  "Bloomレベル": "2nd",
  "バトンタッチ": 2,
  "arts": [
    {
      "エール": ["白", "白", "白"],
      "name": "♰漆黒の翼♰",
      "damage": 100,
      "tokkou": "赤+50",
      "effect": "このアーツで相手のホロメンをダウンさせた時、与えたダメージが残りHPを50以上オーバーしていれば、相手のライフ-１。"
    }
  ],
  "keyword": [
    {
      "type": "コラボエフェクト",
      "name": "堕ちた天使",
      "effect": "相手のセンターホロメンに特殊ダメージ50を与える。"
    }
  ],
  "local_images": ["hBP01-014_RR.png", "hBP01-014_UR.png"]
}
```

### サポート (Support Card)

```json
{
  "id": 16,
  "card_number": "hSD01-016",
  "card_name": "春先のどか",
  "カードタイプ": "サポート・スタッフ・LIMITED",
  "レアリティ": "C",
  "収録商品": [
    "ブースターパック「ブルーミングレディアンス」",
    "スタートデッキ「ときのそら＆AZKi」"
  ],
  "能力テキスト": "自分のデッキを３枚引く。\nLIMITED：ターンに１枚しか使えない。",
  "illustrator": "Yoshimo",
  "local_images": ["hSD01-016_02_C.png", "hSD01-016_C.png", "hSD01-016_P.png", "hSD01-016_P_02.png"]
}
```

---

## Data Source

All card data is scraped from:

```
https://hololive-official-cardgame.com/cardlist/?id={1..N}
```

Each page contains a `<div class="cardlist-Detail_Box_Inner">` with all card fields parsed from the HTML `<dl>`/`<dt>`/`<dd>` structure, arts `<div>`s, keyword `<div>`s, and skill `<div>`s.

Card images are downloaded from the same domain using the `image_url` path (e.g. `wget https://hololive-official-cardgame.com/wp-content/images/cardlist/hBP04/hBP04-001_OSR.png`).

The `local_images` array is built by matching filenames in the `cards/` directory to the card number prefix (e.g. `hBP01-014` matches both `hBP01-014_RR.png` and `hBP01-014_UR.png`).



## SERVER RUN
source .venv/bin/activate && python -m uvicorn game_tools.server:app --host 0.0.0.0 --port 8000

open 2 browser go to 

localhost:8000/client/index.html