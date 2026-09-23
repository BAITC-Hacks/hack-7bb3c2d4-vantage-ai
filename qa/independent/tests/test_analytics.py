from types import SimpleNamespace
import json
import math

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from moneygraph import roles, priority, features, flows, completeness, timeline, echoes, viewdata, dataio


def row(**kw):
    r=dict(gid=100000000000000001,depth=1,is_seed=False,isolated=False,truncated_by_depth=False,
           genuine_terminal=False,in_deg=2,out_deg=2,in_kzt=100000.,out_kzt=200000.,
           in_tx=3,out_tx=3,pass_through=2.,dwell_days=1.,pagerank=.1,authority_score=.1)
    r.update(kw); return SimpleNamespace(**r)

@pytest.mark.parametrize('params,expected',[
 ({'isolated':True},'peripheral'),
 ({'truncated_by_depth':True,'depth':4,'out_deg':0},'abstained_boundary'),
 ({'genuine_terminal':True,'out_deg':0},'terminal'),
 ({'in_deg':8,'pass_through':.5},'consolidator'),
 ({'in_deg':7,'pass_through':.5},'peripheral'),
 ({'in_deg':8,'pass_through':.50001},'peripheral'),
 ({'in_deg':8,'pass_through':float('nan')},'consolidator'),
 ({'out_deg':20},'distributor'),
 ({'out_deg':19},'peripheral'),
 ({'pass_through':.8},'transit'),
 ({'pass_through':1.2},'transit'),
 ({'pass_through':.79999},'peripheral'),
 ({'pass_through':1.20001},'peripheral'),
 ({'in_deg':4,'out_deg':4},'coordinator'),
 ({'in_deg':3,'out_deg':4},'peripheral'),
 ({'in_deg':4,'out_deg':3},'peripheral'),
 ({'in_tx':1,'out_tx':1},'abstained_single_observation'),
 ({'in_tx':1,'out_tx':2},'peripheral'),
 ({'is_seed':True,'in_deg':0,'out_deg':3},'peripheral'),
 ({'in_deg':8,'pass_through':.4,'out_deg':25},'consolidator'),
 ({'out_deg':20,'pass_through':1},'distributor'),
 ({'in_tx':1,'out_tx':1,'pass_through':1},'transit'),
])
def test_role_boundaries_and_precedence(params,expected):
    role,score,evidence=roles._classify(row(**params))
    assert role==expected
    assert math.isfinite(score) and 0<=score<=1
    assert evidence

@pytest.mark.parametrize('lag',[-10,0,1,2,10,float('nan')])
def test_transit_is_ratio_only_as_documented(lag):
    assert roles._classify(row(pass_through=1,dwell_days=lag))[0]=='transit'

@pytest.mark.parametrize('seed',[False,True])
def test_isolated_role_low_confidence(seed):
    result=roles._classify(row(isolated=True,is_seed=seed))
    assert result[0]=='peripheral' and result[1]<=.1

@pytest.mark.parametrize('ratio',[.1,.4,.9,1.1,2])
def test_seed_role_does_not_use_unobserved_inflow(ratio):
    # Project AGENTS.md explicitly states seed roles use outbound data only.
    r=row(is_seed=True,in_deg=8,out_deg=3,pass_through=ratio)
    assert roles._classify(r)[0] not in {'consolidator','transit'}

@pytest.mark.parametrize('degree',[20,60,116])
def test_outbound_only_seed_can_be_distributor(degree):
    # Useful behavioural check: visible high fan-out is evidence even when inflow is absent.
    assert roles._classify(row(is_seed=True,in_deg=0,out_deg=degree))[0]=='distributor'

def test_role_assignment_does_not_mutate_input():
    frame=pd.DataFrame([vars(row()),vars(row(pass_through=1))]); before=frame.copy(deep=True)
    roles.assign(frame); pd.testing.assert_frame_equal(frame,before)

@pytest.mark.parametrize('count',[1,2,5,25,30])
def test_priority_constant_features_finite(count):
    frame=pd.DataFrame([dict(vars(row(gid=100+i)),role='peripheral') for i in range(count)])
    result,top=priority.rank(frame)
    assert np.isfinite(result.priority_score).all()
    assert result.priority_score.eq(0).all()
    assert len(top)==min(count,25)

def test_priority_no_input_mutation():
    frame=pd.DataFrame([dict(vars(row()),role='transit')]); before=frame.copy(deep=True)
    priority.rank(frame); pd.testing.assert_frame_equal(frame,before)

