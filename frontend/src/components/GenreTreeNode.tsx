import { useState } from 'react'
import { ChevronRight, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { GenreNode } from '@/lib/genreTree'

interface Props {
  node: GenreNode
  selected: string | null
  onSelect: (fullPath: string) => void
  onExpand?: (fullPath: string) => void
  depth?: number
}

export function GenreTreeNode({ node, selected, onSelect, onExpand, depth = 0 }: Props) {
  const isSelected = selected === node.fullPath
  const hasChildren = node.children.length > 0
  const isAncestorOfSelected = selected?.startsWith(node.fullPath + ' > ')
  const [expanded, setExpanded] = useState(isAncestorOfSelected || false)

  const toggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    setExpanded(v => !v)
  }

  return (
    <div>
      <div className="group relative flex items-center">
        <button
          onClick={() => onSelect(node.fullPath)}
          className={cn(
            'flex-1 text-left flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm transition-colors',
            depth > 0 && 'ml-3',
            isSelected
              ? 'bg-amber-400/10 text-amber-700 font-medium'
              : 'text-slate-500 hover:bg-slate-100'
          )}>
          {hasChildren ? (
            <span onClick={toggle}
              className="shrink-0 w-3.5 h-3.5 flex items-center justify-center opacity-50 hover:opacity-100">
              <ChevronRight className={cn('w-3 h-3 transition-transform', expanded && 'rotate-90')} />
            </span>
          ) : (
            <span className="shrink-0 w-3.5" />
          )}
          <span className="flex-1 truncate">{node.label}</span>
          <span className="text-xs opacity-50 shrink-0 mr-5">·{node.count}</span>
        </button>

        {onExpand && node.count > 1 && (
          <button
            onClick={e => { e.stopPropagation(); onExpand(node.fullPath) }}
            title="展開子分類"
            className={cn(
              'absolute right-1 opacity-0 group-hover:opacity-100 p-0.5 rounded transition-opacity',
              'text-slate-400 hover:text-amber-600 hover:bg-amber-50'
            )}>
            <Layers className="w-3 h-3" />
          </button>
        )}
      </div>

      {hasChildren && expanded && (
        <div>
          {node.children.map(child => (
            <GenreTreeNode key={child.fullPath} node={child} selected={selected}
              onSelect={onSelect} onExpand={onExpand} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}
