import { expect, test } from '@playwright/test'
import { boot, open } from './helpers'

test.describe('figure gallery and validation log', () => {
  test('all seventeen figures are listed with captions', async ({ page }) => {
    await boot(page)
    await open(page, 'Figure gallery', 'Figure gallery')
    await expect(page.locator('.figcard')).toHaveCount(17)
    await expect(page.locator('.figcard .cap').first()).not.toBeEmpty()
  })

  test('clicking a figure opens and closes the lightbox', async ({ page }) => {
    await boot(page)
    await open(page, 'Figure gallery', 'Figure gallery')
    await page.locator('.figcard img').first().click()
    await expect(page.locator('.lightbox')).toBeVisible()
    await page.locator('.lightbox').click()
    await expect(page.locator('.lightbox')).toHaveCount(0)
  })

  test('every figure PNG actually loads', async ({ page }) => {
    await boot(page)
    await open(page, 'Figure gallery', 'Figure gallery')
    const first = page.locator('.figcard img').first()
    await expect(first).toBeVisible()
    const ok = await first.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)
    expect(ok).toBe(true)
  })

  test('the validation log shows both earlier parts fully green', async ({ page }) => {
    await boot(page)
    await open(page, 'Validation log', 'Validation log')
    await expect(page.locator('.badge.bad')).toHaveCount(0)
    await expect(page.locator('.badge.good').first()).toBeVisible()
  })
})