def test_seed_priority_invariant_to_inflow():
    frame=pd.DataFrame([dict(vars(row(gid=1,is_seed=True)),role='distributor'),
                        dict(vars(row(gid=2,in_kzt=200000,in_deg=10,authority_score=.3)),role='distributor')])
    first=priority.rank(frame)[0].iloc[0].priority_score
    frame.loc[0,'in_kzt']=1e9
    assert priority.rank(frame)[0].iloc[0].priority_score==first

@pytest.mark.parametrize('params,state',[
 ({'in_deg':0,'out_deg':0,'hop_from_seed':0},'isolated'),
 ({'hop_from_seed':4},'truncated_at_depth'),
 ({'is_seed':True,'hop_from_seed':0},'outbound_only'),
 ({'in_deg':0,'hop_from_seed':2},'outbound_only'),
 ({'out_deg':0,'hop_from_seed':2},'inbound_only'),
 ({'hop_from_seed':2},'fully_observed'),
])
def test_completeness_states(params,state):
    assert completeness._state(row(**params))==state

@pytest.mark.parametrize('state',completeness.KNOWLEDGE_STATES)
@pytest.mark.parametrize('depth',[0,2,4])
def test_confidence_caps(state,depth):
    r=row(hop_from_seed=depth,outbound_known=depth<4,downstream_unresolved=.5,knowledge_state=state)
    score=completeness._confidence(r)
    assert 0<=score<=completeness.CONFIDENCE_CAPS[state]

def test_reachability_matches_networkx_on_cycles(synthetic):
    d=synthetic([(1,2,'2026-07-01',10),(2,3,'2026-07-01',10),(3,1,'2026-07-01',10),(3,4,'2026-07-01',10)],
                [(1,0,True),(2,1,False),(3,2,False),(4,4,False),(5,0,True)])
    result=completeness._reachability(d,d.nodes)
    for r in result.itertuples():
        desc=nx.descendants(d.graph,r.gid)
        assert r.descendants==len(desc)
        assert r.descendants_truncated==len(desc&{4})

def test_cycle_detector_known_triangle(synthetic):
    d=synthetic([(1,2,'2026-07-01',100),(2,3,'2026-07-02',80),(3,1,'2026-07-03',60)])
    result=flows.cycles(d)
    assert len(result)==1 and result.iloc[0].length==3
    assert result.iloc[0].min_leg_kzt==60 and result.iloc[0].total_kzt==240

def test_cycle_free_graph_returns_empty_schema(synthetic):
    d=synthetic([(1,2,'2026-07-01',10)])
    r=flows.cycles(d); assert r.empty and 'path' in r

def test_no_reciprocal_pairs_returns_empty_schema(synthetic):
    d=synthetic([(1,2,'2026-07-01',10)])
    r=flows.reciprocal_pairs(d); assert r.empty and 'returned_share' in r

def test_reciprocal_pair_ratio(synthetic):
    d=synthetic([(1,2,'2026-07-01',100),(2,1,'2026-07-02',25)])
    r=flows.reciprocal_pairs(d).iloc[0]
    assert r.returned_share==.25 and r.n_tx==2

def test_chains_are_valid_seed_to_target_paths(synthetic):
    d=synthetic([(1,2,'2026-07-01',10),(2,3,'2026-07-01',10)])
    assert flows.chains_from_seeds(d,3)==[[1,2,3]]

@pytest.mark.parametrize('boundary',[0,1,4])
def test_chain_cutoff(synthetic,boundary):
    d=synthetic([(1,2,'2026-07-01',10),(2,3,'2026-07-01',10)])
    paths=flows.chains_from_seeds(d,3,max_len=boundary)
    assert all(len(p)-1<=boundary for p in paths)

@pytest.mark.parametrize('a,b,expected',[(100,100,True),(100,98,True),(100,102,True),(100,97.99,False),(100,102.01,False)])
def test_echo_tolerance_boundaries(a,b,expected): assert echoes._within(a,b)==expected

@pytest.mark.parametrize('amount,lag,expected',[(10000,0,1),(10000,1,1),(10000,2,0),(10200,0,1),(10201,0,0)])
def test_relay_detection_amount_and_time(synthetic,amount,lag,expected):
    d=synthetic([(1,2,'2026-07-01',10000),(2,3,f'2026-07-{1+lag:02d}',amount)])
    result=echoes.build(d,timeline.build(d)); assert sum(result.kind=='relay')==expected

def test_echo_does_not_match_outflow_before_inflow(synthetic):
    d=synthetic([(1,2,'2026-07-03',10000),(2,3,'2026-07-01',10000)])
    assert echoes.build(d,timeline.build(d)).empty

