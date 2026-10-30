"""Read-only browser QA for the reference-inspired dashboard (local server required)."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / 'output' / 'dashboard-review'
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    def settled():
        page.wait_for_function('document.querySelector(".stApp")?.dataset.testScriptState === "notRunning"', timeout=60000)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8599')
    page.locator('input[type=text]').first.fill('chucuahang')
    page.locator('input[type=password]').first.fill('123')
    page.keyboard.press('Enter')
    page.locator('.mx-summary-grid').wait_for(timeout=60000)
    settled()
    page.wait_for_function('window.mixueMotion?.version === 4', timeout=30000)
    page.wait_for_timeout(1200)
    report = {'screens': [], 'interactions': {}, 'browser_errors': errors}

    for width, height in [(1920,1080),(1440,1000),(1280,900),(1024,900),(768,1024),(430,932),(390,844),(375,812),(320,740)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(500)
        if width < 768:
            collapse = page.locator('[data-testid=stSidebarCollapseButton] button')
            box = collapse.bounding_box() if collapse.count() else None
            if box and box['x'] >= 0 and box['x'] < width:
                collapse.click()
                page.wait_for_timeout(350)
        geometry = page.evaluate('''() => {
          const main = document.querySelector('.stMain');
          const content = document.querySelector('.stMainBlockContainer');
          return {width:innerWidth, documentWidth:document.documentElement.scrollWidth,
            mainWidth:main.clientWidth, mainScrollWidth:main.scrollWidth,
            contentWidth:content.getBoundingClientRect().width,
            dockVisible:getComputedStyle(document.querySelector('.st-key-mobile_dock')).display !== 'none',
            kpiColumns:getComputedStyle(document.querySelector('.mx-kpis')).gridTemplateColumns,
            typography:getComputedStyle(document.querySelector('.mx-kpi small')).fontSize};
        }''')
        page.screenshot(path=str(OUT / f'home-{width}.png'), full_page=width in [1440,390])
        report['screens'].append(geometry)
        assert geometry['documentWidth'] <= width, geometry
        assert geometry['mainScrollWidth'] <= geometry['mainWidth'] + 1, geometry
        assert geometry['dockVisible'] == (width < 768), geometry

    page.set_viewport_size({'width':1440,'height':1000})
    page.keyboard.press('Control+k')
    page.locator('.mx-command[open]').wait_for()
    page.locator('.mx-command input').fill('du bao')
    assert page.locator('.mx-command-results button:visible').count() == 1
    page.keyboard.press('Enter')
    page.locator('.mx-hero[data-scene="Dự báo"]').wait_for(timeout=30000)
    report['interactions']['command_search'] = True

    for scene in ['Trang chủ','Báo cáo & kho','Dự báo','Sơ chế','Nhập hàng','Tem & công thức','👥 Quản lý nhân viên','💬 Tuyết Vương AI']:
        # Search results use the same allowed pages as the sidebar.
        page.locator('.mx-search').click()
        page.locator('.mx-command input').fill('')
        page.locator('.mx-command-results button').filter(has_text=scene).first.click()
        page.locator('.mx-hero').filter(has=page.locator('h2')).wait_for()
        page.wait_for_function('(scene) => document.querySelector(".mx-hero")?.dataset.scene === scene', arg=scene)
        settled()
        page.wait_for_timeout(900)
        assert page.locator('[data-testid=stException]').count() == 0, scene
        if scene in ['💬 Tuyết Vương AI','Tem & công thức','👥 Quản lý nhân viên']:
            page.screenshot(path=str(OUT / f'page-{scene.split()[-1]}.png'))
        report['interactions'][scene] = True
        for width in [768,390,320]:
            page.set_viewport_size({'width':width,'height':900})
            page.wait_for_timeout(800)
            geometry = page.evaluate('''() => {
              const main = document.querySelector('.stMain');
              return {width:innerWidth, documentWidth:document.documentElement.scrollWidth,
                mainWidth:main.clientWidth, mainScrollWidth:main.scrollWidth};
            }''')
            assert geometry['mainScrollWidth'] <= geometry['mainWidth'] + 1, (scene, geometry)
            assert geometry['documentWidth'] <= width, (scene, geometry)
            report.setdefault('page_responsive', []).append({'page':scene,**geometry})
            if width == 390 and scene == '💬 Tuyết Vương AI':
                page.screenshot(path=str(OUT / 'chat-mobile.png'))
        page.set_viewport_size({'width':1440,'height':1000})

    page.locator('.mx-motion').click()
    assert page.evaluate('document.documentElement.dataset.mixueMotion') == 'paused'
    page.locator('.mx-motion').click()
    assert page.evaluate('document.documentElement.dataset.mixueMotion') == 'running'
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_timeout(200)
    assert page.evaluate('document.documentElement.dataset.mixueMotion') == 'paused'
    report['interactions']['motion_pause_and_system_preference'] = True
    page.emulate_media(reduced_motion='no-preference')

    page.set_viewport_size({'width':390,'height':844})
    page.locator('.st-key-mobile_dock label').filter(has_text='Trang chủ').click()
    page.locator('.mx-summary-grid').wait_for()
    settled()
    report['interactions']['mobile_navigation'] = True
    page.locator('.mx-shortcut').filter(has_text='Tem & công thức').click()
    page.locator('.mx-hero[data-scene="Tem & công thức"]').wait_for()
    settled()
    report['interactions']['shortcut_navigation'] = True
    assert not errors, errors
    (OUT / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    browser.close()
