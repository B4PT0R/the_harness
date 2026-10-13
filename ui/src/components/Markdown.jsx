import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { remarkLocalPaths } from "../local-paths";
import { ResourceLink } from "./ResourceLink";

export function Markdown({ children }) {
  return <div className="markdown"><ReactMarkdown
    remarkPlugins={[remarkGfm, remarkMath, remarkLocalPaths]}
    rehypePlugins={[[rehypeKatex, { strict: "ignore", trust: false }]]}
    components={{ a: ResourceLink }}
  >{children || ""}</ReactMarkdown></div>;
}
