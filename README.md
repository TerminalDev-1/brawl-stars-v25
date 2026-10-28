# Terra — Brawl Stars v25 private server

Terra is an experimental Python server and Android client patch for Brawl Stars 25.107. It is an unofficial project and is not affiliated with Supercell.

The client can log in, create and restore a local account, choose a name, and play two events against computer-controlled bots: Gem Grab (3v3 with five bots) and Solo Showdown (with nine bots). Completed battles award tokens towards the Brawl Box counter, trophies and experience; all survive restarts.

| Event | Tokens | Trophies |
| --- | --- | --- |
| Gem Grab | win 20, draw 15, loss 10 | win +8 |
| Solo Showdown, places 1–10 | 20, 18, 16, 14, 12, 10, 8, 6, 4, 2 | +10, +8, +7, +6, +4, +2, +2, +1, 0, 0 |

Every battle also awards 8 experience. The Showdown trophies follow the game's lowest trophy bracket (0–49); the Showdown token amounts are this server's own choice. The result screen animates Shelly's rank bar and the experience bar and plays a rank-up when a rank threshold is crossed. Back in the lobby, the earned trophies and tokens fly into their counters. Experience is saved but not yet shown in the lobby.

This was tested on an ARM-compatible Android 14 tablet. Duo Showdown (the client shows a Duo button, but it falls back to Gem Grab), opening boxes, most progression, the shop, clubs, and friends are not implemented yet.

## Run the server

Requires Python 3.10 or newer; no third-party Python packages are needed.

```powershell
python server/app.py
```

The server listens on `127.0.0.1:9339`. Accounts, login tokens and names are stored in `server/data/accounts.sqlite3`; keep this file private. The client stores its account token in private Android app data. Account data is not included in this repository.

## Install the client

Download the APK from the Releases page. With the device connected through Android Debug Bridge:

```powershell
adb install --bypass-low-target-sdk-block -r --abi armeabi-v7a terra-v25.apk
adb reverse tcp:9339 tcp:9339
```

Start the server, then launch Terra on the device. Repeat `adb reverse` after reconnecting ADB. The client is installed as `com.terra.brawl25`, separate from the official game. On first launch, review the original client notice yourself and enter a name.

The experimental transport supports the local bot-battle flow and does not implement the full game protocol. The game client simulates the match; Python records the result and rewards. It is designed for local use and should not be exposed to the public internet.

## Build and test

See [client_patch/README.md](client_patch/README.md) for rebuilding the APK. Run `python -m unittest discover -s server -v` for the Python tests.

The server and client patch were written for this project, informed by [DDBS-V25](https://github.com/GDsWELL/DDBS-V25). Brawl Stars game assets belong to their respective owners.
