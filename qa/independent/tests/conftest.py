import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pandas as pd
import pytest

sys.dont_write_bytecode = True

def pytest_addoption(parser):
    parser.addoption('--app', required=True)
    parser.addoption('--report-dir', required=True)
    parser.addoption('--skip-browser', action='store_true')

def pytest_configure(config):
    sys.path.insert(0, str(Path(config.getoption('--app')) / 'src'))

def pytest_collection_modifyitems(config, items):
    if config.getoption('--skip-browser'):
        for item in items:
            if 'browser' in item.keywords:
                item.add_marker(pytest.mark.skip(reason='Browser explicitly disabled'))

@pytest.fixture(scope='session')
def app(pytestconfig):
    return Path(pytestconfig.getoption('--app')).resolve()

@pytest.fixture(scope='session')
def report_dir(pytestconfig):
    return Path(pytestconfig.getoption('--report-dir')).resolve()

@pytest.fixture(scope='session')
def raw(app):
    from moneygraph.dataio import load
    return load(app / 'data')

@pytest.fixture(scope='session')
def calculated(raw):
    from moneygraph import features, roles, clusters, priority, hypotheses
    f = roles.assign(features.build(raw))
    f, c = clusters.assign(raw, f)
    f, top = priority.rank(f)
    return f, hypotheses.describe(c, f), top

@pytest.fixture(scope='session')
def pipeline(app, tmp_path_factory, report_dir):
    root = tmp_path_factory.mktemp('pipeline')
    output = root / 'fresh output with spaces'
    source_before = {str(p.relative_to(app)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in app.rglob('*') if p.is_file()}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    start = time.monotonic()
    result = subprocess.run([sys.executable, str(app/'run.py'), '--data', str(app/'data'),
                             '--out', str(output)], cwd=root, env=env,
                            capture_output=True, text=True, timeout=300)
    elapsed = time.monotonic()-start
    (report_dir/'pipeline.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    tables = {p.stem: pd.read_csv(p) for p in output.glob('*.csv')}
    graph = json.loads((output/'graph.json').read_text())
    source_after = {str(p.relative_to(app)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in app.rglob('*') if p.is_file()}
    return dict(out=output, tables=tables, graph=graph, elapsed=elapsed,
                before=source_before, after=source_after, stdout=result.stdout)

@pytest.fixture(scope='session')
def server(app, pipeline):
    from moneygraph.serve import _Handler
    handler = functools.partial(_Handler, web_dir=app/'web', out_dir=pipeline['out'])
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{httpd.server_port}'
    httpd.shutdown(); httpd.server_close(); thread.join(timeout=5)

@pytest.fixture(scope='session')
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()

@pytest.fixture
def page(browser, server, report_dir, request):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    pg = context.new_page()
    pg.set_default_timeout(10000)
    pg.errors = []
    pg.on('pageerror', lambda error: pg.errors.append(str(error)))
    pg.goto(server+'/web/')
    pg.locator('#rail a').first.wait_for()
    yield pg
    if pg.errors:
        (report_dir/(request.node.name.replace('/', '_')+'.errors.txt')).write_text('\n'.join(pg.errors))
    if getattr(request.node, 'rep_call', None) and request.node.rep_call.failed:
        pg.screenshot(path=str(report_dir/(request.node.name.replace('/', '_')+'.png')), full_page=True)
    context.close()

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    setattr(item, 'rep_'+call.when, outcome.get_result())

@pytest.fixture
def synthetic():
    """All synthetic IDs are separate from real case outputs; no production fixtures modified."""
    from moneygraph.dataio import Dataset
    import networkx as nx
    def make(transfers, nodes=None):
        tx = pd.DataFrame(transfers, columns=['src', 'dst', 'date', 'sum_kzt'])
        tx['date'] = pd.to_datetime(tx.date)
        if nodes is None:
            ids = sorted(set(tx.src)|set(tx.dst))
            nodes = [(g, min(i, 4), i==0) for i,g in enumerate(ids)]
        n = pd.DataFrame(nodes, columns=['gid', 'depth', 'is_seed'])
        e = tx.groupby(['src','dst']).agg(sum_kzt=('sum_kzt','sum'), n_tx=('sum_kzt','size')).reset_index()
        e['depth'] = e.src.map(dict(zip(n.gid,n.depth))).fillna(0).astype(int)
        g = nx.DiGraph()
        for r in n.itertuples(): g.add_node(int(r.gid), depth=int(r.depth), is_seed=bool(r.is_seed))
        for r in e.itertuples(): g.add_edge(int(r.src),int(r.dst),sum_kzt=float(r.sum_kzt),n_tx=int(r.n_tx),depth=int(r.depth))
        return Dataset(e,n,tx,g)
    return make
