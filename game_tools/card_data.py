"""
hOCG Support Card Database
===========================
All support card definitions registered into SUPPORT_CARD_DB.
Each entry describes a card's actions, conditions, costs and metadata.

This file is auto-extracted from the original support_card_db.py for modularity.
"""

from __future__ import annotations

from .card_types import ActionType, ConditionType, CostType


# ═══════════════════════════════════════════════════════════════════════════
#  SUPPORT CARD DATABASE
# ═══════════════════════════════════════════════════════════════════════════
#
# Each entry is keyed by card_number.  Fields:
#   card_number, card_name, card_type, is_limited,
#   attachment_type  (None | "tool" | "mascot" | "fan"),
#   conditions       list of {type, ...params},
#   costs            list of {type, ...params},
#   actions          ordered list of {type, ...params},
#   passive_effects  (for attachable cards),
#   triggered_effects (for attachable cards),
#   attachment_target (for fan cards – holomen name restriction),
#   raw_text         original 能力テキスト for reference
# ═══════════════════════════════════════════════════════════════════════════

SUPPORT_CARD_DB: dict[str, dict] = {}

def _reg(entry: dict):
    """Register a card entry into the database."""
    SUPPORT_CARD_DB[entry["card_number"]] = entry


# ═══════════════════════════════════════════════════════════════════════════
#  STAFF LIMITED
# ═══════════════════════════════════════════════════════════════════════════

_reg({
    "card_number": "hSD01-016",
    "card_name": "春先のどか",
    "card_type": "サポート・スタッフ・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.DRAW, "count": 3},
    ],
    "raw_text": "自分のデッキを３枚引く。",
})

_reg({
    "card_number": "hSD01-017",
    "card_name": "マネちゃん",
    "card_type": "サポート・スタッフ・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.HAND_SIZE_GTE, "count": 1},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.SHUFFLE_HAND_DRAW, "draw_count": 5},
    ],
    "raw_text": "自分の手札がこのカードを含まずに１枚以上なければ使えない。自分の手札すべてをデッキに戻してシャッフルする。そして自分のデッキを５枚引く。",
})


# ═══════════════════════════════════════════════════════════════════════════
#  ITEM (non-LIMITED)
# ═══════════════════════════════════════════════════════════════════════════

_reg({
    "card_number": "hSD01-018",
    "card_name": "サブパソコン",
    "card_type": "サポート・アイテム",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.VIEW_DECK_TOP, "count": 5,
         "filter": {"card_type_contains": "LIMITED"},
         "pick_count": 1, "rest_to": "deck_bottom"},
    ],
    "raw_text": "自分のデッキの上から５枚を見る。その中から、LIMITEDのサポートカード１枚を公開し、手札に加える。そして残ったカードを好きな順でデッキの下に戻す。",
})

_reg({
    "card_number": "hBP01-104",
    "card_name": "ふつうのパソコン",
    "card_type": "サポート・アイテム",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_DECK_TO_STAGE, "filter": {"bloom_level": "Debut"},
         "pick_count": 1, "shuffle_after": True},
    ],
    "raw_text": "自分のデッキから、Debutホロメン１枚を公開し、ステージに出す。そしてデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP02-076",
    "card_name": "カスタムパソコン",
    "card_type": "サポート・アイテム",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.HAND_CARD_TO_DECK_BOTTOM,
         "filter": {"bloom_level": "Debut"},
         "description": "Put a Debut holomen from hand to deck bottom"},
        {"type": ActionType.SEARCH_DECK_EVOLVED,
         "filter": {"bloom_level": "1st", "exclude_buzz": True, "same_name_as_returned": True},
         "pick_count": 1, "shuffle_after": True,
         "description": "Search deck for matching non-Buzz 1st holomen"},
    ],
    "raw_text": "自分の手札のDebutホロメン1枚を公開し、デッキの下に戻す。自分のデッキから、戻したホロメンと同じカード名のBuzz以外の1stホロメン1枚を公開し、手札に加える。そしてデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP05-074",
    "card_name": "フレンドリーパソコン",
    "card_type": "サポート・アイテム",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_DECK_TO_STAGE,
         "filter": {"bloom_level": "Debut", "has_extra": "このホロメンはデッキに何枚でも入れられる"},
         "pick_count": {"min": 1, "max": 2}, "shuffle_after": True},
        {"type": ActionType.CONDITIONAL, "condition": {"picked_count_eq": 2},
         "then": [{"type": ActionType.HAND_CARD_TO_DECK_BOTTOM, "filter": {"any": True}, "count": 1}]},
    ],
    "raw_text": "自分のデッキから、エクストラ「このホロメンはデッキに何枚でも入れられる」を持つDebutホロメン1～2枚を公開し、ステージに出す。そしてデッキをシャッフルする。Debutホロメンを2枚出したなら、さらに、自分の手札1枚をデッキの下に戻す。",
})


# ═══════════════════════════════════════════════════════════════════════════
#  ITEM LIMITED
# ═══════════════════════════════════════════════════════════════════════════

_reg({
    "card_number": "hSD01-019",
    "card_name": "スゴイパソコン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [
        {"type": CostType.ARCHIVE_STAGE_CHEER, "count": 1},
    ],
    "actions": [
        {"type": ActionType.SEARCH_DECK,
         "filter": {"bloom_level": ["1st", "2nd"], "exclude_buzz": True},
         "pick_count": 1, "shuffle_after": True},
    ],
    "raw_text": "このカードは、自分のステージのエール１枚をアーカイブしなければ使えない。自分のデッキから、Buzz以外の[１stホロメンか２ndホロメン]１枚を公開し、手札に加える。そしてデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP01-102",
    "card_name": "アイドルマイク",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.HAND_SIZE_LTE, "count": 6},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.VIEW_DECK_TOP, "count": 4,
         "filter": {"tag": "#歌", "card_category": "ホロメン"},
         "pick_count": "any", "rest_to": "deck_bottom"},
    ],
    "raw_text": "自分の手札がこのカードを含まずに6枚以下でなければ使えない。自分のデッキの上から4枚を見る。その中から、#歌を持つホロメンを好きな枚数公開し、手札に加える。そして残ったカードを好きな順でデッキの下に戻す。",
})

_reg({
    "card_number": "hBP01-103",
    "card_name": "ゲーミングパソコン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [
        {"type": CostType.ARCHIVE_HOLO_POWER, "count": 1},
    ],
    "actions": [
        {"type": ActionType.SEARCH_DECK,
         "filter": {"bloom_level": ["Debut", "1st"], "exclude_buzz": True, "color": "same_as_oshi"},
         "pick_count": 1, "shuffle_after": True},
    ],
    "raw_text": "自分のホロパワー1枚をアーカイブしなければ使えない。自分のデッキから、自分の推しホロメンと同色のBuzz以外の[Debutホロメンか１stホロメン]１枚を公開し、手札に加える。そしてデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP01-105",
    "card_name": "ペンライト",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [
        {"type": CostType.ARCHIVE_HOLO_POWER, "count": 1},
    ],
    "actions": [
        {"type": ActionType.SEARCH_YELL_DECK,
         "filter": {"color": "same_as_target_holomen"},
         "pick_count": 1, "send_to": "holomen", "shuffle_after": True},
    ],
    "raw_text": "自分のホロパワー１枚をアーカイブしなければ使えない。自分のエールデッキから、自分のホロメン１人と同色のエール１枚を公開し、自分のホロメンに送る。そしてエールデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP02-075",
    "card_name": "アイドルサインペン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.HAND_SIZE_LTE, "count": 6},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.VIEW_DECK_TOP, "count": 4,
         "filter": {"tag": "#絵", "card_category": "ホロメン"},
         "pick_count": "any", "rest_to": "deck_bottom"},
    ],
    "raw_text": "自分の手札がこのカードを含まずに6枚以下でなければ使えない。自分のデッキの上から4枚を見る。その中から、#絵を持つホロメンを好きな枚数公開し、手札に加える。そして残ったカードを好きな順でデッキの下に戻す。",
})

