import { expect, test } from '@playwright/test'
import { boot, open } from './helpers'

test.describe('overview', () => {
  test.beforeEach(async ({ page }) => {
    await boot(page)
    await open(page, 'Overview', 'FRACTUREVERSE')
  })

  test('the headline counts come from capabilities and the summary', async ({ page }) => {
    await expect(page.getByText('Theories', { exact: true }).locator('..')).toContainText('4')
    await expect(page.getByText('Domains', { exact: true }).locator('..')).toContainText('3')
    await expect(page.getByText('Figures', { exact: true }).locator('..')).toContainText('17')
  })

  test('both Paris lives are on screen for the aerospace anchor case', async ({ page }) => {
    const row = page.locator('tr', { hasText: 'aerospace' }).first()
    await expect(row).toContainText('2671.5')
    await expect(row).toContainText('15217')
  })

  test('all four honesty findings are visible, not only in the source', async ({ page }) => {
    await expect(page.getByText('The specified Paris coefficient is conservative')).toBeVisible()
    await expect(page.getByText('Peridynamic strength depends on the horizon')).toBeVisible()
    await expect(page.getByText('The surrogate task is close to log linear')).toBeVisible()
    await expect(page.getByText('The PINN opening is low at the crack centre')).toBeVisible()
  })

  test('the three domains each carry a source line', async ({ page }) => {
    const cards = page.locator('.hscroll .panel')
    await expect(cards).toHaveCount(3)
    for (const name of ['aerospace', 'biomedical', 'civil']) {
      await expect(cards.filter({ hasText: name }).first()).toContainText('cycles per year', {
        ignoreCase: true,
      })
    }
  })
})
