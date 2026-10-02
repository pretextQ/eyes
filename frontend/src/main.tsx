import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { ConsoleBoundary } from "./components/ConsoleBoundary";
import "@fontsource-variable/dm-sans";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./styles.css";
const client = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 10000, refetchOnWindowFocus: false },
  },
});
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <ConsoleBoundary>
          <App />
        </ConsoleBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
