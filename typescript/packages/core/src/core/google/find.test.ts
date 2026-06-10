// ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========

import { describe, expect, it } from 'vitest'
import { FileStat, FileType, PathSpec } from '../../types.ts'
import { walkFind, type WalkFindDeps } from './find.ts'

function enoent(p: string): Error {
  const e = new Error(`ENOENT: ${p}`) as Error & { code: string }
  e.code = 'ENOENT'
  return e
}

function slashHint(child: string): boolean | null {
  return child.endsWith('/') ? true : null
}

interface FakeStat {
  size?: number | null
  modified?: string | null
  dir?: boolean
}

function makeDeps(
  tree: Record<string, string[]>,
  stats: Record<string, FakeStat> = {},
  isDirName: (child: string) => boolean | null = slashHint,
): WalkFindDeps {
  return {
    readdir: (spec) => {
      const children = tree[spec.original]
      if (children === undefined) return Promise.reject(enoent(spec.original))
      return Promise.resolve(children)
    },
    stat: (spec) => {
      const entry = stats[spec.original]
      if (entry === undefined) return Promise.reject(enoent(spec.original))
      return Promise.resolve(
        new FileStat({
          name: spec.original.split('/').pop() ?? '',
          size: entry.size ?? null,
          modified: entry.modified ?? null,
          type: entry.dir === true ? FileType.DIRECTORY : FileType.TEXT,
        }),
      )
    },
    isDirName,
  }
}

const ROOT = new PathSpec({ original: '/', directory: '/' })

