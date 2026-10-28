"""Brawlers every account owns on this server.

Keys are rows in csv_logic/characters.csv; values are the rows of their
unlock cards in csv_logic/cards.csv. Pixel (row 103, card 224) only exists
in the Terra client, which appends her with client_patch/pixel.py.
"""
SHELLY = 0
PIXEL = 103
OWNED_BRAWLERS = {SHELLY: 0, PIXEL: 224}
