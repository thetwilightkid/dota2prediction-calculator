# Local, self-contained copy of config.py's TEAM_CANONICAL - the prediction/
# folder is fully independent of the parent dota2_fantasy_fetch_2026 root
# (which is reserved for the fantasy-stats calculator). Static data, copied
# once rather than imported live.

TEAM_CANONICAL = {
    9572001: "Team Vision",
    10150538: "LGD Gaming",
    8261500: "Xtreme Gaming",
    9247354: "Team Falcons",
    10150413: "Iron Wing",
    7119388: "Team Spirit",
    2586976: "OG",
    2163: "Team Liquid",
    9823272: "Team Yandex",
    8255888: "BoomBoys",
    9467224: "Aurora Gaming",
    726228: "Vici Gaming",
    9964962: "GamerLegion",
    10136357: "Nigma Galaxy",
    5017210: "Team Resilience",
    10149530: "HULIGANI",
}

# 2026-08-07: TI2026's group stage uses two hidden seeding pods (A plays
# morning sessions, B plays afternoon), same structure user identified from
# TI2025 results. Confirmed against the real announced Day 1 Round 1 pairings -
# all 8 matches are within-pod. Swiss pairing is constrained to stay within a
# team's own pod for the first 3 rounds; from round 4 on it's a fully merged
# 16-team Swiss. See simulate_group_stage.py.
TEAM_POD = {
    9572001: "A",   # Team Vision
    9247354: "A",   # Team Falcons
    8255888: "A",   # BoomBoys
    10150413: "A",  # Iron Wing
    10136357: "A",  # Nigma Galaxy
    2586976: "A",   # OG
    10150538: "A",  # LGD Gaming
    5017210: "A",   # Team Resilience
    9823272: "B",   # Team Yandex
    2163: "B",      # Team Liquid
    9467224: "B",   # Aurora Gaming
    7119388: "B",   # Team Spirit
    8261500: "B",   # Xtreme Gaming
    726228: "B",    # Vici Gaming
    9964962: "B",   # GamerLegion
    10149530: "B",  # HULIGANI
}

# every known team_id registration per canonical team (rebrand/re-registration
# fragmentation) - needed because external rating sources like datdota track
# rating per exact team_id, not per underlying roster/org.
TEAM_ALL_IDS = {
    9572001: [9572001, 9824702],
    10150538: [10150538, 10144195, 9303484],
    8261500: [8261500],
    9247354: [9247354],
    10150413: [10150413, 10182357, 8291895],
    7119388: [7119388],
    2586976: [2586976],
    2163: [2163],
    9823272: [9823272],
    8255888: [8255888],
    9467224: [9467224],
    726228: [726228],
    9964962: [9964962],
    10136357: [10136357, 7554697],
    5017210: [5017210, 9316703, 9579337, 10207984],
    10149530: [10149530, 10182299, 9303383],
}

# local, self-contained copy of config.py's PLAYER_TO_TEAM (nickname -> canonical
# team_id) - keys match player_recent_heroes.json's top-level keys directly.
# 2026-08-07: LGD's TaiLung was permanently banned from competing; replaced by
# Topson for TI2026. See weighting.py's TEAM_WIN_CREDIT_MULTIPLIER for the
# roster-integrity rating penalty this triggered for LGD.
PLAYER_TO_TEAM = {
    "Satanic": 9572001,
    "Noticed": 9572001,
    "No[o]ne-": 9572001,
    "9Class": 9572001,
    "Dukalis": 9572001,
    "Yuma": 10150538,
    "Wisper": 10150538,
    "Topson": 10150538,
    "Thiolicor": 10150538,
    "KingJungles": 10150538,
    "Ame": 8261500,
    "Xxs": 8261500,
    "NothingToSay": 8261500,
    "fy": 8261500,
    "xNova": 8261500,
    "skiter": 9247354,
    "AMMAR_THE_F": 9247354,
    "Malr1ne": 9247354,
    "Cr1t-": 9247354,
    "Sneyking": 9247354,
    "Pure": 10150413,
    "33": 10150413,
    "bzm": 10150413,
    "Ari": 10150413,
    "Whitemon": 10150413,
    "Yatoro": 7119388,
    "Collapse": 7119388,
    "Larl": 7119388,
    "rue": 7119388,
    "not_me": 7119388,
    "Natsumi": 2586976,
    "Raven": 2586976,
    "Yopaj-": 2586976,
    "TIMS": 2586976,
    "skem": 2586976,
    "m1CKe": 2163,
    "Ace ♠": 2163,
    "Nisha": 2163,
    "Boxi": 2163,
    "tOfu": 2163,
    "医者watson`": 9823272,
    "DM": 9823272,
    "CHIRA_JUNIOR": 9823272,
    "Saksa": 9823272,
    "Maladych": 9823272,
    "Kiritych~": 8255888,
    "MieRo": 8255888,
    "gpk~": 8255888,
    "Save-": 8255888,
    "Kataomi`": 8255888,
    "Nightfall": 9467224,
    "Ws`": 9467224,
    "Mikoto": 9467224,
    "Mira": 9467224,
    "kaori": 9467224,
    "shiro": 726228,
    "Bach": 726228,
    "Xm": 726228,
    "XinQ": 726228,
    "y`": 726228,
    "Ghost": 9964962,
    "Fayde": 9964962,
    "RCY": 9964962,
    "Bignum": 9964962,
    "Speeed": 9964962,
    "SumaiL-": 10136357,
    "Davai": 10136357,
    "lorenof": 10136357,
    "OmaR": 10136357,
    "GH": 10136357,
    "YSR-04E": 5017210,
    "niu": 5017210,
    "Echozz": 5017210,
    "planet": 5017210,
    "zzq": 5017210,
    "ssnovv1": 10149530,
    "Corrupted": 10149530,
    "Mirage`雨": 10149530,
    "sayuw": 10149530,
    "RESPECT": 10149530,
}