_reg({
    "card_number": "hBP02-077",
    "card_name": "レトロパソコン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.LIFE_LTE, "count": 3},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_ARCHIVE, "filter": {"card_category": "ホロメン"},
         "pick_count": 1, "to": "hand"},
    ],
    "raw_text": "このカードは、自分のライフが3以下でなければ使えない。自分のアーカイブのホロメン１枚を手札に戻す。",
})

_reg({
    "card_number": "hBP03-084",
    "card_name": "ゴージャスパソコン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [
        {"type": CostType.ARCHIVE_HOLO_POWER, "count": 1},
    ],
    "actions": [
        {"type": ActionType.SEARCH_DECK,
         "filter": {"bloom_level": "1st", "color": "same_as_oshi"},
         "pick_count": 1, "shuffle_after": True},
    ],
    "raw_text": "自分のホロパワー1枚をアーカイブしなければ使えない。自分のデッキから、自分の推しホロメンと同色の1stホロメン1枚を公開し、手札に加える。そしてデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP03-085",
    "card_name": "スーパーパソコン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.VIEW_DECK_TOP, "count": 4,
         "filter": {"bloom_level_pair": ["Debut", "1st"]},
         "pick_count": {"per_type": 1}, "rest_to": "deck_bottom"},
    ],
    "raw_text": "自分のデッキの上から4枚を見る。その中から、[Debutホロメンと1stホロメン]1枚ずつを公開し、手札に加える。そして残ったカードを好きな順でデッキの下に戻す。",
})

_reg({
    "card_number": "hBP03-086",
    "card_name": "デュアルモニターパソコン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_DECK_TO_STAGE,
         "filter": {"bloom_level": "Debut", "has_extra": "このホロメンはデッキに何枚でも入れられる"},
         "pick_count": {"min": 1, "max": 2}, "shuffle_after": True},
    ],
    "raw_text": "自分のデッキから、エクストラ「このホロメンはデッキに何枚でも入れられる」を持つDebutホロメン1～2枚を公開し、ステージに出す。そしてデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP04-089",
    "card_name": "ツートンカラーパソコン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.TWO_DIFFERENT_COLORS_ON_STAGE},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_DECK,
         "filter": {"bloom_level": "1st", "exclude_buzz": True, "color": "same_as_selected_holomen"},
         "pick_count": 2, "pick_description": "Select 2 holomen of different single colors, search 1 matching 1st each",
         "shuffle_after": True},
    ],
    "raw_text": "自分のステージに色が1色で異なる色のホロメンが2人以上いなければ使えない。自分のステージの色が1色で異なる色のホロメン2人を選ぶ。自分のデッキから、Buzz以外のそれぞれ選んだホロメンと同色の1stホロメン1枚ずつを公開し、手札に加える。そしてデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP04-090",
    "card_name": "作業用パソコン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.HAND_SIZE_LTE, "count": 6},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.VIEW_DECK_TOP, "count": 4,
         "filter": {"pick_pair": [
             {"card_category": "ホロメン"},
             {"card_type_in": ["サポート・ツール", "サポート・マスコット", "サポート・ファン"]}
         ]},
         "pick_count": {"per_type": 1}, "rest_to": "deck_bottom"},
    ],
    "raw_text": "自分の手札がこのカードを含まずに6枚以下でなければ使えない。自分のデッキの上から4枚を見る。その中から、ホロメン1枚と[ツールかマスコットかファン]1枚を公開し、公開したカードを手札に加える。そして残ったカードを好きな順でデッキの下に戻す。",
})

_reg({
    "card_number": "hBP06-085",
    "card_name": "フェイバリットパソコン",
    "card_type": "サポート・アイテム・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_DECK,
         "filter": {"pick_triple": [
             {"bloom_level": "Debut", "same_name_pair": True},
             {"bloom_level": "Buzz", "same_name_pair": True},
             {"tag": "#Buzzグッズ", "card_category": "サポート"}
         ]},
         "pick_count": 3, "shuffle_after": True},
    ],
    "raw_text": "自分のデッキから、同じカード名の[DebutホロメンとBuzzホロメン]1枚ずつと#Buzzグッズを持つサポートカード1枚を公開し、公開したカードを手札に加える。そしてデッキをシャッフルする。",
})


# ═══════════════════════════════════════════════════════════════════════════
#  EVENT (non-LIMITED)
# ═══════════════════════════════════════════════════════════════════════════

_reg({
    "card_number": "hSD01-020",
    "card_name": "ホロリスの輪",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.ROLL_DICE, "count": 1,
         "outcomes": {
             ">=3": [{"type": ActionType.ARCHIVE_CHEER_TO_HOLOMEN, "source": "archive", "count": 1}],
         }},
    ],
    "raw_text": "サイコロを１回振る：３以上の時、自分のアーカイブのエール１枚を自分のホロメンに送る。",
})

_reg({
    "card_number": "hBP01-106",
    "card_name": "あとは任せた！",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.SWAP_OWN_CENTER_BACK, "back_condition": "not_resting"},
    ],
    "raw_text": "自分のセンターホロメンとお休みしていないバックホロメン１人を交代させる。",
})

_reg({
    "card_number": "hBP01-107",
    "card_name": "アンコール",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.ARCHIVE_TO_YELL_DECK, "count": {"min": 1, "max": 3},
         "shuffle_after": True},
    ],
    "raw_text": "自分のアーカイブのエール１～３枚をエールデッキに戻す。そしてエールデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP01-112",
    "card_name": "わくわくいたずらタイム",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.ROLL_DICE, "count": 1,
         "outcomes": {
             ">=4": [{"type": ActionType.DEAL_SPECIAL_DAMAGE,
                      "target": "opponent_back", "amount": 20,
                      "no_life_on_down": True}],
         }},
    ],
    "raw_text": "サイコロを１回振る：４以上の時、相手のバックホロメン１人に特殊ダメージ20を与える（ダウンしても相手のライフは減らない）。",
})

_reg({
    "card_number": "hBP02-079",
    "card_name": "爆発の魔法",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "per_turn_limit": {"tag": "#魔法", "category": "イベント", "limit": 1},
    "actions": [
        {"type": ActionType.DEAL_SPECIAL_DAMAGE,
         "target": "opponent_center_or_collab", "amount": 20,
         "no_life_on_down": True},
    ],
    "raw_text": "相手のセンターホロメンかコラボホロメンに特殊ダメージ20を与える。ただし、ダウンしても相手のライフは減らない。自分の#魔法を持つイベントはターンに1回しか使えない。",
})

_reg({
    "card_number": "hBP02-083",
    "card_name": "魔法のタンス",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [
        {"type": CostType.ARCHIVE_HOLO_POWER, "count": 1},
    ],
    "per_turn_limit": {"tag": "#魔法", "category": "イベント", "limit": 1},
    "actions": [
        {"type": ActionType.ARCHIVE_CHEER_TO_HOLOMEN,
         "source": "archive", "color": "紫", "count": 1,
         "target_holomen": "紫咲シオン"},
    ],
    "raw_text": "自分のホロパワー1枚をアーカイブしなければ使えない。自分のアーカイブの紫エール1枚を、自分の〈紫咲シオン〉に送る。自分の#魔法を持つイベントはターンに1回しか使えない。",
})

