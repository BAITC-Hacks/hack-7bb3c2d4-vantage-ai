import json
import math
import os
import subprocess
import sys

import networkx as nx
import numpy as np
import pandas as pd
import pytest

FILES = {
 'nodes_roles': ['gid','role','role_score','cluster_id','priority_score','evidence'],
 'clusters': ['cluster_id','n_nodes','n_seed','sum_kzt_internal','top_gids','hypothesis'],
 'top_nodes': ['rank','gid','role','priority_score','why'],
 'formations': ['formation_id','kind','n_members','n_seeds','breaking_point_gid','score','rank','hypothesis','evidence'],
 'formation_members': ['formation_id','gid','role_in_formation','member_evidence'],
 'completeness': ['gid','knowledge_state','confidence','limitation'],
 'next_data_request': ['rank','request','why','resolves_nodes','illuminates_kzt'],
 'timeline': ['date','src','dst','sum_kzt','n_tx'],
 'echoes': ['echo_id','kind','gid','date','in_kzt','out_kzt','lag_days','score','evidence'],
 'cycles': ['length','path','min_leg_kzt','total_kzt'],
 'reciprocal_pairs': ['gid_a','gid_b','a_to_b_kzt','b_to_a_kzt','returned_share','n_tx'],
 'resilience': ['removed','largest_component','n_components','nodes_reachable_from_seeds'],
 'pagerank_vs_evidence': ['gid','rank_pagerank','rank_priority','rank_gap'],
}

@pytest.mark.parametrize('name', FILES)
def test_output_exists_and_has_rows(pipeline,name):
    assert name in pipeline['tables']
    assert len(pipeline['tables'][name]) > 0

@pytest.mark.parametrize('name', FILES)
def test_output_schema(pipeline,name):
    assert set(FILES[name]) <= set(pipeline['tables'][name])

@pytest.mark.parametrize('name,col', [('nodes_roles','role_score'),('nodes_roles','priority_score'),
 ('formations','score'),('formations','kzt_retained_share'),('completeness','confidence'),
 ('echoes','score'),('reciprocal_pairs','returned_share')])
def test_scores_finite_and_bounded(pipeline,name,col):
    s=pipeline['tables'][name][col]
    assert np.isfinite(s).all() and s.between(0,1).all()

@pytest.mark.parametrize('name,col,max_len', [('nodes_roles','evidence',200),('echoes','evidence',200),
 ('completeness','limitation',200),('formations','evidence',220),('clusters','hypothesis',None),
 ('formations','hypothesis',None),('formation_members','member_evidence',None),('top_nodes','why',None),
 ('next_data_request','why',None)])
def test_explanations_nonempty(pipeline,name,col,max_len):
    s=pipeline['tables'][name][col]
    assert s.notna().all() and s.astype(str).str.strip().str.len().gt(0).all()
    if max_len: assert s.str.len().le(max_len).all()

@pytest.mark.parametrize('name,key',[('nodes_roles','gid'),('completeness','gid'),('top_nodes','gid'),
 ('clusters','cluster_id'),('formations','formation_id'),('echoes','echo_id')])
def test_unique_identifiers(pipeline,name,key):
    assert pipeline['tables'][name][key].is_unique

@pytest.mark.parametrize('name',['nodes_roles','completeness'])
def test_all_declared_nodes_preserved(raw,pipeline,name):
    assert set(pipeline['tables'][name].gid)==set(raw.nodes.gid)
    assert len(pipeline['tables'][name])==len(raw.nodes)

@pytest.mark.parametrize('name,score',[('top_nodes','priority_score'),('formations','score')])
def test_rank_order(pipeline,name,score):
    t=pipeline['tables'][name]
    assert t['rank'].tolist()==list(range(1,len(t)+1))
    assert t[score].is_monotonic_decreasing

def test_top_list_references_actual_nodes(pipeline):
    t=pipeline['tables']; n=t['nodes_roles'].set_index('gid'); top=t['top_nodes']
    assert len(top)>=20
    for r in top.itertuples():
        assert r.role==n.loc[r.gid,'role']
        assert r.priority_score==n.loc[r.gid,'priority_score']

def test_runtime(pipeline): assert pipeline['elapsed']<300

