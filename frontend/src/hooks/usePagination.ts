import { useState, useMemo } from 'react'

export function usePagination<T>(items: T[], pageSize = 24) {
  const [page, setPage] = useState(1)

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize))
  const safePage = Math.min(page, totalPages)

  const paginatedItems = useMemo(
    () => items.slice((safePage - 1) * pageSize, safePage * pageSize),
    [items, safePage, pageSize]
  )

  const reset = () => setPage(1)

  return { page: safePage, totalPages, paginatedItems, setPage, reset, total: items.length }
}