_reg({
    "card_number": "hBP03-087",
    "card_name": "コールアンドレスポンス",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.MOVE_CHEER, "from": "own_stage", "to": "own_holomen", "count": 1},
    ],
    "raw_text": "自分のステージのエール1枚を、自分のホロメンに付け替える。",
})

_reg({
    "card_number": "hBP03-090",
    "card_name": "ホロライブ言えるかな？",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.VIEW_DECK_TOP, "count": 4,
         "filter": {"bloom_level": "Debut"},
         "pick_count": "any", "rest_to": "deck_bottom"},
    ],
    "raw_text": "自分のデッキの上から4枚を見る。その中から、Debutホロメンを好きな枚数公開し、手札に加える。そして残ったカードを好きな順でデッキの下に戻す。",
})

_reg({
    "card_number": "hBP04-091",
    "card_name": "限界飯",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "per_turn_limit": {"card_name": "限界飯", "limit": 1},
    "actions": [
        {"type": ActionType.ARTS_COST_REDUCE, "target_holomen": "一条莉々華",
         "colorless_reduce": 1, "this_turn": True},
    ],
    "raw_text": "このターンの間、自分の〈一条莉々華〉1人のアーツに必要な無色エール-1。自分の〈限界飯〉はターンに1回しか使えない。",
})

_reg({
    "card_number": "hBP04-094",
    "card_name": "まいたけダンス",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.MOVE_CHEER, "from": "own_stage", "to": "target_holomen",
         "target_holomen": "儒烏風亭らでん", "count": {"min": 1, "max": 2}},
        {"type": ActionType.CONDITIONAL,
         "condition": {"target_cheer_gte": 3},
         "then": [{"type": ActionType.ARTS_BOOST, "target": "selected", "amount": 10, "this_turn": True}]},
    ],
    "raw_text": "自分の〈儒烏風亭らでん〉1人を選ぶ。自分のステージのエール1～2枚を、選んだホロメンに付け替えられる。その後、選んだホロメンにエールが3枚以上付いている時、このターンの間、選んだホロメンのアーツ+10。",
})

_reg({
    "card_number": "hBP05-075",
    "card_name": "牛丼",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.BATON_TOUCH_COST_REDUCE, "target": "selected_holomen",
         "reduce": 2, "this_turn": True},
        {"type": ActionType.HEAL, "target": "selected_holomen", "amount": 20},
    ],
    "raw_text": "自分のホロメン1人を選ぶ。このターンの間、選んだホロメンのバトンタッチに必要な無色エール-2。その後、選んだホロメンのHP20回復。",
})

_reg({
    "card_number": "hBP05-076",
    "card_name": "ちょこのビーフストロガノフ",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.ARTS_BOOST, "target": "selected_holomen",
         "amount": 10, "this_turn": True},
        {"type": ActionType.ARTS_BOOST, "target_holomen": "癒月ちょこ",
         "bloom_level_gte": "2nd", "amount": 10, "this_turn": True},
    ],
    "raw_text": "このターンの間、自分のステージのホロメン1人のアーツ+10。その後、このターンの間、自分のステージの2ndホロメンの〈癒月ちょこ〉1人のアーツ+10。",
})

_reg({
    "card_number": "hSD04-013",
    "card_name": "ちょこ先のお薬",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.HEAL, "target": "selected_holomen", "amount": 20},
        {"type": ActionType.CONDITIONAL,
         "condition": {"stage_has_tag": "#料理"},
         "then": [{"type": ActionType.ARTS_BOOST, "target": "selected", "amount": 20, "this_turn": True}]},
    ],
    "raw_text": "自分のホロメン1人を選ぶ。選んだホロメンのHP20回復。自分のステージに#料理を持つホロメンがいる時、さらに、このターンの間、選んだホロメンのアーツ+20。",
})

_reg({
    "card_number": "hBP06-087",
    "card_name": "しめじダンス",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.OSHI_IS, "name": "儒烏風亭らでん"},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.ARCHIVE_YELL_DECK_TOP, "count": 1},
        {"type": ActionType.SEARCH_ARCHIVE, "filter": {"card_name": "儒烏風亭らでん"},
         "pick_count": 1, "to": "hand"},
    ],
    "raw_text": "自分の推しホロメンが〈儒烏風亭らでん〉でなければ使えない。自分のエールデッキの上から1枚をアーカイブする。その後、自分のアーカイブの〈儒烏風亭らでん〉1枚を手札に戻す。",
})

_reg({
    "card_number": "hBP06-092",
    "card_name": "マヨネーズちゅっちゅっ",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.ARTS_BOOST, "target_holomen": "博衣こより",
         "amount": 30, "this_turn": True},
    ],
    "raw_text": "このターンの間、自分のステージの〈博衣こより〉1人のアーツ+30。",
})

_reg({
    "card_number": "hSD12-015",
    "card_name": "脱獄を果たした共犯者たち",
    "card_type": "サポート・イベント",
    "is_limited": False,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.ALL_STAGE_HAS_TAG, "tag": "#Advent"},
    ],
    "costs": [],
    "per_turn_limit": {"card_name": "脱獄を果たした共犯者たち", "limit": 1},
    "actions": [
        {"type": ActionType.DEAL_SPECIAL_DAMAGE, "target": "opponent_center", "amount": 20},
        {"type": ActionType.ARCHIVE_CHEER_TO_HOLOMEN, "source": "archive", "count": 1},
    ],
    "raw_text": "自分のステージのホロメン全員が#Adventでなければ使えない。相手のセンターホロメンに特殊ダメージ20を与える。その後、自分のアーカイブのエール1枚を自分のホロメンに送る。1/turn。",
})


# ═══════════════════════════════════════════════════════════════════════════
#  EVENT LIMITED – "View top 4, pick by filter" pattern (many cards)
# ═══════════════════════════════════════════════════════════════════════════

def _view_top4_by_names(card_number, card_name, names, raw_text=""):
    """Helper: standard 'hand≤6, view top 4, pick named holomen, rest bottom' pattern."""
    _reg({
        "card_number": card_number,
        "card_name": card_name,
        "card_type": "サポート・イベント・LIMITED",
        "is_limited": True,
        "attachment_type": None,
        "conditions": [
            {"type": ConditionType.HAND_SIZE_LTE, "count": 6},
        ],
        "costs": [],
        "actions": [
            {"type": ActionType.VIEW_DECK_TOP, "count": 4,
             "filter": {"card_name_in": names, "card_category": "ホロメン"},
             "pick_count": "any", "rest_to": "deck_bottom"},
        ],
        "raw_text": raw_text,
    })

def _view_top4_by_tag(card_number, card_name, tag, raw_text=""):
    """Helper: standard 'hand≤6, view top 4, pick by tag, rest bottom' pattern."""
    _reg({
        "card_number": card_number,
        "card_name": card_name,
        "card_type": "サポート・イベント・LIMITED",
        "is_limited": True,
        "attachment_type": None,
        "conditions": [
            {"type": ConditionType.HAND_SIZE_LTE, "count": 6},
        ],
        "costs": [],
        "actions": [
            {"type": ActionType.VIEW_DECK_TOP, "count": 4,
             "filter": {"tag": tag, "card_category": "ホロメン"},
             "pick_count": "any", "rest_to": "deck_bottom"},
        ],
        "raw_text": raw_text,
    })

# -- Named holomen search cards --
_view_top4_by_names("hSD01-021", "First Gravity",
    ["ときのそら", "AZKi"])
_view_top4_by_names("hBP01-109", "月と兎の物語",
    ["兎田ぺこら", "ムーナ・ホシノヴァ"])