def test_application_files_not_modified(pipeline): assert pipeline['before']==pipeline['after']

def test_isolated_seeds_are_not_dropped(raw,pipeline):
    isolated=set(raw.nodes.gid)-set(raw.edges.src)-set(raw.edges.dst)
    n=pipeline['tables']['nodes_roles'].set_index('gid')
    assert len(isolated)==19
    assert n.loc[list(isolated),'role'].eq('peripheral').all()

@pytest.mark.parametrize('metric', ['in_deg','out_deg','in_kzt','out_kzt','in_tx','out_tx'])
def test_node_metrics_against_raw_aggregation(raw,pipeline,metric):
    incoming=metric.startswith('in_'); key='dst' if incoming else 'src'
    if metric.endswith('deg'): expected=raw.edges.groupby(key).size()
    elif metric.endswith('kzt'): expected=raw.tx.groupby(key).sum_kzt.sum()
    else: expected=raw.tx.groupby(key).size()
    n=pipeline['tables']['nodes_roles']
    np.testing.assert_allclose(n[metric],n.gid.map(expected).fillna(0),atol=0.01)

@pytest.mark.parametrize('field',['n_nodes','n_seed','sum_kzt_internal','top_gids'])
def test_cluster_measurements(raw,pipeline,field):
    n=pipeline['tables']['nodes_roles']; clusters=pipeline['tables']['clusters']; seeds=raw.seeds
    for r in clusters.itertuples():
        members=set(n.loc[n.cluster_id==r.cluster_id,'gid'])
        if field=='n_nodes': assert r.n_nodes==len(members)
        if field=='n_seed': assert r.n_seed==len(members&seeds)
        if field=='sum_kzt_internal':
            expected=raw.edges.loc[raw.edges.src.isin(members)&raw.edges.dst.isin(members),'sum_kzt'].sum()
            assert r.sum_kzt_internal==pytest.approx(expected,abs=0.01)
        if field=='top_gids': assert set(map(int,str(r.top_gids).split()))<=members

@pytest.mark.parametrize('field',['n_members','n_seeds','breaking_point_gid','kzt_through','min_hop_from_seed'])
def test_formation_measurements(raw,pipeline,field):
    t=pipeline['tables']; m=t['formation_members']; seeds=raw.seeds; depth=raw.nodes.set_index('gid').depth
    for r in t['formations'].itertuples():
        members=set(m.loc[m.formation_id==r.formation_id,'gid'])
        assert members<=set(raw.nodes.gid)
        if field=='n_members': assert len(members)==r.n_members
        if field=='n_seeds': assert len(members&seeds)==r.n_seeds
        if field=='breaking_point_gid': assert r.breaking_point_gid in members
        if field=='min_hop_from_seed': assert r.min_hop_from_seed==depth.loc[list(members)].min()
        if field=='kzt_through':
            expected=raw.edges.loc[raw.edges.src.isin(members)|raw.edges.dst.isin(members),'sum_kzt'].sum()
            assert r.kzt_through==pytest.approx(expected,abs=0.01)

def test_no_duplicate_membership(pipeline):
    assert not pipeline['tables']['formation_members'].duplicated(['formation_id','gid']).any()

def test_no_orphan_membership(pipeline):
    t=pipeline['tables']; assert set(t['formation_members'].formation_id)==set(t['formations'].formation_id)

def test_no_duplicate_formations(pipeline):
    t=pipeline['tables']; m=t['formation_members']; keys=[]
    for r in t['formations'].itertuples():
        keys.append((r.kind,tuple(sorted(m.loc[m.formation_id==r.formation_id,'gid']))))
    assert len(keys)==len(set(keys))

@pytest.mark.parametrize('field',['length','min_leg_kzt','total_kzt'])
def test_cycle_paths_and_amounts(raw,pipeline,field):
    for r in pipeline['tables']['cycles'].itertuples():
        path=list(map(int,r.path.split(' -> ')))
        assert path[0]==path[-1] and len(set(path[:-1]))==len(path)-1
        assert all(raw.graph.has_edge(a,b) for a,b in zip(path,path[1:]))
        amounts=[raw.graph[a][b]['sum_kzt'] for a,b in zip(path,path[1:])]
        if field=='length': assert r.length==len(path)-1 and 2<=r.length<=6
        if field=='min_leg_kzt': assert r.min_leg_kzt==pytest.approx(min(amounts))
        if field=='total_kzt': assert r.total_kzt==pytest.approx(sum(amounts))

