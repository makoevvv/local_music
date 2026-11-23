import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { PlayerBar } from '@/components/PlayerBar';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { CatalogPage } from '@/pages/CatalogPage';
import { LoginPage } from '@/pages/LoginPage';
import { PlaylistDetailPage } from '@/pages/PlaylistDetailPage';
import { PlaylistsPage } from '@/pages/PlaylistsPage';
import { SearchPage } from '@/pages/SearchPage';
import { TrackPage } from '@/pages/TrackPage';
import { useAuthStore } from '@/store/authStore';
import { useTrackEvents } from '@/hooks/useTrackEvents';

export default function App() {
  const initialize = useAuthStore((state) => state.initialize);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useTrackEvents(isAuthenticated);

  return (
    <>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/catalog" replace />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/tracks/:id" element={<TrackPage />} />
          <Route path="/playlists" element={<PlaylistsPage />} />
          <Route path="/playlists/:id" element={<PlaylistDetailPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/catalog" replace />} />
      </Routes>
      <PlayerBar />
    </>
  );
}
