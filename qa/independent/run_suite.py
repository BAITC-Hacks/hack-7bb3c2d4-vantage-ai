#!/usr/bin/env python3
"""Create a frozen Git snapshot and a separate QA environment, then run the suite."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent

def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', required=True, type=Path)
    p.add_argument('--ref', default='HEAD', help='Existing local Git ref; no automatic fetch or checkout')
    p.add_argument('--skip-browser', action='store_true')
    p.add_argument('--no-install', action='store_true', help='Use the existing QA environment')
    a = p.parse_args()
    repo = a.repo.resolve()
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', a.ref], text=True).strip()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    report = BASE / 'reports' / (stamp + '-' + commit[:8])
    report.mkdir(parents=True)
    envdir = BASE / '.venv'
    python = envdir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        run([sys.executable, '-m', 'venv', envdir])
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0')
    # Never pass developer API credentials into the tested application.
    for key in list(env):
        if key.endswith(('API_KEY', 'ACCESS_TOKEN')) or key in ('OPENAI_BASE_URL',):
            env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix='moneygraph-isolated-') as tmp:
        snapshot = (Path(tmp) / 'app').resolve()
        snapshot.mkdir()
        archive = subprocess.check_output(['git', '-C', str(repo), 'archive', commit])
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            for member in tf.getmembers():
                target = (snapshot / member.name).resolve()
                if not target.is_relative_to(snapshot) or member.issym() or member.islnk():
                    raise ValueError('Unsafe archive member: ' + member.name)
            tf.extractall(snapshot)
        if not a.no_install:
            run([python, '-m', 'pip', 'install', '-r', snapshot / 'requirements.txt',
                 '-r', BASE / 'requirements-qa.txt'], env=env)
            if not a.skip_browser:
                run([python, '-m', 'playwright', 'install', 'chromium'], env=env)
        (report / 'metadata.json').write_text(json.dumps({
            'commit': commit, 'repo': str(repo), 'ref': a.ref,
            'utc': stamp, 'browser_enabled': not a.skip_browser,
            'scope': 'committed snapshot only; uncommitted changes excluded'
        }, indent=2))
        with (report / 'environment.txt').open('w') as f:
            run([python, '-m', 'pip', 'freeze'], stdout=f, env=env)
        cmd = [python, '-m', 'pytest', str(BASE / 'tests'), '--app', snapshot,
               '--report-dir', report, '--junitxml', report / 'junit.xml',
               '--cov', snapshot / 'src/moneygraph',
               '--cov-report', 'term-missing', '--cov-report', 'json:' + str(report / 'coverage.json'),
               '--cov-report', 'html:' + str(report / 'coverage-html')]
        if a.skip_browser:
            cmd.append('--skip-browser')
        with (report / 'console.txt').open('w') as log:
            proc = subprocess.Popen([str(x) for x in cmd], cwd=BASE, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
            result = proc.wait()
        print('\nReports:', report)
        return result

if __name__ == '__main__':
    raise SystemExit(main())
