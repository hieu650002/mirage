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
import { resolveGlob } from '../../../core/lancedb/glob.ts'
import { read as lanceRead } from '../../../core/lancedb/read.ts'
import { IOResult, type ByteSource } from '../../../io/types.ts'
import { ResourceName, type PathSpec } from '../../../types.ts'
import { command, type CommandFnResult, type CommandOpts } from '../../config.ts'
import { specOf } from '../../spec/builtins.ts'
import { numberLines } from '../cat_helper.ts'
import { resolveSource } from '../utils/stream.ts'

const ENC = new TextEncoder()

async function* once(data: Uint8Array): AsyncIterable<Uint8Array> {
  await Promise.resolve()
  yield data
}

function concat(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0)
  const merged = new Uint8Array(total)
  let offset = 0
  for (const part of parts) {
    merged.set(part, offset)
    offset += part.length
  }
  return merged
}

async function catCommand(
  accessor: LanceDBAccessor,
  paths: PathSpec[],
  _texts: string[],
  opts: CommandOpts,
): Promise<CommandFnResult> {
  const nFlag = opts.flags.n === true
  if (paths.length > 0) {
    const resolved = await resolveGlob(accessor, paths, opts.index ?? undefined)
    const reads: Record<string, Uint8Array> = {}
    const parts: Uint8Array[] = []
    for (const p of resolved) {
      const data = await lanceRead(accessor, p, opts.index ?? undefined)
      reads[p.stripPrefix] = data
      parts.push(data)
    }
    const merged = concat(parts)
    const out: ByteSource = nFlag ? numberLines(once(merged)) : merged
    return [out, new IOResult({ reads, cache: Object.keys(reads) })]
  }
  try {
    const source = resolveSource(opts.stdin, 'cat: missing operand')
    return [nFlag ? numberLines(source) : source, new IOResult()]
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    return [null, new IOResult({ exitCode: 1, stderr: ENC.encode(`${msg}\n`) })]
  }
}

export const LANCEDB_CAT = command({
  name: 'cat',
  resource: ResourceName.LANCEDB,
  spec: specOf('cat'),
  fn: catCommand,
})
