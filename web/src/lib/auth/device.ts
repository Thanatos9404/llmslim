/** A short, human label for a session's user agent, such as "Chrome on Windows". */
export function describeDevice(userAgent: string | null | undefined): string {
  if (!userAgent) return "Unknown device"
  const ua = userAgent
  const browser = /Edg\//.test(ua)
    ? "Edge"
    : /OPR\/|Opera/.test(ua)
      ? "Opera"
      : /Firefox\//.test(ua)
        ? "Firefox"
        : /Chrome\/|CriOS\//.test(ua)
          ? "Chrome"
          : /Safari\//.test(ua) && /Version\//.test(ua)
            ? "Safari"
            : /HeadlessChrome/.test(ua)
              ? "Chrome"
              : null
  const os = /iPhone|iPad|iPod/.test(ua)
    ? "iOS"
    : /Android/.test(ua)
      ? "Android"
      : /Windows/.test(ua)
        ? "Windows"
        : /Mac OS X|Macintosh/.test(ua)
          ? "macOS"
          : /CrOS/.test(ua)
            ? "ChromeOS"
            : /Linux/.test(ua)
              ? "Linux"
              : null
  if (browser && os) return `${browser} on ${os}`
  return browser ?? os ?? "Unknown device"
}
