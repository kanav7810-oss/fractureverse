import { expect, test } from '@playwright/test'

test.describe('backend contract', () => {
  test('health reports the live solver and the figure count', async ({ request }) => {
    const r = await request.get('/api/health')
    expect(r.ok()).toBe(true)
    const body = await r.json()
    expect(body.live_solver).toBe(true)
    expect(body.figures).toBe(17)
  })

  test('capabilities matches the fixture the frontend was built against', async ({ request }) => {
    const live = await request.get('/api/capabilities').then((r) => r.json())
    const fixture = await request.get('/data/capabilities.json').then((r) => r.json())
    expect(live).toEqual(fixture)
  })

  test('solve reproduces the aerospace anchor case', async ({ request }) => {
    const r = await request.post('/api/solve', {
      data: {
        domain: 'aerospace', material: 'Al2024-T3', theory: 'lefm',
        load: { sigma_max: 150e6, R: 0.1 },
        crack: { a0: 1e-3, geometry: 'center', W: 0.1 },
      },
    })
    const body = await r.json()
    expect(body.N_f).toBeCloseTo(2671.5099717, 4)
    expect(body.a_c).toBeCloseTo(0.0160522541, 8)
    expect(body.history.a).toHaveLength(40)
  })

  test('solve refuses an out of range a over W with a usable message', async ({ request }) => {
    const r = await request.post('/api/solve', {
      data: { crack: { a0: 0.09, geometry: 'center', W: 0.1 } },
    })
    expect(r.status()).toBe(422)
    expect((await r.json()).detail.error).toContain('a/W')
  })

  test('the slow theories are refused unless the caller opts in', async ({ request }) => {
    const r = await request.post('/api/solve', { data: { theory: 'peridynamic' } })
    expect(r.status()).toBe(413)
    expect((await r.json()).detail.hint).toContain('allow_slow')
  })

  test('predict returns a life close to the closed form integration', async ({ request }) => {
    const body = await request.post('/api/predict', { data: {} }).then((r) => r.json())
    expect(body.model).toBe('lstm')
    expect(body.life_ratio_error).toBeLessThan(0.25)
    expect(body.N_f_predicted).toBeGreaterThan(0)
  })

  test('the precomputed grid is not served in live mode', async ({ request }) => {
    const r = await request.get('/api/data/sweep.json')
    expect(r.status()).toBe(404)
    expect((await r.json()).detail.hint).toContain('/api/solve')
  })

  test('the figure endpoints list and serve the PNG', async ({ request }) => {
    const figs = await request.get('/api/figures').then((r) => r.json())
    expect(Object.keys(figs)).toHaveLength(17)
    const png = await request.get(`/api/figures/${Object.keys(figs)[0]}`)
    expect(png.headers()['content-type']).toContain('image/png')
  })

  test('the paper is downloadable as a PDF with no em dash in it', async ({ request }) => {
    const pdf = await request.get('/api/report')
    expect(pdf.status()).toBe(200)
    expect((await pdf.body()).length).toBeGreaterThan(10_000)
    const md = await request.get('/api/report?fmt=markdown').then((r) => r.text())
    expect(md).not.toContain(String.fromCharCode(0x2014))
    expect(md).toContain('FRACTUREVERSE')
  })
})