def test_reciprocal_pairs_complete_and_correct(raw,pipeline):
    expected={(min(a,b),max(a,b)) for a,b in raw.graph.edges if a!=b and raw.graph.has_edge(b,a)}
    rows=pipeline['tables']['reciprocal_pairs']
    assert set(zip(rows.gid_a,rows.gid_b))==expected
    for r in rows.itertuples():
        assert r.a_to_b_kzt==raw.graph[r.gid_a][r.gid_b]['sum_kzt']
        assert r.b_to_a_kzt==raw.graph[r.gid_b][r.gid_a]['sum_kzt']

def test_resilience_against_independent_graph_removal(raw,pipeline):
    ranked=pipeline['tables']['top_nodes'].gid.tolist()
    for r in pipeline['tables']['resilience'].itertuples():
        g=raw.graph.copy(); g.remove_nodes_from(ranked[:r.removed])
        comps=list(nx.weakly_connected_components(g))
        assert r.largest_component==max(map(len,comps),default=0)
        assert r.n_components==len(comps)
        reach=set(raw.seeds) & set(g)
        for s in raw.seeds & set(g): reach.update(nx.descendants(g,s))
        assert r.nodes_reachable_from_seeds==len(reach)

@pytest.mark.parametrize('column',['sum_kzt','n_tx'])
def test_timeline_conserves_raw_data(raw,pipeline,column):
    t=pipeline['tables']['timeline']
    expected=raw.tx.sum_kzt.sum() if column=='sum_kzt' else len(raw.tx)
    assert t[column].sum()==pytest.approx(expected)

def test_timeline_exact_daily_groups(raw,pipeline):
    tx=raw.tx.copy(); tx['date']=tx.date.dt.strftime('%Y-%m-%d')
    expected=tx.groupby(['date','src','dst']).agg(sum_kzt=('sum_kzt','sum'),n_tx=('sum_kzt','size')).reset_index()
    actual=pipeline['tables']['timeline']
    pd.testing.assert_frame_equal(actual,expected,check_dtype=False,atol=0.001)

@pytest.mark.parametrize('name',['nodes_roles.csv','clusters.csv','top_nodes.csv','formations.csv','graph.json','timeline.csv','echoes.csv'])
def test_committed_outputs_match_fresh_calculation(app,pipeline,name):
    committed=app/'out'/name; fresh=pipeline['out']/name
    assert committed.exists()
    if name.endswith('.json'):
        assert json.loads(committed.read_text())==json.loads(fresh.read_text())
    else:
        pd.testing.assert_frame_equal(pd.read_csv(committed),pd.read_csv(fresh),check_exact=False,rtol=1e-8,atol=1e-8)

@pytest.fixture(scope='module')
def repeated(app,tmp_path_factory):
    root=tmp_path_factory.mktemp('repeat'); outputs=[]
    for seed in ['17','93']:
        out=root/seed; env=dict(os.environ,PYTHONHASHSEED=seed,PYTHONDONTWRITEBYTECODE='1')
        p=subprocess.run([sys.executable,str(app/'run.py'),'--data',str(app/'data'),'--out',str(out)],env=env,capture_output=True,text=True,timeout=300)
        assert p.returncode==0,p.stderr
        outputs.append(out)
    return outputs

@pytest.mark.parametrize('name',['nodes_roles.csv','clusters.csv','top_nodes.csv','formations.csv','graph.json','echoes.csv'])
def test_repeatability_across_hash_seeds(repeated,name):
    assert (repeated[0]/name).read_bytes()==(repeated[1]/name).read_bytes()

@pytest.mark.parametrize('args',[['--help'],['--unknown'],['--data','/nonexistent-moneygraph-data']])
def test_cli_exit_contract(app,tmp_path,args):
    p=subprocess.run([sys.executable,str(app/'run.py'),*args,'--out',str(tmp_path/'out')],capture_output=True,text=True,timeout=20)
    if '--help' in args: assert p.returncode==0 and '--data' in p.stdout
    else: assert p.returncode!=0
