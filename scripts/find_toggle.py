from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto('http://localhost:8501', wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator("button:has-text('NV Chính Thức')").first.click()
    page.wait_for_timeout(3000)
    
    # Check all elements with role='button' or button tags
    elements = page.evaluate("""
        () => {
            const res = [];
            document.querySelectorAll('button, [role="button"], [data-testid]').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.left >= 0 && rect.left < window.innerWidth) {
                    res.push({
                        tag: el.tagName,
                        text: el.innerText ? el.innerText.trim().slice(0, 30) : '',
                        testId: el.getAttribute('data-testid') || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        className: el.className || '',
                        x: Math.round(rect.left),
                        y: Math.round(rect.top),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height)
                    });
                }
            });
            return res;
        }
    """)
    print("Visible interactive elements on screen:")
    for el in elements:
        if el['x'] < 200 and el['y'] < 150: # top left corner
            print("Top-left element:", el)
            
    browser.close()
