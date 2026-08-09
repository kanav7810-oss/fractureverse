import { expect, type Page } from '@playwright/test'

/** Click a sidebar entry by its label and wait for the section heading. */
export async function open(page: Page, label: string, heading: string) {
  await page.getByRole('button', { name: label, exact: false }).first().click()
  await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
}

/** Land on the app in live mode, with the backend probe already settled. */
export async function boot(page: Page) {
  await page.goto('/')
  await expect(page.getByTestId('app-mode')).toContainText('live')
}

/** The horizontal scroll rule. No page ever grows a horizontal scrollbar on the body. */
export async function expectNoBodyOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
}
