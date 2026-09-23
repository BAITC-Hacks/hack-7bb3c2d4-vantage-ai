"""Adversarial contracts; failures expose hardening gaps, not necessarily case-data blockers."""
from pathlib import Path
import functools
import http.server
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import networkx as nx
import pandas as pd
import pytest
from moneygraph import dataio, formations, features, completeness, roles, priority, clusters, hypotheses

pytestmark = pytest.mark.robustness

def write_data(d,root):
    root.mkdir(exist_ok=True)
    d.nodes.to_parquet(root/'nodes.parquet',index=False)
    d.edges.to_parquet(root/'edges.parquet',index=False)
    d.tx.to_parquet(root/'transactions.parquet',index=False)

@pytest.mark.parametrize('file',['nodes.parquet','edges.parquet','transactions.parquet'])
def test_missing_required_file_rejected(synthetic,tmp_path,file):
    d=synthetic([(1,2,'2026-07-01',10000)])
    write_data(d,tmp_path); (tmp_path/file).unlink()
    with pytest.raises((OSError,ValueError)): dataio.load(tmp_path)

@pytest.mark.parametrize('table,column',[('nodes','gid'),('nodes','depth'),('nodes','is_seed'),
 ('edges','src'),('edges','dst'),('edges','sum_kzt'),('edges','n_tx'),('tx','date')])
def test_missing_required_column_rejected(synthetic,tmp_path,table,column):
    d=synthetic([(1,2,'2026-07-01',10000)])
    setattr(d,table,getattr(d,table).drop(columns=column)); write_data(d,tmp_path)
    with pytest.raises((KeyError,AttributeError,ValueError)): dataio.load(tmp_path)

@pytest.mark.parametrize('mutation',['duplicate_nodes','undeclared_endpoint','negative_amount','null_gid',
 'negative_depth','duplicate_edges','nonboolean_seed'])
def test_malformed_data_rejected_before_analysis(synthetic,tmp_path,mutation):
    d=synthetic([(1,2,'2026-07-01',10000)])
    if mutation=='duplicate_nodes': d.nodes=pd.concat([d.nodes,d.nodes.iloc[[0]]],ignore_index=True)
    if mutation=='undeclared_endpoint': d.edges.loc[0,'dst']=999
    if mutation=='negative_amount': d.edges.loc[0,'sum_kzt']=-10000
    if mutation=='null_gid': d.nodes['gid']=d.nodes.gid.astype(float); d.nodes.loc[0,'gid']=float('nan')
    if mutation=='negative_depth': d.nodes.loc[0,'depth']=-1
    if mutation=='duplicate_edges': d.edges=pd.concat([d.edges,d.edges],ignore_index=True)
    if mutation=='nonboolean_seed': d.nodes['is_seed']=['False','True']
    write_data(d,tmp_path)
    with pytest.raises((ValueError,TypeError,AssertionError)): dataio.load(tmp_path)

def test_input_rows_not_mutated_by_feature_build(raw):
    saved=[x.copy(deep=True) for x in (raw.nodes,raw.edges,raw.tx)]
    features.build(raw)
    for actual,expected in zip((raw.nodes,raw.edges,raw.tx),saved): pd.testing.assert_frame_equal(actual,expected)

def test_role_independent_of_dataframe_index(calculated):
    f=calculated[0].drop(columns=['role','role_score','evidence'])
    a=roles.assign(f).set_index('gid')[['role','role_score','evidence']].sort_index()
    f=f.sample(frac=1,random_state=5).reset_index(drop=True)
    b=roles.assign(f).set_index('gid')[['role','role_score','evidence']].sort_index()
    pd.testing.assert_frame_equal(a,b)

def test_cluster_no_negative_or_missing_members(raw,calculated):
    f=calculated[0]
    assert f.cluster_id.ge(0).all() and f.component_id.ge(0).all()
    assert set(f.gid)==set(raw.nodes.gid)