_view_top4_by_names("hSD02-012", "いろはにほへっと あやふぶみ",
    ["白上フブキ", "大神ミオ", "百鬼あやめ"])
_view_top4_by_names("hSD03-012", "泥棒建設",
    ["猫又おかゆ", "鷹嶺ルイ", "大神ミオ", "白上フブキ", "ラプラス・ダークネス", "戌神ころね"])
_view_top4_by_names("hSD04-012", "スバちょこルーナ",
    ["大空スバル", "癒月ちょこ", "姫森ルーナ"])
_view_top4_by_names("hBP02-078", "かなた建設",
    ["天音かなた", "AZKi", "沙花叉クロヱ"])
_view_top4_by_names("hSD07-014", "不知火建設",
    ["不知火フレア", "尾丸ポルカ", "さくらみこ", "星街すいせい", "白銀ノエル"])
_view_top4_by_names("hBP05-077", "バカタレサーカス",
    ["白上フブキ", "不知火フレア", "角巻わため", "尾丸ポルカ"])

# -- Tag-based search cards --
_view_top4_by_tag("hBP01-111", "ホロライブインドネシア3期生", "#ID３期生")
_view_top4_by_tag("hBP01-113", "Promise", "#Promise")
_view_top4_by_tag("hPR-002", "ReGLOSS", "#ReGLOSS")
_view_top4_by_tag("hBP02-080", "秘密結社holoX", "#秘密結社holoX")
_view_top4_by_tag("hBP02-081", "ホロライブ インドネシア2期生", "#ID2期生")
_view_top4_by_tag("hBP02-082", "ホロライブゲーマーズ", "#ゲーマーズ")
_view_top4_by_tag("hBP02-085", "HOLOLIVE FANTASY", "#3期生")
_view_top4_by_tag("hBP03-091", "ホロライブインドネシア1期生", "#ID1期生")
_view_top4_by_tag("hBP03-092", "ホロライブ0期生", "#0期生")
_view_top4_by_tag("hBP03-093", "ホロライブ4期生", "#4期生")
_view_top4_by_tag("hBP03-094", "FPS配信", "#シューター")
_view_top4_by_tag("hBP04-092", "ねぽらぼ", "#5期生")
_view_top4_by_tag("hBP04-093", "ホロライブ2期生", "#2期生")
_view_top4_by_tag("hBP04-096", "Advent", "#Advent")
_view_top4_by_tag("hBP05-078", "晩酌配信", "#お酒")
_view_top4_by_tag("hBP06-091", "ホロライブ1期生", "#1期生")
_view_top4_by_tag("hSD10-012", "FLOW GLOW", "#FLOW GLOW")
_view_top4_by_tag("hSD13-016", "Justice", "#Justice")


# ═══════════════════════════════════════════════════════════════════════════
#  EVENT LIMITED – Other unique cards
# ═══════════════════════════════════════════════════════════════════════════

_reg({
    "card_number": "hBP01-108",
    "card_name": "じゃあ敵だね",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.SWAP_OPPONENT_CENTER_BACK},
    ],
    "raw_text": "相手のセンターホロメンとバックホロメン１人を交代させる。",
})

_reg({
    "card_number": "hBP01-110",
    "card_name": "鈍器でぶっ叩くわよ！",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.ROLL_DICE, "count": 1,
         "outcomes": {
             "<=3": [{"type": ActionType.DEAL_SPECIAL_DAMAGE,
                      "target": "opponent_holomen", "amount": 0,
                      "effect": "archive_1_cheer"}],
         },
         "alt_oshi": {
             "name": "七詩ムメイ",
             "replace_with": [{"type": ActionType.DEAL_SPECIAL_DAMAGE,
                               "target": "opponent_center", "amount": 0,
                               "effect": "archive_2_cheer",
                               "game_limit": 1}]
         }},
    ],
    "raw_text": "サイコロを１回振る：３以下の時、相手のホロメンのエール１枚をアーカイブする。◆自分の推しホロメンが〈七詩ムメイ〉の時、能力変更可能[ゲームに１回]相手のセンターホロメンのエール２枚をアーカイブする。",
})

_reg({
    "card_number": "hBP02-084",
    "card_name": "みっころね24",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.DRAW, "count": 2},
        {"type": ActionType.ROLL_DICE, "count": 1,
         "outcomes": {
             "3,5,6": [{"type": ActionType.SEARCH_DECK,
                        "filter": {"bloom_level": "Debut"},
                        "pick_count": 1, "shuffle_after": True}],
             "2,4": [{"type": ActionType.DRAW, "count": 1}],
         }},
    ],
    "raw_text": "自分のデッキを2枚引き、サイコロを1回振る：3か5か6の時、自分のデッキから、Debutホロメン1枚を手札に加える。2か4の時、自分のデッキを1枚引く。",
})

_reg({
    "card_number": "hBP03-088",
    "card_name": "凸待ち",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.LIFE_LT_OPPONENT},
        {"type": ConditionType.NO_OPPONENT_COLLAB},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.OPPONENT_MOVE_BACK_TO_COLLAB,
         "note": "Opponent chooses which back holomen to move to collab (not treated as collab action)"},
    ],
    "raw_text": "自分のライフが相手より少ない時にしか使えない。相手のコラボホロメンがいない時、相手はバックホロメン1人をコラボポジションに移動させる（移動はコラボとしては扱わない）。",
})

_reg({
    "card_number": "hBP03-089",
    "card_name": "ファンミーティング",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_DECK,
         "filter": {"card_type_contains": "ファン"},
         "pick_count": 1, "shuffle_after": True},
    ],
    "raw_text": "自分のデッキから、ファン1枚を手札に加える。そしてデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP04-095",
    "card_name": "マスコットキャッチャー",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_DECK,
         "filter": {"card_type_contains": "マスコット"},
         "pick_count": 1, "shuffle_after": True},
    ],
    "raw_text": "自分のデッキから、マスコット1枚を手札に加える。そしてデッキをシャッフルする。",
})

_reg({
    "card_number": "hBP05-079",
    "card_name": "み俺恥",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.DRAW, "count": 2},
        {"type": ActionType.CONDITIONAL,
         "condition": {"prev_turn_own_downed": True, "life_lt_opponent": True},
         "then": [{"type": ActionType.ARCHIVE_CHEER_TO_HOLOMEN,
                   "source": "archive", "count": 1}]},
    ],
    "raw_text": "自分のデッキを2枚引く。その後、直前の相手のターンに自分のホロメンがダウンしていて、自分のライフが相手のライフより少ないなら、アーカイブのエール1枚を自分のホロメン1人に送る。",
})

_reg({
    "card_number": "hBP05-080",
    "card_name": "SorAZセレブレーション",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.DRAW, "count": 2},
        {"type": ActionType.VIEW_DECK_TOP, "count": 5,
         "filter": {"bloom_level": "1st"},
         "pick_count": 1, "rest_to": "deck_bottom"},
    ],
    "raw_text": "自分のデッキを2枚引く。その後、自分のデッキの上から5枚を見る。その中から、1stホロメン1枚を手札に加える。そして残ったカードを好きな順でデッキの下に戻す。",
})

_reg({
    "card_number": "hBP06-086",
    "card_name": "愛情いっぱい召し上がれ♪",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.DRAW, "count": 1},
        {"type": ActionType.HEAL, "target": "selected_holomen", "amount": 100},
    ],
    "raw_text": "自分のデッキを1枚引く。その後、自分のホロメン1人のHP100回復。",
})

