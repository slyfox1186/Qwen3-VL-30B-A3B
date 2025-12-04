import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Session } from '@/types/api';

interface SessionState {
  session: Session | null;
  sessions: Session[];
  isLoading: boolean;
  error: string | null;
  hasHydrated: boolean;
  isCreating: boolean;
  setSession: (session: Session) => void;
  addSession: (session: Session) => void;
  removeSession: (sessionId: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearSession: () => void;
  setHasHydrated: (state: boolean) => void;
  createSession: () => Promise<Session | null>;
  updateSessionTitle: (sessionId: string, title: string) => Promise<boolean>;
  generateLLMTitle: (sessionId: string) => Promise<string | null>;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      session: null,
      sessions: [],
      isLoading: false,
      error: null,
      hasHydrated: false,
      isCreating: false,
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
      createSession: async () => {
        const { isCreating, setSession } = get();
        if (isCreating) return null;

        set({ isCreating: true, error: null });
        try {
          const res = await fetch(`${API_BASE_URL}/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ metadata: { client: 'web' } }),
          });
          if (!res.ok) throw new Error('Failed to create session');
          const data = await res.json();
          setSession(data);
          return data;
        } catch (err) {
          console.error('Session creation failed:', err);
          set({ error: 'Failed to create session' });
          return null;
        } finally {
          set({ isCreating: false });
        }
      },

      updateSessionTitle: async (sessionId: string, title: string) => {
        try {
          const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ metadata: { title } }),
          });

          if (!res.ok) {
            console.error('Failed to update session title');
            return false;
          }

          // Update local state
          set((state) => ({
            sessions: state.sessions.map((s) =>
              s.id === sessionId ? { ...s, metadata: { ...s.metadata, title } } : s
            ),
            session:
              state.session?.id === sessionId
                ? { ...state.session, metadata: { ...state.session.metadata, title } }
                : state.session,
          }));

          return true;
        } catch (err) {
          console.error('Error updating session title:', err);
          return false;
        }
      },

      generateLLMTitle: async (sessionId: string) => {
        try {
          const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/generate-title`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          });

          if (!res.ok) {
            console.warn('LLM title generation failed:', res.status);
            return null;
          }

          const data = await res.json();
          const title = data.title;

          // Update local state with LLM-generated title
          set((state) => ({
            sessions: state.sessions.map((s) =>
              s.id === sessionId ? { ...s, metadata: { ...s.metadata, title } } : s
            ),
            session:
              state.session?.id === sessionId
                ? { ...state.session, metadata: { ...state.session.metadata, title } }
                : state.session,
          }));

          return title;
        } catch (err) {
          console.warn('Error generating LLM title:', err);
          return null;
        }
      },
    }),
    {
      name: 'session-storage',
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