@pytest.mark.parametrize('shape',['funnel','fan_out','reciprocal_loop','chain'])
def test_known_formation_patterns(synthetic,shape):
    if shape=='funnel': tx=[(i,10,'2026-07-01',10000) for i in range(1,5)]+[(10,1,'2026-07-02',5000)]
    elif shape=='fan_out': tx=[(1,i,'2026-07-01',10000) for i in range(2,12)]+[(12,1,'2026-07-01',10000),(1,12,'2026-07-02',5000)]
    elif shape=='reciprocal_loop': tx=[(1,2,'2026-07-01',10000),(2,1,'2026-07-02',8000)]
    else: tx=[(1,2,'2026-07-01',10000),(2,3,'2026-07-01',10000),(3,4,'2026-07-01',10000),(10,11,'2026-07-01',10000),(11,10,'2026-07-02',5000)]
    d=synthetic(tx)
    f=roles.assign(features.build(d)); f,c=clusters.assign(d,f); f,_=priority.rank(f)
    result,membership=formations.build(d,f,f,c)
    assert shape in set(result.kind)
    assert set(membership.gid)<=set(d.nodes.gid)

@pytest.mark.parametrize('kind',['chain','funnel','reciprocal_loop','bridge'])
def test_breaking_point_known_graphs(synthetic,kind):
    if kind=='reciprocal_loop': tx=[(1,2,'2026-07-01',100),(2,1,'2026-07-01',80)]; ids=(1,2); entry=1
    elif kind=='funnel': tx=[(1,4,'2026-07-01',100),(2,4,'2026-07-01',100),(3,4,'2026-07-01',100)]; ids=(1,2,3,4); entry=4
    else: tx=[(1,2,'2026-07-01',100),(2,3,'2026-07-01',100),(3,4,'2026-07-01',100)]; ids=(1,2,3,4); entry=1
    d=synthetic(tx); ctx={'in_adj':{},'out_adj':{}}
    for n in d.graph:
        ctx['in_adj'][n]=[(s,a['sum_kzt']) for s,_,a in d.graph.in_edges(n,data=True)]
        ctx['out_adj'][n]=[(t,a['sum_kzt']) for _,t,a in d.graph.out_edges(n,data=True)]
    candidate={'members':ids,'entry':entry,'kind':kind}
    gid,method,effect,frag=formations._breaking_point(d.graph,ctx,candidate,sum(d.edges.sum_kzt))
    assert gid in ids and effect>=0 and 0<=frag<=1
    if kind=='chain': assert gid==2 and method=='dominator' and effect==2
    if kind=='funnel': assert gid==4 and method=='articulation' and effect==3
    if kind=='reciprocal_loop': assert method=='flow' and effect==180
    if kind=='bridge': assert method=='articulation'

def test_full_completeness_matches_states_and_confidence(raw,calculated):
    f=calculated[0]; c,requests,summary=completeness.build(raw,f,f)
    assert set(c.gid)==set(raw.nodes.gid)
    assert set(c.knowledge_state)<=set(completeness.KNOWLEDGE_STATES)
    for r in c.itertuples(): assert 0<=r.confidence<=completeness.CONFIDENCE_CAPS[r.knowledge_state]
    assert requests['rank'].tolist()==list(range(1,len(requests)+1))
    assert requests.resolves_nodes.between(0,len(raw.nodes)).all()
    assert summary['ground_truth_check']=='agrees with the brief'

def test_server_symlink_cannot_escape_mount(tmp_path):
    from moneygraph.serve import _Handler
    web=tmp_path/'web'; out=tmp_path/'out'; web.mkdir(); out.mkdir()
    secret=tmp_path/'private.txt'; secret.write_text('private fixture')
    (web/'escape.txt').symlink_to(secret)
    handler=functools.partial(_Handler,web_dir=web.resolve(),out_dir=out.resolve())
    httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=threading.Thread(target=httpd.serve_forever,daemon=True); thread.start()
    try:
        with pytest.raises(HTTPError) as e: urlopen(f'http://127.0.0.1:{httpd.server_port}/web/escape.txt')
        assert e.value.code==404
    finally: httpd.shutdown(); httpd.server_close(); thread.join(timeout=5)
