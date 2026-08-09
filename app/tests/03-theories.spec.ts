import { expect, test } from '@playwright/test'
import { boot, open } from './helpers'

test.describe('theory explorer', () => {
  test.beforeEach(async ({ page }) => {
    await boot(page)
    await open(page, 'Theory explorer', 'Theory explorer')
  })

  test('every theory in capabilities has a card', async ({ page }) => {
    const caps = await page.request.get('/api/capabilities').then((r) => r.json())
    await expect(page.locator('.hscroll .navbtn')).toHaveCount(caps.theories.length)
  })

  test('selecting a theory shows its blurb and the domains it serves', async ({ page }) => {
    await page.locator('.hscroll .navbtn').nth(2).click()
    const panel = page.locator('.panel').first()
    await expect(panel.locator('h2')).toBeVisible()
    await expect(panel.getByText('Available for')).toBeVisible()
  })

  test('the geometry table lists every accepted geometry key', async ({ page }) => {
    const caps = await page.request.get('/api/capabilities').then((r) => r.json())
    for (const g of caps.geometries) {
      await expect(page.locator('td.mono', { hasText: new RegExp(`^${g}$`) })).toBeVisible()
    }
  })
})
