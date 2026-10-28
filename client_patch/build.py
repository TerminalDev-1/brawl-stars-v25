"""Build an isolated, instrumented v25.107 client for startup research."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pixel

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'client_work'
PATCH = ROOT / 'client_patch'
DEFAULT_TOOLS = Path(os.environ.get('BRAWL_TOOLS', str(ROOT.parent / 'v29' / 'tools')))
EXPECTED = '8f0c6e9172f029d7b8fb4e916d5ed98ba3a1cc333adcc4eb20ee672cf4e9172f'
PACKAGE = 'com.terra.brawl25'

def run(*args):
    print('>', *args, flush=True)
    subprocess.run([str(x) for x in args], check=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools', type=Path, default=DEFAULT_TOOLS, help='directory containing apktool.jar, uber-apk-signer.jar, Frida gadget and platform-tools')
    p.add_argument('--apk', type=Path, help='original v25.107 APK; required for first build')
    p.add_argument('--transport', action='store_true', help='embed experimental v25 server transport')
    p.add_argument('--script', type=Path, help='embed this Frida script instead (development tracing)')
    p.add_argument('--debugger', action='store_true', help='wait for a Frida debugger at port 27042')
    p.add_argument('--install', action='store_true')
    p.add_argument('--serial', help='ADB device serial')
    a = p.parse_args()
    tools = a.tools.resolve()
    if not SOURCE.exists():
        if not a.apk:
            p.error('--apk is required when client_work has not been decoded')
        run('java', '-jar', tools / 'apktool.jar', 'd', '-o', SOURCE, a.apk.resolve())
    lib = SOURCE / 'lib/armeabi-v7a'
    if hashlib.sha256((lib / 'libg.so').read_bytes()).hexdigest() != EXPECTED:
        raise SystemExit('Unexpected libg.so: only stock 25.107 is supported')
    manifest = SOURCE / 'AndroidManifest.xml'
    data = manifest.read_text(encoding='utf-8')
    data = data.replace('package="com.supercell.brawlstars"', f'package="{PACKAGE}"')
    data = data.replace('android:authorities="com.supercell.brawlstars.', f'android:authorities="{PACKAGE}.')
    manifest.write_text(data, encoding='utf-8')
    smali = SOURCE / 'smali/com/supercell/titan/GameApp.smali'
    data = smali.read_text(encoding='utf-8')
    needle = '    const-string v0, "g"\n'
    inject = '    const-string v0, "gadget"\n\n    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V\n\n'
    if inject not in data:
        if data.count(needle) != 1:
            raise SystemExit('Cannot identify game library load')
        data = data.replace(needle, inject + needle)
        smali.write_text(data, encoding='utf-8')
    pixel.apply(SOURCE / 'assets')
    shutil.copyfile(tools / 'libfrida-gadget-arm.so', lib / 'libgadget.so')
    interaction = {'type':'listen','address':'127.0.0.1','port':27042,'on_load':'wait'} if a.debugger else {'type':'script','path':'libgadget.script.so'}
    (lib / 'libgadget.config.so').write_text(json.dumps({'interaction': interaction}), encoding='utf-8')
    script = a.script or PATCH / ('experimental_transport.js' if a.transport else 'diagnostic.js')
    shutil.copyfile(script, lib / 'libgadget.script.so')
    out = ROOT / 'build'
    out.mkdir(exist_ok=True)
    unsigned = out / 'terra-v25-diagnostic-unsigned.apk'
    run('java', '-jar', tools / 'apktool.jar', 'b', SOURCE, '-o', unsigned)
    run('java', '-jar', tools / 'uber-apk-signer.jar', '-a', unsigned, '-o', out, '--allowResign')
    signed = out / 'terra-v25-diagnostic-aligned-debugSigned.apk'
    if not signed.exists():
        raise SystemExit('Signed APK not found')
    if a.install:
        adb = [tools / 'platform-tools/adb.exe']
        if a.serial:
            adb += ['-s', a.serial]
        run(*adb, 'install', '--bypass-low-target-sdk-block', '-r', '--abi', 'armeabi-v7a', signed)
        run(*adb, 'reverse', 'tcp:9339', 'tcp:9339')
    print('Built', signed)

if __name__ == '__main__':
    main()
