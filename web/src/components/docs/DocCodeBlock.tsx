"use client";

import React, { useState } from "react";
import { Check, Copy, Terminal } from "lucide-react";

export function DocCodeBlock({
  language = "bash",
  filename,
  code,
}: {
  language?: string;
  filename?: string;
  code: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="reading-code select-text">
      {/* Code Header Bar */}
      <div className="reading-code__head">
        <div className="flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5" />
          {filename && <span>{filename}</span>}
          {!filename && <span>{language}</span>}
        </div>
        <button
          onClick={handleCopy}
          aria-label="Copy code block snippet"
          title="Copy code to clipboard"
          className="reading-code__copy"
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Code Area */}
      <div className="reading-code__body">
        <pre>
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
}
