import React, { createContext, useContext, useState } from "react";
import { api } from "../api";
import { useLocale } from "../i18n";
import { localPath } from "../local-paths";

export const ResourceRequest = createContext(api);

export function ResourceLink({ node, href, children, ...props }) {
  const request = useContext(ResourceRequest);
  const { t } = useLocale();
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState("");
  const path = localPath(href);
  if (!path) return <a {...props} href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
  async function open(event) {
    event.preventDefault();
    if (opening) return;
    setOpening(true);
    setError("");
    try { await request("local-files/open", { method: "POST", body: { path } }); }
    catch (failure) { setError(failure.message); }
    finally { setOpening(false); }
  }
  return <>
    <a {...props} href={href} className="resource-link" title={t("openLocalResource", { path })}
      aria-busy={opening} aria-disabled={opening || undefined} onClick={open}>{children}</a>
    {error && <span className="resource-error error" role="alert">{error}</span>}
  </>;
}
