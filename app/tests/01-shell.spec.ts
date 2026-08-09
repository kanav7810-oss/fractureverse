import { expect, test } from '@playwright/test'
import { boot, expectNoBodyOverflow, open } from './helpers'

test.describe('shell and data mode', () => {
  test('the twelve features are all in the sidebar', async ({ page }) => {
    await boot(page)
    const nav = page.locator('.navbtn')
    await expect(nav).toHaveCount(12)
    await expect(nav.first()).toContainText('Overview')
    await expect(nav.last()).toContainText('Validation log')
  })

  test('live mode is named on screen, not inferred', async ({ page }) => {
    await boot(page)
    await expect(page.getByTestId('app-mode')).toContainText('solves run in api/main.py')
    await open(page, 'Solver playground', 'Solver playground')
    await expect(page.getByTestId('solver-mode')).toContainText('live backend')
  })

  test('offline mode says so when the backend is unreachable', async ({ page }) => {
    await page.route('**/api/health', (route) => route.abort())
    await page.goto('/')
    await expect(page.getByTestId('app-mode')).toContainText('offline')
    await open(page, 'Solver playground', 'Solver playground')
    await expect(page.getByTestId('solver-mode')).toContainText('offline fixtures')
  })

  test('the body never grows a horizontal scrollbar', async ({ page }) => {
    await boot(page)
    await expectNoBodyOverflow(page)
    await open(page, 'Overview', 'FRACTUREVERSE')
    await expectNoBodyOverflow(page)
  })

  test('wide content scrolls inside its own strip', async ({ page }) => {
    await boot(page)
    const strip = page.locator('.hscroll').first()
    await expect(strip).toBeVisible()
    const scrollable = await strip.evaluate((el) => el.scrollWidth > el.clientWidth)
    expect(scrollable).toBe(true)
    await expectNoBodyOverflow(page)
  })

  test('no wheel handler is registered anywhere in the bundle', async ({ page }) => {
    await boot(page)
    const hijacked = await page.evaluate(() => {
      let seen = false
      const original = EventTarget.prototype.addEventListener
      EventTarget.prototype.addEventListener = function (type, ...rest: any[]) {
        if (type === 'wheel' || type === 'mousewheel') seen = true
        return original.call(this, type, ...(rest as [any]))
      }
      window.dispatchEvent(new Event('resize'))
      EventTarget.prototype.addEventListener = original
      return seen
    })
    expect(hijacked).toBe(false)
  })
})
