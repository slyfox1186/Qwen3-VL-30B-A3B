import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Session } from '@/types/api';

interface SessionState {
  session: Session | null;
  sessions: Session[];
  isLoading: boolean;
  error: string | null;
  hasHydrated: boolean;
  setSession: (session: Session) => void;
  addSession: (session: Session) => void;
  removeSession: (sessionId: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearSession: () => void;
  setHasHydrated: (state: boolean) => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      session: null,
      sessions: [],
      isLoading: false,
      error: null,
      hasHydrated: false,
      setSession: (session) => {
        const { sessions } = get();
        const exists = sessions.find((s) => s.id === session.id);
        set({
          session,
          sessions: exists
            ? sessions.map((s) => (s.id === session.id ? session : s))
            : [session, ...sessions]
        });
      },
      addSession: (session) => set((state) => ({
        sessions: [session, ...state.sessions.filter(s => s.id !== session.id)]
      })),
      removeSession: (sessionId) => set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== sessionId),
        session: state.session?.id === sessionId ? null : state.session
      })),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      clearSession: () => set({ session: null, error: null }),
      setHasHydrated: (state) => set({ hasHydrated: state }),
    }),
    {
      name: 'session-storage',
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