_reg({
    "card_number": "hBP06-088",
    "card_name": "ドッキリうさぎ",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.PREV_TURN_DOWNED_AND_LIFE_LT},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.OPPONENT_REST_TO_BACK,
         "target": "opponent_center_or_collab",
         "skip_next_reset": True},
    ],
    "raw_text": "直前の相手のターンに自分のホロメンがダウンしていて、自分のライフが相手より少ない時にしか使えない。相手のセンターホロメンかコラボホロメンを選ぶ。選んだホロメンをお休みさせてバックポジションに移動させる。次の相手のリセットステップでアクティブにならない。",
})

_reg({
    "card_number": "hBP06-089",
    "card_name": "ドローイングストリーム",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_YELL_DECK,
         "filter": {"any_cheer": True},
         "pick_count": 1, "send_to_tag": "#絵", "shuffle_after": True},
        {"type": ActionType.SEARCH_ARCHIVE,
         "filter": {"tag": "#絵", "card_category": "ホロメン"},
         "pick_count": 1, "to": "hand"},
    ],
    "raw_text": "自分のエールデッキから、エール1枚を自分の#絵を持つホロメンに送る。そしてエールデッキをシャッフルする。その後、自分のアーカイブの#絵を持つホロメン1枚を手札に戻す。",
})

_reg({
    "card_number": "hBP06-090",
    "card_name": "ブルームステージ",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.DRAW, "count": 2},
        {"type": ActionType.CONDITIONAL,
         "condition": {"life_lte": 4},
         "then": [{"type": ActionType.EXTRA_BLOOM,
                   "description": "Can bloom a 1st holomen (that bloomed from Debut this turn) once more using hand card"}]},
    ],
    "raw_text": "自分のデッキを2枚引く。その後、自分のライフが4以下なら、このターンにDebutからBloomした1stホロメン1人をもう1回Bloomできる。",
})

_reg({
    "card_number": "hBP06-093",
    "card_name": "山田ルイ54世",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.ALL_STAGE_HAS_TAG, "tag": "#秘密結社holoX"},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_DECK,
         "filter": {"tag": "#秘密結社holoX", "card_category": "ホロメン"},
         "pick_count": 2, "shuffle_after": True},
        {"type": ActionType.CONDITIONAL,
         "condition": {"own_cheer_lt_opponent": True},
         "then": [{"type": ActionType.YELL_DECK_TOP_TO_HOLOMEN, "count": 1}]},
    ],
    "raw_text": "自分のステージのホロメン全員が#秘密結社holoXでなければ使えない。自分のデッキから#秘密結社holoX2枚を手札に加える。シャッフル。自分のエールが相手より少ないなら、エールデッキの上から1枚をホロメンに送れる。",
})

_reg({
    "card_number": "hBP06-094",
    "card_name": "ワークアウト",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.OWN_COLLAB_EXISTS_OR_NO_OPP_COLLAB},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.ARTS_BOOST, "target": "selected_holomen",
         "amount": 20, "amount_if_buzz_or_2nd": 50, "this_turn": True},
    ],
    "raw_text": "自分のコラボホロメンがいるか、相手のコラボホロメンがいない時にしか使えない。このターンの間、自分のステージのホロメン1人のアーツ+20。そのホロメンがBuzzか2ndなら、かわりにアーツ+50。",
})

_reg({
    "card_number": "hBP06-095",
    "card_name": "IDENTIFY -AREA 15-",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.ALL_STAGE_HAS_TAG, "tag": "#ID1期生"},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.SEARCH_DECK,
         "filter": {"tag": "#ID1期生", "card_category": "ホロメン"},
         "pick_count": 2, "shuffle_after": True},
        {"type": ActionType.CONDITIONAL,
         "condition": {"yell_deck_empty": True},
         "then": [{"type": ActionType.PASSIVE_ABILITY,
                   "description": "This turn: when own #ID1期生 downs opponent center, opponent life -1"}]},
    ],
    "raw_text": "自分のステージのホロメン全員が#ID1期生でなければ使えない。自分のデッキから#ID1期生2枚を手札に加える。シャッフル。エールデッキが0枚なら、このターン#ID1期生がセンターダウンさせた時、相手ライフ-1。",
})

_reg({
    "card_number": "hBP06-096",
    "card_name": "2人あわせてラムダック！",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [],
    "costs": [],
    "actions": [
        {"type": ActionType.ARCHIVE_CHEER_TO_HOLOMEN,
         "source": "archive", "count": 1,
         "target_holomen": "角巻わため"},
        {"type": ActionType.ARCHIVE_CHEER_TO_HOLOMEN,
         "source": "archive", "count": 1,
         "target_holomen": "大空スバル"},
        {"type": ActionType.ARTS_BOOST, "target_holomen": "角巻わため",
         "amount": 20, "this_turn": True},
        {"type": ActionType.ARTS_BOOST, "target_holomen": "大空スバル",
         "amount": 20, "this_turn": True},
    ],
    "raw_text": "自分の[角巻わためと大空スバル]1人ずつを選ぶ。自分のアーカイブのエールを選んだホロメンに1枚ずつ送る。その後、このターンの間、選んだホロメンのアーツ+20。",
})

_reg({
    "card_number": "hSD10-011",
    "card_name": "WHAT'S UP!!!!! KEEEEEP GROWING!!!!!",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.ALL_STAGE_HAS_TAG, "tag": "#FLOW GLOW"},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.SEND_ARCHIVE_CHEER_SPLIT,
         "total": 3, "targets": ["center", "collab"], "max_per_target": 2},
    ],
    "raw_text": "自分のステージのホロメン全員が#FLOW GLOWでなければ使えない。自分のアーカイブのエール3枚を選び、自分のセンターホロメンとコラボホロメンに割り振って送る。ただしホロメン1人に送る枚数は2枚まで。",
})

_reg({
    "card_number": "hSD13-017",
    "card_name": "JUSTICE, JUST LIKE THAT!!!!",
    "card_type": "サポート・イベント・LIMITED",
    "is_limited": True,
    "attachment_type": None,
    "conditions": [
        {"type": ConditionType.ALL_STAGE_HAS_TAG, "tag": "#Justice"},
    ],
    "costs": [],
    "actions": [
        {"type": ActionType.RETURN_STACKED_TO_HAND,
         "target": "selected_holomen",
         "count": {"min": 1, "max": 2}},
        {"type": ActionType.ARTS_BOOST, "target": "selected",
         "amount_per_returned": 20, "this_turn": True},
    ],
    "raw_text": "自分のステージのホロメン全員が#Justiceでなければ使えない。ホロメン1人を選ぶ。重なっているホロメン1~2枚を手札に戻す。このターンの間、戻した枚数×アーツ+20。",
})


# ═══════════════════════════════════════════════════════════════════════════
#  TOOL CARDS (attachable)
# ═══════════════════════════════════════════════════════════════════════════

def _tool(card_number, card_name, arts_boost=0, passive_text="",
          conditional_holder=None, conditional_effect=None, raw_text="",
          extra_cost=None):
    """Helper to register a tool card."""
    entry = {
        "card_number": card_number,
        "card_name": card_name,
        "card_type": "サポート・ツール",
        "is_limited": False,
        "attachment_type": "tool",
        "attachment_limit": 1,
        "conditions": [],
        "costs": [] if not extra_cost else extra_cost,
        "actions": [],
        "passive_effects": [],
        "triggered_effects": [],
        "raw_text": raw_text,
    }
    if arts_boost:
        entry["passive_effects"].append(
            {"type": "arts_modifier", "amount": arts_boost})
    if conditional_holder and conditional_effect:
        entry["triggered_effects"].append({
            "condition": conditional_holder,
            "effects": conditional_effect,
        })
    if passive_text:
        entry["passive_effects"].append({"type": "text", "description": passive_text})
    _reg(entry)

