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

export const LANCEDB_PROMPT = `This mount is a LanceDB table exposed as a filesystem.

Directories are the configured group-by columns; descending narrows a filter.
Each matching row is a <id>.md card plus a <id>.<ext> blob file. Semantic search
is a virtual folder: read a query as a path segment, e.g.
ls "_search/red running shoes" then cat "_search/red running shoes/<id>.md".
Use ls/cd/cat/tree/find/wc as usual; quote queries that contain spaces.`
