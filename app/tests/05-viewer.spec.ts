import { expect, test } from '@playwright/test'
import { boot, open } from './helpers'

test.describe('volumetric crack viewer', () => {
  test.beforeEach(async ({ page }) => {
    await boot(page)
    await open(page, 'Crack viewer 3D', 'Volumetric crack viewer')
  })

  test('the canvas renders and the HUD reports one draw call', async ({ page }) => {
    await expect(page.locator('.viewer canvas')).toBeVisible()
    await expect(page.locator('.hud')).toContainText('one draw call')
  })

  test('the default resolution is the 50,000 cell grid', async ({ page }) => {
    await expect(page.locator('.hud')).toContainText('50,000 instances')
    await expect(page.locator('.viewer + .panel select')).toHaveValue('50x50x20')
  })

  test('the fallback resolution is selectable and keeps one draw call', async ({ page }) => {
    await page.locator('.viewer + .panel select').selectOption('30x30x10')
    await expect(page.locator('.hud')).toContainText('9,000 instances')
    await expect(page.locator('.hud')).toContainText('one draw call')
  })

  test('the horizon implied strength is never shown without the applied stress', async ({ page }) => {
    const note = page.locator('.note', { hasText: 'Finding 6.2' })
    await expect(note).toContainText('MPa against the')
    await expect(note).toContainText('applied')
  })
})
