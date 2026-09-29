#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/fusion'


def check_skill():
    text = (SKILL / 'SKILL.md').read_text()
    match = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not match:
        raise SystemExit('SKILL.md needs YAML frontmatter.')
    fields = dict(line.split(': ', 1) for line in match.group(1).splitlines())
    if fields.get('name') != SKILL.name or not fields.get('description'):
        raise SystemExit('SKILL.md frontmatter needs name: fusion and a description.')
    for document in [SKILL / 'SKILL.md', *SKILL.glob('references/*.md'), ROOT / 'README.md', *ROOT.glob('docs/*.md')]:
        for target in re.findall(r'\]\(([^)#:]+)(?:#[^)]*)?\)', document.read_text()):
            if not (document.parent / target).exists():
                raise SystemExit(f'{document.relative_to(ROOT)} links to missing {target}.')


def main():
    for path in [*ROOT.glob('scripts/*.py'), *SKILL.glob('scripts/*.py'), *ROOT.glob('tests/*.py')]:
        compile(path.read_text(), str(path), 'exec')
    sys.path.insert(0, str(SKILL / 'scripts'))
    import model_config
    model_config.validate(json.loads((SKILL / 'config/models.default.json').read_text()))
    check_skill()
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=ROOT, env=environment, check=True)
    print('Source syntax, default models, skill structure, links, and tests passed.')


if __name__ == '__main__':
    main()