def test_split_conserves_amount(synthetic):
    d=synthetic([(1,2,'2026-07-01',10000),(2,3,'2026-07-01',4000),(2,4,'2026-07-02',6000)])
    r=echoes.build(d,timeline.build(d)); assert len(r)==1
    assert r.iloc[0].kind=='split' and r.iloc[0].out_kzt==10000

@pytest.mark.parametrize('targets',[2,3,4])
def test_fan_split_minimum_distinct_targets(synthetic,targets):
    d=synthetic([(1,2+i,'2026-07-01',5000) for i in range(targets)])
    r=echoes.build(d,timeline.build(d)); assert sum(r.kind=='fan_split')==(1 if targets>=3 else 0)

def test_fan_split_duplicate_recipient_total(synthetic):
    d=synthetic([(1,2,'2026-07-01',5000),(1,2,'2026-07-01',5000),(1,3,'2026-07-01',5000),(1,4,'2026-07-01',5000)])
    r=echoes.build(d,timeline.build(d)); fan=r[r.kind=='fan_split'].iloc[0]
    assert fan.out_kzt==20000, 'Total must include repeated transfers, not only unique recipients'

def test_echo_consumption_does_not_reuse_transfer(synthetic):
    d=synthetic([(1,2,'2026-07-01',10000),(4,2,'2026-07-01',10000),(2,3,'2026-07-01',10000)])
    r=echoes.build(d,timeline.build(d)); assert len(r)==1

def test_echo_records_preserve_large_ids(synthetic):
    a,b,c=100000000000000001,100000000000000002,100000000000000003
    d=synthetic([(a,b,'2026-07-01',10000),(b,c,'2026-07-01',10000)])
    tl=timeline.build(d); records=echoes.records(echoes.build(d,tl),tl)
    assert records[0]['gid']==str(b)
    assert records[0]['legs'][0]['s']==str(a)

def test_echo_csv_reconstruction_excludes_other_dates(synthetic):
    d=synthetic([(1,2,'2026-07-01',10000),(2,3,'2026-07-01',10000),(1,2,'2026-07-20',7000)])
    tl=timeline.build(d); r=echoes.build(d,tl); r.attrs={}
    legs=echoes.legs(r,tl)
    assert all(x['date'] in {'2026-07-01','2026-07-02'} for x in legs[0]['legs'])

def test_timeline_includes_empty_days(synthetic):
    d=synthetic([(1,2,'2026-07-16',10)])
    days=timeline.days(timeline.build(d))
    assert len(days)==31 and days[0]['date']=='2026-07-01' and days[-1]['date']=='2026-07-31'
    assert days[0]['transfers']==[] and days[15]['kzt']==10

def test_timeline_same_pair_same_day_aggregates(synthetic):
    d=synthetic([(1,2,'2026-07-01',10),(1,2,'2026-07-01',15)])
    r=timeline.build(d); assert len(r)==1 and r.iloc[0].n_tx==2 and r.iloc[0].sum_kzt==25

@pytest.mark.parametrize('value,expected',[(np.int64(7),7),(np.float64(1.25),1.25),(np.bool_(True),True),
 (float('nan'),None),(float('inf'),None),(-float('inf'),None),(pd.NaT,None),(None,None)])
def test_json_scalar_sanitisation(value,expected):
    assert viewdata._pyify(value)==expected

def test_json_nested_sanitisation():
    result=viewdata._pyify({'items':np.array([1.,float('nan')]),'flag':np.bool_(True)})
    assert json.loads(json.dumps(result,allow_nan=False))=={'items':[1.,None],'flag':True}

def test_id_stringification_no_mutation():
    frame=pd.DataFrame({'gid':[100000000000000001],'breaking_point_gid':[100000000000000003]})
    before=frame.copy(); result=viewdata._stringify_gids(frame,('breaking_point_gid',))
    assert result.iloc[0].gid=='100000000000000001'
    assert result.iloc[0].breaking_point_gid=='100000000000000003'
    pd.testing.assert_frame_equal(frame,before)

@pytest.mark.parametrize('mutation',['amount','count','missing_pair'])
def test_integrity_detects_edge_transaction_disagreement(synthetic,mutation):
    d=synthetic([(1,2,'2026-07-01',10000),(2,3,'2026-07-01',10000)])
    if mutation=='amount': d.tx.loc[0,'sum_kzt']=20000
    if mutation=='count': d.tx=pd.concat([d.tx,d.tx.iloc[[0]]],ignore_index=True)
    if mutation=='missing_pair': d.tx=d.tx.iloc[1:]
    assert not dataio.integrity_report(d)['edges_match_transactions']
