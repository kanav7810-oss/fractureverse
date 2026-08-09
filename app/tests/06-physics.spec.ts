import { expect, test } from '@playwright/test'
import { boot, open } from './helpers'

test.describe('XFEM and peridynamics', () => {
  test('the crack path and the K history both render', async ({ page }) => {
    await boot(page)
    await open(page, 'XFEM crack path', 'XFEM crack path')
    await expect(page.getByRole('heading', { name: 'Path in the panel' })).toBeVisible()
    await expect(page.locator('.recharts-surface')).toHaveCount(2)
  })

  test('one XFEM single step solve per domain, each against the analytical K', async ({ page }) => {
    await boot(page)
    await open(page, 'XFEM crack path', 'XFEM crack path')
    const cards = page.locator('.hscroll .panel')
    await expect(cards).toHaveCount(3)
    await expect(cards.first()).toContainText('K_I analytical')
  })

  test('the peridynamic damage field draws and reports branching', async ({ page }) => {
    await boot(page)
    await open(page, 'Peridynamic damage', 'Peridynamic damage and branching')
    await expect(page.locator('canvas')).toBeVisible()
    await expect(page.getByText('Branch columns')).toBeVisible()
  })

  test('the fracture energy check table is present', async ({ page }) => {
    await boot(page)
    await open(page, 'Peridynamic damage', 'Peridynamic damage and branching')
    await expect(page.getByRole('heading', { name: 'Fracture energy check' })).toBeVisible()
    await expect(page.locator('table td.mono').first()).toBeVisible()
  })

  test('the propagation is never run live from the browser', async ({ page }) => {
    const calls: string[] = []
    page.on('request', (r) => r.url().includes('/api/solve') && calls.push(r.url()))
    await boot(page)
    await open(page, 'XFEM crack path', 'XFEM crack path')
    await open(page, 'Peridynamic damage', 'Peridynamic damage and branching')
    expect(calls).toHaveLength(0)
  })
})
