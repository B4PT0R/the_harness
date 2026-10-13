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
  const web = /^https?:\/\//.test(href || "");
  if (!path && !web) return <a {...props} href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
  async function open(event) {
    event.preventDefault();
    if (opening) return;
    setOpening(true);
    setError("");
    try {
      await request(path ? "local-files/open" : "browser/open-external", {
        method: "POST", body: path ? { path } : { url: href },
      });
    }
    catch (failure) { setError(failure.message); }
    finally { setOpening(false); }
  }
  return <>
    <a {...props} href={href} className="resource-link" title={path ? t("openLocalResource", { path }) : undefined}
      aria-busy={opening} aria-disabled={opening || undefined} onClick={open}
      onAuxClick={(event) => { if (event.button === 1) open(event); }}>{children}</a>
    {error && <span className="resource-error error" role="alert">{error}</span>}
  </>;
}