_tool("hBP01-115", "星街すいせいのマイク", arts_boost=10,
     conditional_holder={"holomen": "星街すいせい", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "on_down_opponent", "effect": "send_yell_deck_top_to_self"}])
_tool("hSD02-013", "阿修羅＆羅刹", arts_boost=10,
     conditional_holder={"holomen": "百鬼あやめ", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "passive", "effect": "arts+10"}])
_tool("hBP02-086", "ホロスパークリング", arts_boost=20,
     passive_text="このツールが付いている#お酒を持たないホロメンが受けるダメージ+10。")
_tool("hBP02-087", "紫咲シオンの魔法のステッキ", arts_boost=10,
     conditional_holder={"holomen": "紫咲シオン", "bloom_gte": "1st", "position": "center"},
     conditional_effect=[{"trigger": "passive", "effect": "oshi_skill_turn_limit_2x",
                          "skill_name": "ねえ゛え゛え゛え゛え゛え゛え゛"}])
_tool("hBP02-088", "森カリオペの鎌", arts_boost=10,
     conditional_holder={"holomen": "森カリオペ", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "on_attach_from_hand", "effect": "archive_deck_top_1"}])
_tool("hBP03-095", "ホロキャップ",
     conditional_holder={"bloom_level_in": ["Debut", "Spot"]},
     conditional_effect=[{"trigger": "passive", "effect": "hp+30"},
                         {"trigger": "passive", "effect": "immune_special_damage"}])
_tool("hBP03-096", "ライフル", arts_boost=10,
     conditional_holder={"tag": "#シューター", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "passive", "effect": "special_damage_to_opponent+10"}])
_tool("hBP03-097", "リコーダー", arts_boost=10,
     conditional_holder={"holomen": "音乃瀬奏", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "on_down_opponent", "effect": "draw_1"}])
_tool("hBP04-097", "緑の試験管", arts_boost=10,
     conditional_holder={"holomen": "博衣こより", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "main_step_activate",
                          "cost": "archive_1_cheer",
                          "effect": "activate_resting_holox_holomen"}])
_tool("hBP04-098", "鍛冶ハンマー", arts_boost=10,
     conditional_holder={"tag": "#ID3期生", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "passive", "effect": "arts+10"}])
_tool("hBP04-099", "古代武器",
     conditional_holder={"holomen": "アーニャ・メルフィッサ", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "passive", "effect": "arts+10_per_古代武器_on_stage"},
                         {"trigger": "on_down_opponent_turn",
                          "cost": "archive_hand_1",
                          "effect": "return_tool_to_hand"}])
_tool("hBP01-114", "石の斧", arts_boost=20,
     passive_text="このツールが付いているホロメンがアーツを使った時、このホロメンに特殊ダメージ10を与える。",
     conditional_holder={"holomen": "アキ・ローゼンタール", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "on_self_heal", "effect": "draw_1", "per_turn": 1}])
_tool("hBP05-081", "白銀ノエルのメイス", arts_boost=10,
     conditional_holder={"holomen": "白銀ノエル", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "passive", "condition": "cheer_gte_3", "effect": "arts+20"}])
_tool("hBP05-082", "アキ・ローゼンタールの斧", arts_boost=10,
     extra_cost=[{"type": CostType.ARCHIVE_HAND_CARD, "count": 1,
                  "alt": {"type": CostType.ARCHIVE_STAGE_TOOL, "tool_name": "石の斧"}}],
     conditional_holder={"holomen": "アキ・ローゼンタール", "bloom_gte": "2nd"},
     conditional_effect=[{"trigger": "passive", "effect": "arts+40"}])
_tool("hBP05-083", "ネリッサ・レイヴンクロフトの杖", arts_boost=10,
     conditional_holder={"holomen": "ネリッサ・レイヴンクロフト", "bloom_gte": "2nd",
                         "position_in": ["center", "collab"]},
     conditional_effect=[{"trigger": "on_archive_hand_by_ability",
                          "effect": "deal_special_damage_20_to_opponent_center_or_collab",
                          "per_turn": 1}])
_tool("hBP05-084", "角巻わためのハープ", arts_boost=10,
     conditional_holder={"holomen": "角巻わため", "bloom_gte": "2nd"},
     conditional_effect=[{"trigger": "passive", "condition": "stage_has_わためいと", "effect": "arts+10"},
                         {"trigger": "on_arts_used", "effect": "send_archive_cheer_to_角巻わため"}])
_tool("hSD06-011", "ﾁｬｷ丸", arts_boost=10,
     conditional_holder={"holomen": "風真いろは", "bloom_gte": "1st"},
     conditional_effect=[{"trigger": "on_receive_damage_opponent_turn",
                          "effect": "deal_special_damage_20_to_opponent_center",
                          "no_life_on_down": True, "per_turn": 1}])
_tool("hSD10-013", "ふぐ太郎",
     passive_text="このツールが付いている#FLOW GLOWを持つホロメンのアーツ+10。",
     conditional_holder={"tag": "#FLOW GLOW"},
     conditional_effect=[{"trigger": "end_step_if_arts_used",
                          "effect": "search_deck_flow_glow_debut_or_spot_to_stage_then_return_tool"}])
_tool("hBP06-097", "カワイイスタジャン",
     conditional_holder={"bloom_level": "Buzz"},
     conditional_effect=[{"trigger": "passive", "effect": "hp+30"},
                         {"trigger": "passive", "effect": "hp_immune_opponent_main_step"}])
_tool("hBP06-098", "鬼神刀「阿修羅」", arts_boost=10,
     conditional_holder={"holomen": "百鬼あやめ"},
     conditional_effect=[{"trigger": "on_collab",
                          "condition": "self_life_1_and_no_opponent_collab",
                          "effect": "opponent_move_back_to_collab"}])
_tool("hBP06-099", "ゆび", arts_boost=10,
     passive_text="このツールを手札から〈戌神ころね〉に付けた時、自分のアーカイブの〈戌神ころね〉1枚を手札に戻せる。")


# ═══════════════════════════════════════════════════════════════════════════
#  MASCOT CARDS (attachable)
# ═══════════════════════════════════════════════════════════════════════════

def _mascot(card_number, card_name, hp_boost=0, arts_boost=0,
            conditional_holder=None, conditional_effect=None, passive_text="", raw_text=""):
    """Helper to register a mascot card."""
    entry = {
        "card_number": card_number,
        "card_name": card_name,
        "card_type": "サポート・マスコット",
        "is_limited": False,
        "attachment_type": "mascot",
        "attachment_limit": 1,
        "conditions": [],
        "costs": [],
        "actions": [],
        "passive_effects": [],
        "triggered_effects": [],
        "raw_text": raw_text,
    }
    if hp_boost:
        entry["passive_effects"].append({"type": "hp_modifier", "amount": hp_boost})
    if arts_boost:
        entry["passive_effects"].append({"type": "arts_modifier", "amount": arts_boost})
    if conditional_holder and conditional_effect:
        entry["triggered_effects"].append({
            "condition": conditional_holder,
            "effects": conditional_effect,
        })
    if passive_text:
        entry["passive_effects"].append({"type": "text", "description": passive_text})
    _reg(entry)

_mascot("hBP01-116", "うぱお", arts_boost=10,
        conditional_holder={"holomen": "天音かなた"},
        conditional_effect=[{"trigger": "on_receive_damage_opponent_turn",
                             "effect": "deal_special_damage_20_to_opponent_center", "per_turn": 1}])
_mascot("hBP01-117", "フレンド", arts_boost=10,
        conditional_holder={"holomen": "七詩ムメイ"},
        conditional_effect=[{"trigger": "on_receive_damage_opponent_turn",
                             "cost": "archive_this_mascot",
                             "effect": "damage_received-30"}])
