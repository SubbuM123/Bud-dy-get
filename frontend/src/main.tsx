/**
 * Application bootstrap: mounts the React tree onto #root (see index.html) and wraps it
 * with the two providers every page depends on - React Query for server-state caching and
 * React Router for client-side navigation. This is the only file that touches ReactDOM
 * directly; everything else composes down from <App />.
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

// Shared React Query client: cache API responses for 5 minutes and retry a failed request once.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 1,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
