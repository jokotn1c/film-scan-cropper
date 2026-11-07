"""Launch the built .app through LaunchServices and verify its live process.

Run on macOS after PyInstaller. This checks packaging/startup, not visual
Dock behavior or a user machine's first-launch Gatekeeper latency.
"""
import json
import plistlib
from pathlib import Path
import subprocess
import tempfile
import time


def main():
    bundle = Path('dist-macos-arm64/FilmCrop-RAW.app').resolve()
    contents = bundle / 'Contents'
    plist = plistlib.loads((contents / 'Info.plist').read_bytes())
    assert plist['CFBundleIdentifier'] == 'com.jokotn1c.filmscancropper'
    assert (contents / 'Resources' / plist['CFBundleIconFile']).is_file()
    assert not plist.get('LSUIElement', False), 'Application must remain in Dock'
    with tempfile.TemporaryDirectory(prefix='filmcrop-startup-') as temp:
        report = Path(temp) / 'startup.json'
        started = time.monotonic()
        subprocess.run(['open', '-n', '-W', str(bundle), '--args',
                        '--startup-test', str(report)], check=True, timeout=90)
        result = json.loads(report.read_text(encoding='utf8'))
        assert 'error' not in result, result
        assert result['window_visible'], result
        assert Path(result['bundle_resources']).is_relative_to(contents), result
        executable = str(contents / 'MacOS' / plist['CFBundleExecutable'])
        processes = []
        for line in result['processes'].splitlines():
            fields = line.strip().split(None, 2)
            if len(fields) == 3 and fields[2] == executable:
                processes.append(int(fields[0]))
        assert processes == [result['pid']], result
        result['launch_seconds'] = round(time.monotonic() - started, 2)
        destination = Path('dist-macos-arm64/startup-check.json')
        destination.write_text(json.dumps(result, indent=2), encoding='utf8')
        print('PASS visible window, bundled libraries, single application process:',
              result['launch_seconds'], 'seconds including automatic close')


if __name__ == '__main__':
    main()
