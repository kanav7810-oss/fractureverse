import { expect, test } from '@playwright/test'
import { boot, open } from './helpers'

const stat = (page: any, label: string) =>
  page.locator('.stat', { has: page.locator('.k', { hasText: new RegExp(`^${label}$`) }) })
    .first()
    .locator('.v')

test.describe('solver playground', () => {
  test.beforeEach(async ({ page }) => {
    await boot(page)
    await open(page, 'Solver playground', 'Solver playground')
  })

  test('the default live solve matches the aerospace anchor case', async ({ page }) => {
    await expect(page.getByTestId('solver-stats')).toBeVisible()
    await expect(stat(page, 'Cycles to failure')).toContainText('2672')
    await expect(stat(page, 'Critical crack a_c')).toContainText('16.1')
  })

  test('the selectors are generated from capabilities', async ({ page }) => {
    const caps = await page.request.get('/api/capabilities').then((r) => r.json())
    const geometry = page.locator('select').nth(2)
    await expect(geometry.locator('option')).toHaveCount(caps.geometries.length)
    const law = page.locator('select').nth(3)
    await expect(law.locator('option')).toHaveCount(caps.growth_laws.length)
  })

  test('moving the stress slider changes the life', async ({ page }) => {
    const before = await stat(page, 'Cycles to failure').textContent()
    await page.locator('input[type=range]').first().fill('8')
    await expect(stat(page, 'Cycles to failure')).not.toHaveText(String(before))
  })

  test('an out of range a over W is refused, not extrapolated', async ({ page }) => {
    await page.locator('select').nth(2).selectOption('compact')
    await page.locator('input[type=range]').nth(1).fill('0')
    await expect(page.getByTestId('no-solution')).toBeVisible()
    await expect(page.getByTestId('no-solution')).toContainText('0.2')
  })

  test('the growth history is returned by the live solve', async ({ page }) => {
    await expect(page.getByTestId('growth-chart')).toBeVisible()
    await expect(page.getByTestId('growth-chart').locator('svg')).toBeVisible()
  })

  test('the elastic plastic theory adds the J and CTOD block', async ({ page }) => {
    await page.locator('select').nth(4).selectOption('epfm')
    await expect(page.getByRole('heading', { name: 'Elastic plastic result at the same point' }))
      .toBeVisible()
    await expect(stat(page, 'J over J_IC')).not.toHaveText('n/a')
  })

  test('the LSTM prediction sits beside the closed form life', async ({ page }) => {
    await expect(page.getByTestId('predict-stats')).toBeVisible()
    const value = async (label: string) =>
      Number((await stat(page, label).textContent())!.match(/^[0-9.e+-]+/i)![0])
    expect(await value('Life, LSTM')).toBeGreaterThan(0)
    expect(await value('Life, closed form')).toBeGreaterThan(0)
  })

  test('offline mode falls back to the precomputed grid', async ({ page }) => {
    await page.route('**/api/health', (route) => route.abort())
    await page.goto('/')
    await open(page, 'Solver playground', 'Solver playground')
    await expect(page.getByTestId('solver-mode')).toContainText('precomputed grid')
    await expect(stat(page, 'Cycles to failure')).toContainText('2672')
  })
})
