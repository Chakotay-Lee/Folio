export interface GenreNode {
  label: string
  fullPath: string
  count: number
  children: GenreNode[]
}

export function buildGenreTree(books: { genre_path: string | null; count?: number }[]): GenreNode[] {
  const root: Map<string, GenreNode> = new Map()

  const getOrCreate = (map: Map<string, GenreNode>, label: string, fullPath: string): GenreNode => {
    if (!map.has(label)) {
      map.set(label, { label, fullPath, count: 0, children: [] })
    }
    return map.get(label)!
  }

  for (const book of books) {
    if (!book.genre_path?.trim()) continue
    const parts = book.genre_path.split(' > ').map(p => p.trim()).filter(Boolean)
    let currentMap = root
    let pathSoFar = ''
    for (let i = 0; i < parts.length; i++) {
      pathSoFar = i === 0 ? parts[0] : `${pathSoFar} > ${parts[i]}`
      const node = getOrCreate(currentMap, parts[i], pathSoFar)
      node.count += (book.count ?? 1)
      if (i < parts.length - 1) {
        // Ensure children map exists by converting children array to map temporarily
        if (!node._childMap) node._childMap = new Map()
        currentMap = node._childMap
        // Sync array from map
        node.children = Array.from(node._childMap.values())
      }
    }
  }

  // Sync all child maps to arrays and clean up
  function finalize(nodes: Map<string, GenreNode>): GenreNode[] {
    return Array.from(nodes.values()).map(node => {
      if (node._childMap) {
        node.children = finalize(node._childMap)
        delete node._childMap
      }
      return node
    }).sort((a, b) => b.count - a.count)
  }

  return finalize(root)
}

// Returns true if book's genre_path is at or below the selected node's fullPath
export function matchesGenreFilter(genrePath: string | null, selectedPath: string): boolean {
  if (!selectedPath) return true
  if (!genrePath) return false
  return genrePath === selectedPath || genrePath.startsWith(selectedPath + ' > ')
}

// Private augment type for build process
declare module './genreTree' {
  interface GenreNode {
    _childMap?: Map<string, GenreNode>
  }
}
