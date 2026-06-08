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

import type { LanceDBAccessor } from '../../../accessor/lancedb.ts'
import type { IndexCacheStore } from '../../../cache/index/store.ts'
import { resolveGlob } from '../../../core/lancedb/glob.ts'
import { read as lanceRead } from '../../../core/lancedb/read.ts'
import { readdir as lanceReaddir } from '../../../core/lancedb/readdir.ts'
import { IOResult, type ByteSource } from '../../../io/types.ts'
import { PathSpec, ResourceName } from '../../../types.ts'
import { command, type CommandFnResult, type CommandOpts } from '../../config.ts'
import { specOf } from '../../spec/builtins.ts'
import { compilePattern, grepLines } from '../grep_helper.ts'
import { readStdinAsync } from '../utils/stream.ts'

const ENC = new TextEncoder()
const DEC = new TextDecoder('utf-8', { fatal: false })

interface RgFlags {
  ignoreCase: boolean
  invert: boolean
  lineNumbers: boolean
  countOnly: boolean
  filesOnly: boolean
  wholeWord: boolean
  fixedString: boolean
  onlyMatching: boolean
  maxCount: number | null
  hidden: boolean
}

function parseRgFlags(flags: Record<string, string | boolean>): RgFlags {
  const toInt = (v: string | boolean | undefined): number | null =>
    typeof v === 'string' ? Number.parseInt(v, 10) : null
  return {
    ignoreCase: flags.i === true,
    invert: flags.v === true,
    lineNumbers: flags.n === true,
    countOnly: flags.c === true,
    filesOnly: flags.args_l === true,
    wholeWord: flags.w === true,
    fixedString: flags.F === true,
    onlyMatching: flags.o === true,
    maxCount: toInt(flags.m),
    hidden: flags.hidden === true,
  }
}

function isRowFile(name: string, accessor: LanceDBAccessor): boolean {
  if (name.endsWith('.md')) return true
  const { blobColumn, blobExt } = accessor.config
  return blobColumn !== null && name.endsWith(`.${blobExt}`)
}

async function collectFiles(
  accessor: LanceDBAccessor,
  path: PathSpec,
  index: IndexCacheStore | undefined,
): Promise<string[]> {
  let children: string[]
  try {
    children = await lanceReaddir(accessor, path, index)
  } catch {
    return []
  }
  const files: string[] = []
  for (const child of children) {
    const name = child.split('/').pop() ?? ''
    if (isRowFile(name, accessor)) {
      files.push(child)
    } else {
      const childSpec = new PathSpec({
        original: child,
        directory: child,
        resolved: false,
        prefix: path.prefix,
      })
      files.push(...(await collectFiles(accessor, childSpec, index)))
    }
  }
  return files
}

function splitLinesNoTrailing(text: string): string[] {
  const stripped = text.endsWith('\n') ? text.slice(0, -1) : text
  return stripped === '' ? [] : stripped.split('\n')
}

async function rgCommand(
  accessor: LanceDBAccessor,
  paths: PathSpec[],
  texts: string[],
  opts: CommandOpts,
): Promise<CommandFnResult> {
  const [exprText] = texts
  if (exprText === undefined) {
    return [
      null,
      new IOResult({ exitCode: 2, stderr: ENC.encode('rg: usage: rg [flags] pattern [path]\n') }),
    ]
  }
  const f = parseRgFlags(opts.flags)
  const pat = compilePattern(exprText, f.ignoreCase, f.fixedString, f.wholeWord)

  if (paths.length > 0) {
    const resolved = await resolveGlob(accessor, paths, opts.index ?? undefined)
    const filePrefix = resolved[0]?.prefix ?? ''
    const filePaths: string[] = []
    for (const p of resolved) {
      filePaths.push(...(await collectFiles(accessor, p, opts.index ?? undefined)))
    }
    const orderedFiles = Array.from(new Set(filePaths))
    const allResults: string[] = []
    let anyMatch = false
    for (const bp of orderedFiles) {
      let data: Uint8Array
      try {
        const bpSpec = new PathSpec({
          original: bp,
          directory: bp,
          resolved: true,
          prefix: filePrefix,
        })
        data = await lanceRead(accessor, bpSpec)
      } catch {
        continue
      }
      const text = DEC.decode(data)
      if (text === '') continue
      const matched = grepLines(bp, splitLinesNoTrailing(text), pat, f)
      if (matched.length === 0) continue
      anyMatch = true
      if (f.filesOnly) {
        allResults.push(bp)
        continue
      }
      if (f.countOnly) {
        allResults.push(`${bp}:${String(matched.length)}`)
        continue
      }
      for (const line of matched) allResults.push(`${bp}:${line}`)
    }
    if (!anyMatch) return [new Uint8Array(0), new IOResult({ exitCode: 1 })]
    const out: ByteSource = ENC.encode(allResults.join('\n'))
    return [out, new IOResult()]
  }

  const raw = await readStdinAsync(opts.stdin)
  if (raw === null) {
    return [
      null,
      new IOResult({ exitCode: 2, stderr: ENC.encode('rg: usage: rg [flags] pattern path\n') }),
    ]
  }
  const matched = grepLines('<stdin>', splitLinesNoTrailing(DEC.decode(raw)), pat, f)
  if (matched.length === 0) return [new Uint8Array(0), new IOResult({ exitCode: 1 })]
  if (f.countOnly) return [ENC.encode(String(matched.length)), new IOResult()]
  return [ENC.encode(matched.join('\n')), new IOResult()]
}

export const LANCEDB_RG = command({
  name: 'rg',
  resource: ResourceName.LANCEDB,
  spec: specOf('rg'),
  fn: rgCommand,
})