_mascot("hBP01-118", "あん肝", hp_boost=10,
        conditional_holder={"holomen": "ときのそら"},
        conditional_effect=[{"trigger": "on_arts_use", "effect": "treat_as_white_cheer"}])
_mascot("hBP01-119", "ジョブズ", hp_boost=10,
        conditional_holder={"holomen": "アキ・ローゼンタール"},
        conditional_effect=[{"trigger": "on_arts_used", "effect": "heal_10_any_holomen"}])
_mascot("hBP01-120", "がんも", arts_boost=10,
        conditional_holder={"holomen": "鷹嶺ルイ", "position": "center"},
        conditional_effect=[{"trigger": "on_arts_used", "effect": "draw_1"}])
_mascot("hBP01-121", "Kotori",
        passive_text="センターかコラボで受けるダメージ-10。",
        conditional_holder={"holomen": "小鳥遊キアラ"},
        conditional_effect=[{"trigger": "on_bloom", "effect": "draw_1"}])
_mascot("hSD02-014", "ぽよ余", hp_boost=20,
        conditional_holder={"holomen": "百鬼あやめ"},
        conditional_effect=[{"trigger": "on_bloom", "effect": "draw_1"}])
_mascot("hSD03-013", "おかにゃん",
        passive_text="センターかコラボで受けるダメージ-10。",
        conditional_holder={"holomen": "猫又おかゆ"},
        conditional_effect=[{"trigger": "on_archive_blue_cheer",
                             "effect": "can_archive_mascot_instead"}])
_mascot("hSD04-014", "しょこら", hp_boost=20,
        conditional_holder={"holomen": "癒月ちょこ"},
        conditional_effect=[{"trigger": "on_bloom", "effect": "heal_20_self"}])
_mascot("hSD05-014", "ばんぺん", arts_boost=10,
        conditional_holder={"holomen": "轟はじめ"},
        conditional_effect=[{"trigger": "passive", "effect": "hp+20"}])
_mascot("hSD06-012", "ぽこべぇ", hp_boost=10,
        conditional_holder={"holomen": "風真いろは"},
        conditional_effect=[{"trigger": "passive", "effect": "hp+20"}])
_mascot("hBP02-089", "おるやんけ", hp_boost=20,
        conditional_holder={"holomen": "白上フブキ"},
        conditional_effect=[{"trigger": "on_collab", "effect": "draw_1"}])
_mascot("hBP02-090", "ネジマキツネ", hp_boost=20,
        conditional_holder={"holomen": "白上フブキ"},
        conditional_effect=[{"trigger": "on_down", "effect": "transfer_1_cheer_to_other"}])
_mascot("hBP02-091", "フブチュン", hp_boost=20,
        conditional_holder={"holomen": "白上フブキ"},
        conditional_effect=[{"trigger": "on_collab", "effect": "return_mascot_from_archive"}])
_mascot("hBP02-092", "フブラ", hp_boost=20,
        conditional_holder={"holomen": "白上フブキ"},
        conditional_effect=[{"trigger": "main_step_activate",
                             "cost": "archive_2_cheer",
                             "effect": "arts+50_this_turn", "per_turn": 1}])
_mascot("hBP02-093", "ミテイル", hp_boost=20,
        conditional_holder={"holomen": "白上フブキ"},
        conditional_effect=[{"trigger": "passive", "position": "back",
                             "effect": "immune_opponent_damage"}])
_mascot("hBP02-094", "Tatang", arts_boost=10,
        conditional_holder={"holomen": "パヴォリア・レイネ"},
        conditional_effect=[{"trigger": "passive", "effect": "hp+30"}])
_mascot("hBP02-095", "ドクロくん", arts_boost=10,
        conditional_holder={"holomen": "宝鐘マリン", "position": "center"},
        conditional_effect=[{"trigger": "on_bloom", "effect": "draw_1"}])
_mascot("hBP02-096", "イヌ", arts_boost=10,
        conditional_holder={"holomen": "沙花叉クロヱ"},
        conditional_effect=[{"trigger": "on_down_opponent",
                             "effect": "send_archive_cheer_to_holox_holomen"}])
_mascot("hBP02-097", "UDIN", arts_boost=10,
        conditional_holder={"holomen": "クレイジー・オリー"},
        conditional_effect=[{"trigger": "on_bloom", "effect": "draw_1_then_archive_hand_1"}])
_mascot("hBP02-098", "Death-sensei", hp_boost=20,
        conditional_holder={"holomen": "森カリオペ"},
        conditional_effect=[{"trigger": "passive", "effect": "all_arts_cheer_colorless"}])
_mascot("hBP03-098", "金時", hp_boost=20,
        conditional_holder={"holomen": "さくらみこ"},
        conditional_effect=[{"trigger": "on_collab", "effect": "draw_1"}])
_mascot("hBP03-099", "マグチ", arts_boost=10,
        conditional_holder={"holomen": "さくらみこ"},
        conditional_effect=[{"trigger": "on_collab",
                             "effect": "arts+10_center_さくらみこ_this_turn"}])
_mascot("hBP03-100", "ペロ", hp_boost=20,
        conditional_holder={"holomen_in": ["フワワ・アビスガード", "モココ・アビスガード"]},
        conditional_effect=[{"trigger": "passive", "effect": "all_arts_cheer_colorless"}])
_mascot("hBP03-101", "ビビ", hp_boost=20,
        conditional_holder={"holomen": "常闇トワ"},
        conditional_effect=[{"trigger": "passive", "effect": "special_damage_to_opponent+10"}])
_mascot("hBP03-102", "フトイヌ", arts_boost=10,
        conditional_holder={"holomen": "戌神ころね"},
        conditional_effect=[{"trigger": "on_collab", "effect": "send_archive_yellow_cheer_to_self"}])
_mascot("hBP03-103", "ホソイヌ", arts_boost=10,
        conditional_holder={"holomen": "戌神ころね"},
        conditional_effect=[{"trigger": "on_down",
                             "cost": "archive_holo_power_1",
                             "effect": "return_mascot_to_hand"}])
_mascot("hBP03-104", "Riscot", arts_boost=10,
        conditional_holder={"holomen": "アユンダ・リス"},
        conditional_effect=[{"trigger": "on_collab",
                             "effect": "transfer_stage_cheer_to_self"}])
_mascot("hBP04-100", "ココロ", hp_boost=20,
        conditional_holder={"holomen": "博衣こより"},
        conditional_effect=[{"trigger": "on_collab", "effect": "arts+10_this_turn"}])
_mascot("hBP04-101", "だいふく", arts_boost=10,
        conditional_holder={"holomen": "雪花ラミィ"},
        conditional_effect=[{"trigger": "passive", "effect": "hp+20"}])
_mascot("hBP04-102", "やめなー", arts_boost=10,
        conditional_holder={"tag": "#5期生", "bloom_gte": "1st"},
        conditional_effect=[{"trigger": "passive", "position": "back",
                             "effect": "immune_opponent_damage"}])
_mascot("hBP04-103", "カラス", arts_boost=10,
        conditional_holder={"holomen": "ラプラス・ダークネス"},
        conditional_effect=[{"trigger": "main_step_dice", "position": "collab",
                             "effect": "on_odd_move_to_back", "per_turn": 1}])
_mascot("hBP04-104", "スバルドダック", hp_boost=20,
        conditional_holder={"holomen": "大空スバル"},
        conditional_effect=[{"trigger": "passive",
                             "condition": "total_cheer_gte_10",
                             "effect": "arts+20"}])
