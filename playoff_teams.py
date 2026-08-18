# Time-bound TI2026 playoff bracket constants (Aug 20-23). Kept standalone,
# mirroring team_config.py's own role as a self-contained copy rather than a
# shared import - team_config.py documents itself as the fantasy-root's config
# copy, and a playoff-only subset doesn't belong permanently in that file.

# The 8 teams that qualified out of the 16-team Group Stage.
PLAYOFF_TEAM_IDS = [
    9572001,   # Team Vision
    2163,      # Team Liquid
    7119388,   # Team Spirit
    10150413,  # Iron Wing
    8255888,   # BoomBoys
    9823272,   # Team Yandex
    10136357,  # Nigma Galaxy
    9247354,   # Team Falcons
]

# Real, announced Upper Bracket Round 1 seeding.
UB_R1_PAIRINGS = [
    (10150413, 7119388),  # Iron Wing vs Team Spirit
    (9572001, 8255888),   # Team Vision vs BoomBoys
    (2163, 9823272),      # Team Liquid vs Team Yandex
    (10136357, 9247354),  # Nigma Galaxy vs Team Falcons
]
