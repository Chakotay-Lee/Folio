import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="p-8 text-center">
      <h2 className="text-2xl font-semibold mb-2">404 — Page not found</h2>
      <Link to="/" className="text-sm text-muted-foreground underline">Go to Dashboard</Link>
    </div>
  )
}
