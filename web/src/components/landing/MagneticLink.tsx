"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

type MagneticLinkProps = {
  href: string;
  className?: string;
  children: ReactNode;
  ariaLabel?: string;
};

export function MagneticLink({ href, className = "", children, ariaLabel }: MagneticLinkProps) {
  const move = (event: React.MouseEvent<HTMLAnchorElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    const dx = (event.clientX - (rect.left + rect.width / 2)) / 16;
    const dy = (event.clientY - (rect.top + rect.height / 2)) / 16;
    event.currentTarget.style.setProperty("--pointer-x", `${x}%`);
    event.currentTarget.style.setProperty("--pointer-y", `${y}%`);
    event.currentTarget.style.setProperty("--magnet-x", `${Math.max(-5, Math.min(5, dx))}px`);
    event.currentTarget.style.setProperty("--magnet-y", `${Math.max(-4, Math.min(4, dy))}px`);
  };

  const reset = (event: React.MouseEvent<HTMLAnchorElement> | React.FocusEvent<HTMLAnchorElement>) => {
    event.currentTarget.style.setProperty("--magnet-x", "0px");
    event.currentTarget.style.setProperty("--magnet-y", "0px");
  };

  return <Link href={href} aria-label={ariaLabel} className={`button magnetic-link ${className}`} onMouseMove={move} onMouseLeave={reset} onBlur={reset} style={{ "--pointer-x": "50%", "--pointer-y": "50%", "--magnet-x": "0px", "--magnet-y": "0px" } as CSSProperties}>
    <span className="magnetic-link__content">{children}</span>
  </Link>;
}
