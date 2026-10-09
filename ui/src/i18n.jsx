import React, { createContext, useContext, useEffect, useState } from "react";
import { localeKey, readLocale, resolveLocale, translate } from "./locales";
const Context = createContext(null);
export function LocaleProvider({ children }) {
  const [locale, update] = useState(readLocale);
  useEffect(() => { document.documentElement.lang = locale; }, [locale]);
  function setLocale(value) {
    const next = resolveLocale(value);
    try { localStorage.setItem(localeKey, next); } catch { /* Session-only when storage is disabled. */ }
    update(next);
  }
  return <Context.Provider value={{ locale, setLocale, t: (key, values) => translate(key, values, locale) }}>{children}</Context.Provider>;
}
export const useLocale = () => useContext(Context);
