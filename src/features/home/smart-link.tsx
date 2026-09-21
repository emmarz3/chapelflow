import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { isAnchorHref, isExternalHref, safeHref } from "../../lib/homepage-content";

/** Renders an editor-supplied href as the right kind of link, or plain text if it is unsafe. */
export function SmartLink({
  href,
  className,
  children,
  onClick,
  tabIndex,
}: {
  href: string;
  className?: string;
  children: ReactNode;
  onClick?: () => void;
  tabIndex?: number;
}) {
  const safe = safeHref(href);
  if (!safe) return <span className={className}>{children}</span>;
  if (isExternalHref(safe))
    return (
      <a className={className} href={safe} target="_blank" rel="noopener noreferrer" onClick={onClick} tabIndex={tabIndex}>
        {children}
      </a>
    );
  if (isAnchorHref(safe))
    return (
      <a className={className} href={safe} onClick={onClick} tabIndex={tabIndex}>
        {children}
      </a>
    );
  return (
    <Link className={className} to={safe} onClick={onClick} tabIndex={tabIndex}>
      {children}
    </Link>
  );
}
