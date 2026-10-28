"""Playable brawlers in the Terra v25 client.

Keys are rows in csv_logic/characters.csv; values are (name, row of the
unlock card in csv_logic/cards.csv, rarity). Pixel (row 103, card 224) only
exists in the Terra client, which appends her with client_patch/pixel.py.
"""
SHELLY = 0
PIXEL = 103
# Every account starts with these.
STARTER_BRAWLERS = (SHELLY, PIXEL)

BRAWLERS = {
    0: ('Shelly', 0, 'common'),
    1: ('Colt', 4, 'common'),
    2: ('Bull', 8, 'common'),
    3: ('Brock', 12, 'common'),
    4: ('Rico', 16, 'super_rare'),
    5: ('Spike', 20, 'legendary'),
    6: ('Barley', 24, 'rare'),
    7: ('Jessie', 28, 'common'),
    8: ('Nita', 32, 'common'),
    9: ('Dynamike', 36, 'common'),
    10: ('El Primo', 40, 'rare'),
    11: ('Mortis', 44, 'mega_epic'),
    12: ('Crow', 48, 'legendary'),
    13: ('Poco', 52, 'rare'),
    14: ('Bo', 56, 'common'),
    15: ('Piper', 60, 'epic'),
    16: ('Pam', 64, 'epic'),
    17: ('Tara', 68, 'mega_epic'),
    18: ('Darryl', 72, 'super_rare'),
    19: ('Penny', 95, 'super_rare'),
    20: ('Frank', 100, 'epic'),
    21: ('Gene', 105, 'mega_epic'),
    22: ('Tick', 110, 'common'),
    23: ('Leon', 115, 'legendary'),
    24: ('Rosa', 120, 'rare'),
    25: ('Carl', 125, 'super_rare'),
    26: ('Bibi', 130, 'epic'),
    27: ('8-Bit', 177, 'common'),
    28: ('Sandy', 182, 'legendary'),
    29: ('Bea', 188, 'epic'),
    30: ('Emz', 194, 'common'),
    31: ('Mr. P', 200, 'mega_epic'),
    32: ('Max', 206, 'mega_epic'),
    PIXEL: ('Pixel', 224, 'legendary'),
}


def unlock_card(brawler):
    return BRAWLERS[brawler][1]
