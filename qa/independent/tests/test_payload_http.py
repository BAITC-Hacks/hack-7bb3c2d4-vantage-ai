import json
from urllib.error import HTTPError
from urllib.request import urlopen, Request
import pytest

@pytest.mark.parametrize('key',['meta','nodes','edges','top','clusters','formations','formation_members',
 'node_completeness','next_data_request','completeness_summary','days','echoes','integrity','resilience'])
def test_payload_sections_present(pipeline,key): assert key in pipeline['graph']

def test_json_is_strict(pipeline):
    def reject(value): raise AssertionError('Non-standard JSON value: '+value)
    json.loads((pipeline['out']/'graph.json').read_text(),parse_constant=reject)

@pytest.mark.parametrize('section,key',[('nodes','id'),('edges','s'),('edges','t'),('top','gid'),
 ('formations','breaking_point_gid'),('formation_members','gid'),('node_completeness','gid'),('echoes','gid')])
def test_payload_account_ids_are_exact_strings(pipeline,raw,section,key):
    valid=set(map(str,raw.nodes.gid))
    assert all(isinstance(r[key],str) and r[key] in valid for r in pipeline['graph'][section])

def test_nested_ids_in_timeline_and_echoes(pipeline,raw):
    valid=set(map(str,raw.nodes.gid)); g=pipeline['graph']
    for records in ([d['transfers'] for d in g['days']]+[e['legs'] for e in g['echoes']]):
        for r in records:
            assert r['s'] in valid and r['t'] in valid
    assert all(isinstance(gid,str) and gid in valid for p in g.get('leadChains',[]) for gid in p)

def test_graph_counts(pipeline,raw):
    g=pipeline['graph']; assert g['meta']['nodes']==len(g['nodes'])==len(raw.nodes)
    assert g['meta']['edges']==len(g['edges'])==len(raw.edges)
    assert sum(g['meta']['roleCounts'].values())==len(raw.nodes)

@pytest.mark.parametrize('field',['y','priority','roleScore'])
def test_node_layout_and_scores_in_range(pipeline,field):
    bad=[n['id'] for n in pipeline['graph']['nodes'] if not 0<=n[field]<=1]
    assert not bad, f'{len(bad)} nodes have {field} outside [0,1]'

def test_node_positions_unique_within_hop(pipeline):
    pairs=[(n['hop'],n['y']) for n in pipeline['graph']['nodes']]
    assert len(pairs)==len(set(pairs)), 'Distinct nodes overlap in their assigned hop slot'

def test_payload_daily_totals(pipeline,raw):
    days=pipeline['graph']['days']
    assert len(days)==31
    assert sum(d['kzt'] for d in days)==pytest.approx(raw.tx.sum_kzt.sum())
    assert sum(d['n_tx'] for d in days)==len(raw.tx)
    for d in days:
        assert d['kzt']==pytest.approx(sum(t['kzt'] for t in d['transfers']))
        assert d['active']==len({g for t in d['transfers'] for g in [t['s'],t['t']]})

def test_payload_formation_membership(pipeline):
    g=pipeline['graph']; members=g['formation_members']
    for f in g['formations']:
        ids={r['gid'] for r in members if r['formation_id']==f['formation_id']}
        assert len(ids)==f['n_members'] and f['breaking_point_gid'] in ids

@pytest.mark.parametrize('path',['/web/','/web/index.html','/web/i18n.js','/web/replay.js','/web/echoes.js',
 '/out/graph.json','/out/nodes_roles.csv','/out/formations.csv','/out/echoes.csv'])
def test_http_serves_public_assets(server,path):
    with urlopen(server+path,timeout=5) as r:
        assert r.status==200 and r.read()
        assert r.headers.get('Cache-Control')=='no-store'

@pytest.mark.parametrize('path',['/','/web','/index.html'])
def test_http_entry_redirect(server,path):
    with urlopen(server+path) as r: assert r.geturl().endswith('/web/') and r.status==200

@pytest.mark.parametrize('path',['/run.py','/AGENTS.md','/.env','/.git/config','/data/nodes.parquet',
 '/web/../run.py','/web/%2e%2e/run.py','/out/%2e%2e/requirements.txt','/web/missing.js'])
def test_http_does_not_expose_repository(server,path):
    with pytest.raises(HTTPError) as e: urlopen(server+path,timeout=5)
    assert e.value.code==404

def test_http_custom_output_mount(server,pipeline):
    with urlopen(server+'/out/graph.json') as r:
        assert json.load(r)==pipeline['graph']

def test_http_head(server):
    with urlopen(Request(server+'/out/graph.json',method='HEAD')) as r:
        assert r.status==200 and not r.read()
        assert int(r.headers['Content-Length'])>0

def test_http_query_string(server):
    with urlopen(server+'/out/graph.json?version=123') as r: assert 'nodes' in json.load(r)
