import re
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.browser
PAGES=['start','review','account','structures','replay','echoes','limits']

@pytest.mark.parametrize('section',PAGES)
def test_every_screen_opens_without_script_errors(page,section):
    page.locator(f'#rail a[href="#{section}"]').click()
    expect(page.locator(f'#p-{section}')).to_be_visible()
    assert not page.errors

def test_default_language_is_english(page):
    expect(page.locator('html')).to_have_attribute('lang','en')

@pytest.mark.parametrize('lang',['ru','kk','en'])
def test_language_switch_persists(page,lang):
    page.locator(f'#lang button[data-l="{lang}"]').click()
    expect(page.locator('html')).to_have_attribute('lang',lang)
    page.reload(); expect(page.locator('html')).to_have_attribute('lang',lang)
    assert not page.errors

def test_theme_toggle_persists(page):
    page.locator('#theme').click()
    expect(page.locator('html')).to_have_attribute('data-theme','dark')
    page.reload(); expect(page.locator('html')).to_have_attribute('data-theme','dark')
    page.locator('#theme').click()
    expect(page.locator('html')).not_to_have_attribute('data-theme','dark')

@pytest.mark.parametrize('kind',['top','boundary','isolated','transit'])
def test_search_account_by_full_id(page,pipeline,kind):
    nodes=pipeline['graph']['nodes']
    if kind=='top': gid=pipeline['graph']['top'][0]['gid']
    elif kind=='boundary': gid=next(n['id'] for n in nodes if n['role']=='abstained_boundary')
    elif kind=='isolated': gid=next(n['id'] for n in nodes if n['inDeg']==n['outDeg']==0)
    else: gid=next(n['id'] for n in nodes if n['role']=='transit')
    page.locator('#q').fill(gid)
    expect(page.locator('#p-account')).to_be_visible()
    expect(page.locator('#panel-a')).to_contain_text(gid)
    assert not page.errors

def test_unknown_account_has_no_stale_card(page,pipeline):
    gid=pipeline['graph']['top'][0]['gid']; page.locator('#q').fill(gid)
    expect(page.locator('#panel-a')).to_contain_text(gid)
    page.locator('#q').fill('999999999999999999')
    expect(page.locator('#panel-a')).not_to_contain_text(gid)
    assert not page.errors

def test_priority_row_opens_exact_account(page,pipeline):
    page.locator('#rail a[href="#review"]').click()
    row=page.locator('#p-review tr[data-gid]').first
    gid=row.get_attribute('data-gid'); row.click()
    expect(page.locator('#panel-a')).to_contain_text(gid)

def test_neighbourhood_and_whole_network_toggle(page):
    page.locator('#rail a[href="#account"]').click()
    for view in ['all','near']:
        b=page.locator(f'#view-a button[data-v="{view}"]'); b.click()
        expect(b).to_have_attribute('aria-pressed','true')
    assert not page.errors

def test_canvas_draws_nonuniform_content(page):
    page.locator('#rail a[href="#account"]').click()
    page.wait_for_timeout(100)
    result=page.locator('#cv-a').evaluate('''c => {
      const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
      let visible=0; for(let i=3;i<d.length;i+=4) if(d[i]) visible++;
      return {width:c.width,height:c.height,visible};
    }''')
    assert result['width']>0 and result['height']>0 and result['visible']>100

def test_group_selection(page):
    page.locator('#rail a[href="#structures"]').click()
    row=page.locator('#list-f [data-frm]').nth(1); row.click()
    expect(page.locator('#panel-f')).not_to_be_empty()
    assert not page.errors

def test_replay_play_and_pause(page):
    page.locator('#rail a[href="#replay"]').click()
    play=page.locator('#mod-replay .rp-play')
    play.click()
    expect(play).to_contain_text('Pause')
    play.click()
    expect(play).to_contain_text('Play')
    assert not page.errors

def test_replay_slider_first_last_day(page):
    page.locator('#rail a[href="#replay"]').click()
    slider=page.locator('#mod-replay input[type="range"]')
    for value in ['1','31']:
        slider.fill(value); slider.dispatch_event('input')
        expect(slider).to_have_value(value)
    assert not page.errors

def test_echo_cards_and_sort(page):
    page.locator('#rail a[href="#echoes"]').click()
    expect(page.locator('.ech-card').first).to_be_visible()
    select=page.locator('#mod-echoes select')
    for value in select.locator('option').evaluate_all('(xs)=>xs.map(x=>x.value)'):
        select.select_option(value)
        expect(page.locator('.ech-card').first).to_be_visible()
    assert not page.errors

def test_echo_open_account(page):
    page.locator('#rail a[href="#echoes"]').click()
    button=page.locator('.ech-open').first; gid=button.get_attribute('data-gid'); button.click()
    expect(page.locator('#panel-a')).to_contain_text(gid)

@pytest.mark.parametrize('width',[390,768,1440])
@pytest.mark.parametrize('section',['start','account','structures','echoes'])
def test_responsive_page_has_no_document_overflow(page,width,section):
    page.set_viewport_size({'width':width,'height':900})
    page.goto(page.url.split('#')[0]+'#'+section)
    expect(page.locator(f'#p-{section}')).to_be_visible()
    page.wait_for_timeout(100)
    sizes=page.evaluate('({scroll:document.documentElement.scrollWidth,width:innerWidth})')
    assert sizes['scroll']<=sizes['width']+2,sizes
    assert not page.errors

def test_no_external_network_requests(browser,server):
    ctx=browser.new_context(); p=ctx.new_page(); external=[]
    p.on('request',lambda r: external.append(r.url) if not r.url.startswith(server) else None)
    try:
        p.goto(server+'/web/'); p.locator('#rail a').first.wait_for()
        assert not external
    finally: ctx.close()

def test_missing_payload_shows_actionable_error(browser,server):
    ctx=browser.new_context(); p=ctx.new_page()
    p.route('**/out/graph.json',lambda route: route.fulfill(status=404,body='missing'))
    try:
        p.goto(server+'/web/')
        expect(p.locator('.boot')).to_contain_text('python3 run.py --serve')
    finally: ctx.close()

def test_unknown_route_falls_back_to_overview(page):
    page.goto(page.url.split('#')[0]+'#not-a-page')
    expect(page.locator('#p-start')).to_be_visible()
