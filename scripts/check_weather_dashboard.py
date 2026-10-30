"""Check the weather comparison layout on a running local dashboard (port 8601)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

out = Path('output/dashboard-review')
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8601')
    page.locator('input[type=text]').first.fill('quanly')
    page.locator('input[type=password]').first.fill('123')
    page.keyboard.press('Enter')
    page.locator('.mx-summary-grid').wait_for(timeout=90000)
    page.locator('.mx-search').click()
    page.locator('.mx-command input').fill('du bao')
    page.locator('.mx-command-results button:visible').first.click()
    page.locator('.mx-hero[data-scene="Dự báo"]').wait_for(timeout=30000)
    today = datetime.now(timezone(timedelta(hours=7))).date()
    picker = page.get_by_test_id('stDateInput').locator('input').first
    picker.fill(today.isoformat())
    picker.press('Tab')
    page.keyboard.press('Escape')
    page.get_by_role('button', name='🚀 Chạy Mô hình Dự báo', exact=True).click()
    page.get_by_text('Bảng Dự báo Sản lượng Menu Ngày', exact=False).wait_for(timeout=90000)
    page.wait_for_function('document.querySelector(".stApp")?.dataset.testScriptState === "notRunning"')
    assert not page.locator('[data-testid=stException]').count()
    assert 'Thời tiết khu vực' in page.locator('.stMain').inner_text()
    page.get_by_text('ước tính thời tiết', exact=False).wait_for(timeout=30000)
    report = {'screens': [], 'browser_errors': errors}
    for width, height in [(1440, 1000), (768, 1024), (390, 844), (320, 740)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(400)
        collapse = page.locator('[data-testid=stSidebarCollapseButton] button')
        box = collapse.bounding_box() if collapse.count() else None
        if width < 768 and box and 0 <= box['x'] < width:
            collapse.click()
            page.wait_for_timeout(300)
        page.get_by_text('Thời tiết khu vực:', exact=False).evaluate("element => element.scrollIntoView({block: 'start'})")
        page.wait_for_timeout(200)
        geometry = page.evaluate('''() => ({width:innerWidth, documentWidth:document.documentElement.scrollWidth,
            mainWidth:document.querySelector('.stMain').clientWidth,
            mainScrollWidth:document.querySelector('.stMain').scrollWidth})''')
        assert geometry['documentWidth'] <= width, geometry
        assert geometry['mainScrollWidth'] <= geometry['mainWidth'] + 1, geometry
        page.screenshot(path=str(out / f'weather-{width}.png'), full_page=True)
        report['screens'].append(geometry)
    assert not errors, errors
    (out / 'weather-responsive.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    browser.close()
