"""Documentation and auxiliary artifact contracts (no application changes)."""
import ast
import json
from pathlib import Path
import re
import struct
import pytest

@pytest.mark.parametrize('filename',['README.md','docs/FORMATIONS.md','docs/COMPLETENESS.md',
 'docs/SCREEN.md','docs/DATASET-README.md','docs/case-spec-full.txt'])
def test_required_documentation_exists(app,filename):
    assert (app/filename).is_file() and (app/filename).stat().st_size>0

@pytest.mark.parametrize('name',['solution-schema','formations','network-overview','roles','rank-disagreement',
 'resilience','blind-spot','journey'])
def test_documentation_png_is_valid_nonempty(app,name):
    p=app/'docs/img'/f'{name}.png'; data=p.read_bytes()
    assert data[:8]==b'\x89PNG\r\n\x1a\n'
    width,height=struct.unpack('>II',data[16:24])
    assert width>=200 and height>=200 and len(data)>1000

def test_all_python_source_parses(app):
    for p in list((app/'src').rglob('*.py'))+list((app/'tools').rglob('*.py'))+[app/'run.py']:
        ast.parse(p.read_text(),filename=str(p))

def test_readme_local_images_resolve(app):
    text=(app/'README.md').read_text()
    for link in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text):
        if not link.startswith(('https://','http://')): assert (app/link).exists(),link

def test_root_static_entry_points_to_web(app):
    text=(app/'index.html').read_text()
    assert 'web/' in text

def test_dependencies_are_pinned(app):
    lines=[line.strip() for line in (app/'requirements.txt').read_text().splitlines() if line.strip() and not line.startswith('#')]
    assert lines and all('==' in line for line in lines)

def test_no_runtime_import_of_qa_tools(app):
    for p in (app/'src').rglob('*.py'):
        tree=ast.parse(p.read_text())
        imported=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import): imported.extend(a.name.split('.')[0] for a in node.names)
            if isinstance(node,ast.ImportFrom): imported.append((node.module or '').split('.')[0])
        assert not set(imported)&{'pytest','playwright','unittest'},p
