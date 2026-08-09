import { expect, test } from '@playwright/test'
import { boot, open } from './helpers'

test.describe('surrogate models and the PINN', () => {
  test('the leaderboard reports the four models on the test split', async ({ page }) => {
    await boot(page)
    await open(page, 'Model leaderboard', 'Prognostic model leaderboard')
    const rows = page.locator('table tbody tr')
    await expect(rows).toHaveCount(4)
    await expect(page.locator('tr', { hasText: 'LSTM' }).first()).toContainText('0.0277')
  })

  test('switching the split changes the reported scores', async ({ page }) => {
    await boot(page)
    await open(page, 'Model leaderboard', 'Prognostic model leaderboard')
    const cell = page.locator('tr', { hasText: 'LSTM' }).first().locator('td.num').first()
    const test_value = await cell.textContent()
    await page.locator('select').first().selectOption('train')
    await expect(cell).not.toHaveText(String(test_value))
  })

  test('the R squared warning is on the page, not only in the handoff', async ({ page }) => {
    await boot(page)
    await open(page, 'Model leaderboard', 'Prognostic model leaderboard')
    await expect(page.locator('.note', { hasText: 'Finding 6.3' })).toContainText('RMSE in decades')
  })

  test('SHAP attribution renders and names the dropped leaky features', async ({ page }) => {
    await boot(page)
    await open(page, 'Feature attribution', 'Feature attribution')
    await expect(page.locator('.recharts-surface')).toBeVisible()
    const dropped = page.locator('.badge.warn')
    await expect(dropped.first()).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Features dropped on purpose' })).toBeVisible()
  })

  test('the parity explorer holds the 225 held out trajectories', async ({ page }) => {
    await boot(page)
    await open(page, 'Parity explorer', 'Held out parity explorer')
    await expect(page.locator('.recharts-surface')).toBeVisible()
    const ml = await page.request.get('/api/data/ml.json').then((r) => r.json())
    expect(ml.parity.y).toHaveLength(225)
  })

  test('the PINN view quotes all four routes to K_I', async ({ page }) => {
    await boot(page)
    await open(page, 'PINN against XFEM', 'Physics informed network against XFEM')
    for (const k of ['K_I, PINN opening fit', 'K_I, XFEM opening fit',
                     'K_I, interaction integral', 'K_I closed form']) {
      await expect(page.locator('.stat .k', { hasText: k }).first()).toBeVisible()
    }
  })

  test('the opening profile finding is stated beside the chart', async ({ page }) => {
    await boot(page)
    await open(page, 'PINN against XFEM', 'Physics informed network against XFEM')
    await expect(page.locator('.note', { hasText: 'Finding 6.4' })).toContainText('13 percent low')
  })
})