_mascot("hBP05-085", "みこだにぇー", hp_boost=10,
        conditional_holder={"holomen": "さくらみこ"},
        conditional_effect=[{"trigger": "on_down_opponent_turn",
                             "effect": "opponent_archive_hand_1"}])
_mascot("hBP05-086", "Cilus", hp_boost=20,
        conditional_holder={"holomen": "こぼ・かなえる"},
        conditional_effect=[{"trigger": "on_opponent_back_down", "position": "center",
                             "effect": "draw_1", "per_turn": 1}])
_mascot("hBP06-100", "Chattino", hp_boost=10,
        conditional_holder={"holomen": "ラオーラ・パンテーラ", "bloom_gte": "1st"},
        conditional_effect=[{"trigger": "passive",
                             "condition": "oshi_is_ラオーラ・パンテーラ",
                             "effect": "hp+20"}])
_mascot("hBP06-101", "ムーナびと", hp_boost=20,
        conditional_holder={"holomen": "ムーナ・ホシノヴァ"},
        conditional_effect=[{"trigger": "on_deal_special_damage",
                             "effect": "send_archive_blue_cheer_to_back", "per_turn": 1}])
_mascot("hBP06-102", "えびふらいおん", hp_boost=20,
        conditional_holder={"holomen": "夏色まつり"},
        conditional_effect=[{"trigger": "on_down_opponent_turn",
                             "effect": "transfer_yellow_cheer_to_other_夏色まつり"}])
_mascot("hSD12-016", "GEOW", hp_boost=20,
        conditional_holder={"holomen": "古石ビジュー", "bloom_gte": "1st"},
        conditional_effect=[{"trigger": "on_attach",
                             "effect": "archive_stage_yell_then_search_yell_deck_to_holomen"}],
        raw_text="このマスコットが付いているホロメンのHP+20。手札から1st以上の〈古石ビジュー〉に付けた時、自分のステージのエール1枚をアーカイブできる：自分のエールデッキから、エール1枚を公開し、自分のホロメンに送る。そしてエールデッキをシャッフルする。")
_mascot("hSD13-018", "Popo", hp_boost=20,
        conditional_holder={"holomen": "ジジ・ムリン"},
        conditional_effect=[{"trigger": "passive",
                             "condition": "stacked_cards_0",
                             "effect": "arts+20"}])


# ═══════════════════════════════════════════════════════════════════════════
#  FAN CARDS (attachable, specific holomen, multiple allowed)
# ═══════════════════════════════════════════════════════════════════════════

def _fan(card_number, card_name, target_holomen, effects, passive_text="", raw_text=""):
    """Helper to register a fan card."""
    entry = {
        "card_number": card_number,
        "card_name": card_name,
        "card_type": "サポート・ファン",
        "is_limited": False,
        "attachment_type": "fan",
        "attachment_limit": None,  # unlimited per holomen
        "attachment_target": target_holomen,
        "conditions": [],
        "costs": [],
        "actions": [],
        "passive_effects": [],
        "triggered_effects": effects,
        "raw_text": raw_text,
    }
    if passive_text:
        entry["passive_effects"].append({"type": "text", "description": passive_text})
    _reg(entry)

_fan("hBP01-122", "ロゼ隊", "アキ・ローゼンタール",
     [{"trigger": "on_down_opponent_turn", "effect": "send_yell_deck_top_to_アキ・ローゼンタール"}])
_fan("hBP01-123", "野うさぎ同盟", "兎田ぺこら",
     [{"trigger": "on_dice_roll", "cost": "archive_this_fan", "effect": "reroll_all_dice"}])
_fan("hBP01-124", "開拓者", "AZKi",
     [{"trigger": "on_down_opponent_turn", "effect": "transfer_1_cheer_to_other"}])
_fan("hBP01-125", "KFP", "小鳥遊キアラ",
     [{"trigger": "on_attach_from_hand", "cost": "archive_hand_1", "effect": "draw_1"}])
_fan("hBP01-126", "座員", "尾丸ポルカ",
     [{"trigger": "on_arts_use", "effect": "treat_as_red_cheer"},
      {"trigger": "passive", "effect": "damage_received+10"}])
_fan("hBP02-099", "すこん部", "白上フブキ",
     [], passive_text="HP+10。")
_fan("hBP02-100", "白銀聖騎士団", "白銀ノエル",
     [{"trigger": "passive", "effect": "damage_received-10"}])
_fan("hBP02-101", "ミオファ", "大神ミオ",
     [{"trigger": "on_down_opponent_turn", "effect": "draw_1"}])
_fan("hBP02-102", "塩っ子", "紫咲シオン",
     [{"trigger": "passive", "effect": "arts+10"},
      {"trigger": "on_receive_damage", "effect": "archive_this_fan"}])
_fan("hBP03-105", "ルーナイト", "姫森ルーナ",
     [{"trigger": "on_receive_damage_opponent_turn",
       "cost": "archive_this_fan", "effect": "damage_received-30"}])
_fan("hBP03-106", "SSRB", "獅白ぼたん",
     [{"trigger": "on_archive_cheer", "effect": "can_archive_fan_instead"}])
_fan("hBP03-107", "35P", "さくらみこ",
     [{"trigger": "on_arts_use", "effect": "treat_as_red_cheer"},
      {"trigger": "on_down", "effect": "opponent_draw_1"}])
_fan("hBP03-108", "はあとん", "赤井はあと",
     [{"trigger": "on_dice_roll", "cost": "archive_this_fan", "effect": "reroll_all_dice"}])
_fan("hBP03-109", "Ruffians", ["フワワ・アビスガード", "モココ・アビスガード"],
     [{"trigger": "on_down_opponent_turn",
       "effect": "send_archive_blue_cheer_to_フワワ・アビスガード"}])
_fan("hBP03-110", "ろぼさー", "ロボ子さん",
     [{"trigger": "on_arts_use", "effect": "treat_as_purple_cheer"},
      {"trigger": "passive", "effect": "arts-10"}])
_fan("hBP03-111", "ころねすきー", "戌神ころね",
     [{"trigger": "passive", "effect": "baton_touch_cost-1"}])
_fan("hBP03-112", "わためいと", "角巻わため",
     [{"trigger": "on_down_opponent_turn",
       "effect": "transfer_1-2_yellow_cheer_to_other_角巻わため"}])
_fan("hBP03-113", "Risuners", "アユンダ・リス",
     [{"trigger": "on_receive_cheer", "effect": "arts+10_this_turn", "per_turn": 1}])
_fan("hSD03-014", "おにぎりゃー", "猫又おかゆ",
     [], passive_text="HP+10。")
_fan("hSD07-015", "エルフレンド", "不知火フレア",
     [], passive_text="HP+10。")
_fan("hBP04-105", "こよりの助手くん", "博衣こより",
     [{"trigger": "on_attach_from_hand_or_archive",
       "effect": "transfer_stage_cheer_to_this_holomen"}])
_fan("hBP04-106", "雪民", "雪花ラミィ",
     [{"trigger": "passive", "effect": "special_damage_to_opponent_center+10"}])
_fan("hBP05-087", "Jailbird", "ネリッサ・レイヴンクロフト",
     [{"trigger": "on_down_opponent_turn",
       "effect": "transfer_1_cheer_to_歌_holomen"}])
_fan("hBP06-103", "まつりす", "夏色まつり",
     [{"trigger": "on_dice_roll_by_oshi_or_1期生",
       "cost": "archive_this_fan",
       "effect": "treat_one_die_as_4"}])
_fan("hBP06-104", "スバ友", "大空スバル",
     [{"trigger": "on_down_opponent_turn",
       "effect": "send_yell_deck_top_to_大空スバル"}])

