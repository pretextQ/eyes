import { createContext, useContext } from "react";
import type { Api } from "./api";
export const ConnectionContext = createContext<{
  api: Api | null;
  openConnection: () => void;
}>({ api: null, openConnection: () => {} });
export const useConnection = () => useContext(ConnectionContext);
