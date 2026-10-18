import React, { Component, useEffect, useRef, useState } from "react";
import { useLocale } from "../i18n";
import { Icon, IconButton } from "./Icons";

// Explicit presentation is data, never an instruction to execute supplied HTML.
export function artifactSource(value) {
  if (typeof value !== "string") return null;
  if (/^\/(?!\/)/.test(value) && !value.includes("\\")) return value;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function Description({ payload }) {
  return payload.description && <p className="artifact-description">{String(payload.description)}</p>;
}

function ImageDownload({ src, name }) {
  const { t } = useLocale();
  return <a className="artifact-image-download" href={src} download={name || true}
      target="_blank" rel="noopener noreferrer">
    <Icon name="download" />{t("artifactImageDownload")}
  </a>;
}

function ImageViewer({ src, payload, alt, dismiss }) {
  const { t } = useLocale();
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    const trigger = document.activeElement;
    element.showModal();
    element.querySelector("button").focus();
    return () => {
      element.close();
      trigger?.focus({ preventScroll: true });
    };
  }, []);
  return <dialog ref={dialog} className="artifact-image-viewer" aria-label={alt}
      onCancel={event => { event.preventDefault(); dismiss(); }}
      onClick={event => { if (event.target === event.currentTarget) dismiss(); }}>
    <header className="artifact-image-toolbar">
      <span className="artifact-image-title">{payload.title || payload.name || t("artifactImage")}</span>
      <ImageDownload src={src} name={payload.name} />
      <IconButton icon="close" label={t("close")} onClick={dismiss} />
    </header>
    <div className="artifact-image-stage" onClick={dismiss}>
      <img src={src} alt={alt} onClick={event => event.stopPropagation()} />
    </div>
  </dialog>;
}

function ImageArtifact({ payload }) {
  const { t } = useLocale();
  const [failedSource, setFailedSource] = useState(null);
  const [expandedSource, setExpandedSource] = useState(null);
  const src = artifactSource(payload.src);
  const alt = String(payload.alt || payload.title || payload.name || t("artifactImage"));
  if (!src || failedSource === src) return <p role="status">{t("artifactUnavailable")}</p>;
  return <>
    <button type="button" className="artifact-image-preview" aria-label={t("artifactImageExpand")}
        onClick={() => setExpandedSource(src)}>
      <img src={src} alt={alt} loading="lazy" onError={() => setFailedSource(src)} />
    </button>
    <div className="artifact-image-actions">
      <IconButton icon="expand" label={t("artifactImageExpand")} onClick={() => setExpandedSource(src)} />
      <ImageDownload src={src} name={payload.name} />
    </div>
    {expandedSource === src && <ImageViewer key={src} src={src} payload={payload} alt={alt}
      dismiss={() => setExpandedSource(null)} />}
  </>;
}

function FileArtifact({ payload }) {
  const { t } = useLocale();
  const src = artifactSource(payload.src);
  return <>
    {src ? <a className="artifact-download" href={src} download={payload.name || true}
        target="_blank" rel="noopener noreferrer">{t("artifactDownload", { name: payload.name || payload.title || t("artifactFile") })}</a>
      : <p role="status">{t("artifactUnavailable")}</p>}
    <Description payload={payload} />
  </>;
}

function Fallback({ kind, payload }) {
  const { t } = useLocale();
  return <details className="artifact-fallback"><summary>{t("artifactDetails", { kind })}</summary>
    <pre>{JSON.stringify(payload, null, 2)}</pre>
  </details>;
}

class RenderBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidUpdate(previous) {
    if (this.state.failed && previous.payload !== this.props.payload) this.setState({ failed: false });
  }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

const builtins = { image: ImageArtifact, file: FileArtifact };

export function Artifact({ kind, payload = {}, renderers = {}, temporary = false }) {
  const { t } = useLocale();
  const Renderer = Object.hasOwn(renderers, kind) ? renderers[kind]
    : Object.hasOwn(builtins, kind) ? builtins[kind] : null;
  const fallback = <Fallback kind={kind} payload={payload} />;
  return <article className={`message artifact artifact-${kind}`} aria-label={t("artifact")}>
    {temporary && <small className="message-live">{t("artifactTemporary")}</small>}
    {payload.title && <h3>{String(payload.title)}</h3>}
    <RenderBoundary fallback={fallback} payload={payload}>
      {Renderer ? <Renderer kind={kind} payload={payload} /> : fallback}
    </RenderBoundary>
  </article>;
}
