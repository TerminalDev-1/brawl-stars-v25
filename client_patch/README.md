# Building the v25 client

The builder decodes the supplied Brawl Stars 25.107 ARM32 APK, verifies the stock `libg.so` SHA-256, renames the app package, embeds the v25 transport script and Frida Gadget, then rebuilds and signs the APK. The original APK and official installed package remain untouched.

You need Java, Python 3, apktool 3, uber-apk-signer, an ARM32 Frida gadget and Android platform-tools. Put them in a directory as `apktool.jar`, `uber-apk-signer.jar`, `libfrida-gadget-arm.so` and `platform-tools/adb.exe`. The default tools path points to the neighboring v29 project, or pass `--tools`.

```powershell
python client_patch/build.py --tools PATH_TO_TOOLS --apk PATH_TO_V25_APK --transport
python client_patch/build.py --tools PATH_TO_TOOLS --transport --install --serial DEVICE_SERIAL
```

The first build creates the ignored `client_work/` directory. The install option sets up `adb reverse tcp:9339 tcp:9339`. The generated signed APK is in `build/`. Preserve the signing key if you need to update the installed app without losing its data.

The version-specific transport bypasses the original network encryption for the local server and redirects the game socket to loopback. It uses the client's local simulation for bot battles and sends the completed result to Python. The APK needs the local Python server to reach the lobby and record rewards.
