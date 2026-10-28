# Terra — Brawl Stars v25 private server

Terra is an experimental Python server and Android client patch for Brawl Stars 25.107. It is an unofficial project and is not affiliated with Supercell.

The client can log in, create and restore a local account, choose a name, and play Gem Grab against five computer-controlled bots. Completed battles award tokens towards the Brawl Box counter and trophies; both survive restarts. A win awards 20 tokens and 8 trophies, a draw awards 15 tokens, and a loss awards 10 tokens. Every battle also awards 8 experience. The result screen animates Shelly's rank bar and the experience bar from the saved values and plays a rank-up when a rank threshold is crossed. Experience is saved but not yet shown in the lobby. This was tested on an ARM-compatible Android 14 tablet. Opening boxes, most progression, the shop, clubs, and friends are not implemented yet.

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
