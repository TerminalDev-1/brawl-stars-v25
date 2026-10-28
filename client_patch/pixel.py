"""Add Pixel, a custom brawler, to the decoded v25 client data.

Pixel uses Max's model and animations, fires 8-Bit's blaster beams at
1,500 damage each, has 6,200 health, and her Super throws 8-Bit's damage
booster turret, which also leaves a Max-style speed boost where it lands.
Every row is cloned from an existing Max or 8-Bit row and appended, so the
row numbers of existing data stay the same. Re-applying rebuilds Pixel's rows
in place from their sources, so edits here reach an already patched client.
"""
import csv
import io
import re
from pathlib import Path

NUMBER = re.compile(r'-?\d+$')

# file -> list of (source row name, new row name, {column: value})
ROWS = {
    'csv_logic/characters.csv': [
        ('Speedy', 'Pixel', {
            'WeaponSkill': 'PixelWeapon', 'UltimateSkill': 'PixelUlti',
            'Hitpoints': '6200', 'DefaultSkin': 'PixelDefault',
            'TID': 'TID_PIXEL', 'HeroBundleTID': 'TID_HERO_BUNDLE_PIXEL',
            # 8-Bit's reload and empty-ammo sounds.
            'ReloadEffect': 'reload_arcade', 'DryFireEffect': 'arcade_dryfire',
            'OffenseRating': '5', 'DefenseRating': '4', 'UtilityRating': '4',
        }),
    ],
    'csv_logic/skills.csv': [
        # Range 21 is 7 tiles (8-Bit's is 30, 10 tiles).
        ('ArcadeWeapon', 'PixelWeapon', {'Damage': '1500', 'CastingRange': '21'}),
        ('ArcadeUlti', 'PixelUlti', {'Projectile': 'PixelUltiProjectile'}),
    ],
    'csv_logic/projectiles.csv': [
        ('ArcadeUltiProjectile', 'PixelUltiProjectile', {'SpawnAreaEffectObject': 'PixelSpeedArea'}),
    ],
    'csv_logic/area_effects.csv': [
        ('SpeedyUltiArea', 'PixelSpeedArea', {'TimeMs': '4000'}),
    ],
    'csv_logic/skins.csv': [
        ('SpeedyDefault', 'PixelDefault', {'Conf': 'PixelDefault', 'PetSkin': 'DamageBoosterDefault'}),
    ],
    'csv_logic/skin_confs.csv': [
        # No MainAttackEffect, so the weapon's 8-Bit laser effect and sound play
        # instead of Max's.
        ('SpeedyDefault', 'PixelDefault', {'Character': 'Pixel', 'MainAttackEffect': ''}),
    ],
    'csv_logic/cards.csv': [
        ('Speedy_unlock', 'Pixel_unlock', {'Target': 'Pixel', 'Rarity': 'legendary', 'SortOrder': '505'}),
        ('Speedy_hp', 'Pixel_hp', {'Target': 'Pixel'}),
        ('Arcade_abi', 'Pixel_abi', {'Target': 'Pixel', 'Skill': 'PixelWeapon', 'TID': 'TID_PIXEL_WEAPON'}),
        ('Arcade_ulti', 'Pixel_ulti', {'Target': 'Pixel', 'Skill': 'PixelUlti', 'TID': 'TID_PIXEL_ULTI'}),
    ],
}

TEXTS = {
    'TID_PIXEL': 'PIXEL',
    'TID_PIXEL_SHORT_DESC': 'DAMAGE DEALER',
    'TID_PIXEL_DESC': "Pixel borrowed 8-Bit's blasters and Max's sneakers. Her Super drops a damage booster that also gets everyone moving!",
    'TID_PIXEL_WEAPON': 'MEGA BEAMS',
    'TID_PIXEL_WEAPON_DESC': 'Pixel fires a burst of heavy blaster beams. Each beam hits hard.',
    'TID_PIXEL_ULTI': 'POWER SURGE',
    'TID_PIXEL_ULTI_DESC': 'Pixel throws a turret that boosts the damage of nearby allies and leaves a speed boost where it lands.',
    'TID_HERO_BUNDLE_PIXEL': 'Pixel Pack',
}


def _fields(line):
    return next(csv.reader(io.StringIO(line)))


def _line(fields):
    out = []
    for value in fields:
        out.append(value if value == '' or NUMBER.match(value) else '"' + value.replace('"', '""') + '"')
    return ','.join(out)


def apply(root):
    root = Path(root)
    for name, additions in ROWS.items():
        path = root / name
        text = path.read_bytes().decode('utf-8')
        lines = text.split('\r\n')
        while lines and lines[-1] == '':
            lines.pop()
        header = _fields(lines[0])
        rows = {_fields(l)[0]: l for l in lines[2:] if l and not l.startswith(',')}
        for source, new, changes in additions:
            fields = _fields(rows[source])
            fields += [''] * (len(header) - len(fields))
            fields[0] = new
            for column, value in changes.items():
                fields[header.index(column)] = value
            line = _line(fields)
            if new in rows:
                lines[lines.index(rows[new])] = line
            else:
                lines.append(line)
            rows[new] = line
        path.write_bytes(('\r\n'.join(lines) + '\r\n').encode('utf-8'))
    path = root / 'localization/texts.csv'
    text = path.read_bytes().decode('utf-8')
    newline = '\r\n' if '\r\n' in text else '\n'
    existing = {_fields(l)[0] for l in text.splitlines()[2:] if l}
    add = [_line([tid, value]) for tid, value in TEXTS.items() if tid not in existing]
    if add:
        path.write_bytes((text.rstrip('\r\n') + newline + newline.join(add) + newline).encode('utf-8'))


def character_row(root):
    """Row number of Pixel in characters.csv, as used in data references."""
    lines = (Path(root) / 'csv_logic/characters.csv').read_bytes().decode('utf-8').split('\r\n')[2:]
    names = [_fields(l)[0] for l in lines if l]
    return names.index('Pixel')


if __name__ == '__main__':
    import sys
    apply(sys.argv[1])
    print('Pixel is character row', character_row(sys.argv[1]))
