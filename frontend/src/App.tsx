import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { LangProvider } from '@/lib/LangContext'
import { AppLayout } from '@/layouts/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { DiscoverPage } from '@/pages/DiscoverPage'
import { FoldersPage } from '@/pages/FoldersPage'
import { NotesPage } from '@/pages/NotesPage'
import { ProfilePage } from '@/pages/ProfilePage'
import { SettingsPage } from '@/pages/SettingsPage'
import { DevPage } from '@/pages/DevPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { EpubReaderPage } from '@/pages/EpubReaderPage'

export default function App() {
  return (
    <LangProvider>
      <BrowserRouter>
        <Routes>
          <Route path="reader/:uuid" element={<EpubReaderPage />} />
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="discover" element={<DiscoverPage />} />
            <Route path="folders" element={<FoldersPage />} />
            <Route path="notes" element={<NotesPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="dev" element={<DevPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </LangProvider>
  )
}
