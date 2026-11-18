import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/mapGeometry.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
const { pointAlongRoute, cameraBounds } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} should equal ${expected}`)

test('patrol movement follows length of each route segment, including end points', () => {
  const route = [{ x: .1, y: .1 }, { x: .4, y: .1 }, { x: .4, y: .5 }]
  assert.deepEqual(pointAlongRoute(route, 0), route[0])
  const halfway = pointAlongRoute(route, 50)
  near(halfway.x, .4); near(halfway.y, .15)
  assert.deepEqual(pointAlongRoute(route, 100), route[2])
  assert.deepEqual(pointAlongRoute(route, 130), route[2])
  assert.deepEqual(pointAlongRoute(route, -20), route[0])
})

test('empty and duplicate route points never produce NaN or errors', () => {
  assert.equal(pointAlongRoute([], 50), null)
  assert.deepEqual(pointAlongRoute([{ x: .3, y: .4 }], 20), { x: .3, y: .4 })
  assert.deepEqual(pointAlongRoute([{ x: .3, y: .4 }, { x: .3, y: .4 }], 80), { x: .3, y: .4 })
  assert.deepEqual(pointAlongRoute([{ x: 0, y: 0 }, { x: 0, y: 0 }, { x: 1, y: 0 }], 50), { x: .5, y: 0 })
})

test('zoomed and unzoomed camera cannot pan beyond supplied image', () => {
  assert.deepEqual(cameraBounds({ x: -200, y: 5000 }, 1, 2400, 1500), { x: 1200, y: 750 })
  assert.deepEqual(cameraBounds({ x: -200, y: 5000 }, 2, 2400, 1500), { x: 600, y: 1125 })
  assert.deepEqual(cameraBounds({ x: 1300, y: 800 }, 2, 2400, 1500), { x: 1300, y: 800 })
})