describe('google walkFind', () => {
  it('walks recursively, strips trailing slashes, sorts by codepoint', async () => {
    const deps = makeDeps(
      {
        '/': ['/docs/', '/Zeta.txt', '/alpha.txt'],
        '/docs': ['/docs/readme.md'],
      },
      {
        '/Zeta.txt': { size: 1 },
        '/alpha.txt': { size: 1 },
        '/docs/readme.md': { size: 1 },
      },
    )
    const out = await walkFind(ROOT, deps)
    expect(out).toEqual(['/Zeta.txt', '/alpha.txt', '/docs', '/docs/readme.md'])
  })

  it('matches names against the trailing-slash-stripped entry', async () => {
    const deps = makeDeps({ '/': ['/docs/'], '/docs': [] })
    const out = await walkFind(ROOT, deps, { name: 'docs' })
    expect(out).toEqual(['/docs'])
  })

  it('classifies via the isDirName hint without calling stat', async () => {
    const deps = makeDeps(
      {
        '/': ['/owned', '/note.json'],
        '/owned': ['/owned/a.json'],
      },
      {},
      (child) => !child.endsWith('.json'),
    )
    const dirs = await walkFind(ROOT, deps, { type: 'd' })
    expect(dirs).toEqual(['/owned'])
    const files = await walkFind(ROOT, deps, { type: 'f' })
    expect(files).toEqual(['/note.json', '/owned/a.json'])
  })

  it('falls back to stat for slash-less entries when the hint is null', async () => {
    const deps = makeDeps(
      {
        '/': ['/docs', '/notes.txt'],
        '/docs': ['/docs/readme.md'],
      },
      {
        '/docs': { dir: true },
        '/notes.txt': { size: 10 },
        '/docs/readme.md': { size: 5 },
      },
    )
    const dirs = await walkFind(ROOT, deps, { type: 'd' })
    expect(dirs).toEqual(['/docs'])
    const files = await walkFind(ROOT, deps, { type: 'f' })
    expect(files).toEqual(['/docs/readme.md', '/notes.txt'])
  })

  it('uses GNU depth semantics with top-level children at depth 1', async () => {
    const deps = makeDeps({
      '/': ['/docs/', '/notes.txt'],
      '/docs': ['/docs/inner.txt'],
    })
    expect(await walkFind(ROOT, deps, { maxDepth: 0 })).toEqual([])
    expect(await walkFind(ROOT, deps, { maxDepth: 1 })).toEqual(['/docs', '/notes.txt'])
    expect(await walkFind(ROOT, deps, { minDepth: 1 })).toEqual([
      '/docs',
      '/docs/inner.txt',
      '/notes.txt',
    ])
    expect(await walkFind(ROOT, deps, { minDepth: 2 })).toEqual(['/docs/inner.txt'])
  })

  it('applies size filters to files only, treating null size as 0', async () => {
    const deps = makeDeps(
      {
        '/': ['/big.txt', '/docs/', '/empty.json'],
        '/docs': [],
      },
      {
        '/big.txt': { size: 2048 },
        '/empty.json': { size: null },
      },
    )
    expect(await walkFind(ROOT, deps, { minSize: 1024 })).toEqual(['/big.txt', '/docs'])
    expect(await walkFind(ROOT, deps, { maxSize: 100 })).toEqual(['/docs', '/empty.json'])
  })

  it('filters by mtime, parsing naive timestamps as UTC and excluding missing ones', async () => {
    const deps = makeDeps(
      {
        '/': ['/naive.txt', '/none.txt', '/zulu.txt'],
      },
      {
        '/naive.txt': { size: 1, modified: '2026-01-05T00:00:00' },
        '/none.txt': { size: 1, modified: null },
        '/zulu.txt': { size: 1, modified: '2026-01-05T00:00:00Z' },
      },
    )
    const mtimeMin = Date.parse('2026-01-04T23:30:00Z') / 1000
    const mtimeMax = Date.parse('2026-01-05T00:30:00Z') / 1000
    const out = await walkFind(ROOT, deps, { mtimeMin, mtimeMax })
    expect(out).toEqual(['/naive.txt', '/zulu.txt'])
  })

  it('keeps a child whose readdir raises ENOENT but stops descending', async () => {
    const deps = makeDeps({ '/': ['/ghost/'] })
    const out = await walkFind(ROOT, deps)
    expect(out).toEqual(['/ghost'])
  })

  it('propagates non-ENOENT readdir errors', async () => {
    const base = makeDeps({ '/': ['/bad/'] })
    const deps: WalkFindDeps = {
      ...base,
      readdir: (spec, index) =>
        spec.original === '/bad'
          ? Promise.reject(new Error('rate limited'))
          : base.readdir(spec, index),
    }
    await expect(walkFind(ROOT, deps)).rejects.toThrow('rate limited')
  })

  it('treats ENOENT stat fallbacks as files but propagates other stat errors', async () => {
    const base = makeDeps({ '/': ['/mystery'] })
    const enoentDeps: WalkFindDeps = {
      ...base,
      stat: (spec) => Promise.reject(enoent(spec.original)),
    }
    expect(await walkFind(ROOT, enoentDeps, { type: 'f' })).toEqual(['/mystery'])
    const failingDeps: WalkFindDeps = {
      ...base,
      stat: () => Promise.reject(new Error('rate limited')),
    }
    await expect(walkFind(ROOT, failingDeps, { type: 'f' })).rejects.toThrow('rate limited')
  })

  it('propagates non-ENOENT stat errors during size filtering', async () => {
    const base = makeDeps({ '/': ['/a.json'] }, {}, () => false)
    const deps: WalkFindDeps = { ...base, stat: () => Promise.reject(new Error('rate limited')) }
    await expect(walkFind(ROOT, deps, { minSize: 1 })).rejects.toThrow('rate limited')
  })

  it('drops entries whose stat raises ENOENT during size filtering', async () => {
    const deps = makeDeps({ '/': ['/a.json'] }, {}, () => false)
    expect(await walkFind(ROOT, deps, { minSize: 1 })).toEqual([])
  })

  it('strips the mount prefix from keys and matches pathPattern prefix-stripped', async () => {
    const deps = makeDeps({
      '/gd': ['/gd/docs/'],
      '/gd/docs': ['/gd/docs/inner.txt'],
    })
    const root = new PathSpec({ original: '/gd', directory: '/gd', prefix: '/gd' })
    expect(await walkFind(root, deps)).toEqual(['/docs', '/docs/inner.txt'])
    expect(await walkFind(root, deps, { pathPattern: '/docs/*' })).toEqual(['/docs/inner.txt'])
  })

  it('matches bracket classes in name patterns', async () => {
    const deps = makeDeps({ '/': ['/file1.txt', '/fileX.txt'] }, {}, () => false)
    const out = await walkFind(ROOT, deps, { name: 'file[0-9].txt' })
    expect(out).toEqual(['/file1.txt'])
  })

  it('applies orNames, nameExclude, and iname filters', async () => {
    const deps = makeDeps({ '/': ['/a.md', '/b.txt', '/c.csv'] }, {}, () => false)
    expect(await walkFind(ROOT, deps, { orNames: ['*.md', '*.csv'] })).toEqual(['/a.md', '/c.csv'])
    expect(await walkFind(ROOT, deps, { nameExclude: '*.txt' })).toEqual(['/a.md', '/c.csv'])
    expect(await walkFind(ROOT, deps, { iname: 'B.TXT' })).toEqual(['/b.txt'])
  })
})
