// Line icons and provider marks for the accounts pages. The line icons are drawn here (16px grid, 1.5px strokes), like
// the home page's. The Google and GitHub marks are the artwork of @lobehub/icons 5.13.0 (MIT), already a dependency
// of this site: es/Google/components/Color.js and es/Github/components/Mono.js, path data unchanged.

type IconProps = { size?: number; className?: string }

const line = (size: number) => ({ width: size, height: size, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, focusable: false })

export function KeyIcon({ size = 18, className }: IconProps) {
  return <svg {...line(size)} className={className}><circle cx="5.5" cy="10.5" r="3" /><path d="M7.6 8.4 13.5 2.5M11.5 4.5l1.5 1.5M10 6l1.2 1.2" /></svg>
}

export function EyeIcon({ size = 16, className }: IconProps) {
  return <svg {...line(size)} className={className}><path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8z" /><circle cx="8" cy="8" r="2" /></svg>
}

export function EyeOffIcon({ size = 16, className }: IconProps) {
  return <svg {...line(size)} className={className}><path d="M2.5 2.5l11 11M6.6 4a6.6 6.6 0 0 1 1.4-.5c4.1 0 6.5 4.5 6.5 4.5a11 11 0 0 1-1.7 2.3M10.4 10.6A2 2 0 0 1 6.6 8.4M4.3 5.3A11.4 11.4 0 0 0 1.5 8s2.4 4.5 6.5 4.5a6 6 0 0 0 2.7-.6" /></svg>
}

export function MailIcon({ size = 18, className }: IconProps) {
  return <svg {...line(size)} className={className}><rect x="1.75" y="3.25" width="12.5" height="9.5" rx="2" /><path d="m2.5 4.5 5.5 4 5.5-4" /></svg>
}

export function AlertIcon({ size = 16, className }: IconProps) {
  return <svg {...line(size)} className={className}><circle cx="8" cy="8" r="6.25" /><path d="M8 4.75v3.75M8 11h.01" /></svg>
}

export function CheckCircleIcon({ size = 16, className }: IconProps) {
  return <svg {...line(size)} className={className}><circle cx="8" cy="8" r="6.25" /><path d="m5.25 8.25 1.9 1.9 3.6-4.1" /></svg>
}

export function InfoIcon({ size = 16, className }: IconProps) {
  return <svg {...line(size)} className={className}><circle cx="8" cy="8" r="6.25" /><path d="M8 7.25V11M8 5h.01" /></svg>
}

export function DeviceIcon({ size = 18, className }: IconProps) {
  return <svg {...line(size)} className={className}><rect x="1.75" y="2.75" width="12.5" height="8.5" rx="1.5" /><path d="M5.5 13.25h5M8 11.25v2" /></svg>
}

export function GoogleMark({ size = 18, className }: IconProps) {
  return <svg className={className} viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" focusable="false">
    <path fill="#4285F4" d="M23 12.245c0-.905-.075-1.565-.236-2.25h-10.54v4.083h6.186c-.124 1.014-.797 2.542-2.294 3.569l-.021.136 3.332 2.53.23.022C21.779 18.417 23 15.593 23 12.245z" />
    <path fill="#34A853" d="M12.225 23c3.03 0 5.574-.978 7.433-2.665l-3.542-2.688c-.948.648-2.22 1.1-3.891 1.1a6.745 6.745 0 01-6.386-4.572l-.132.011-3.465 2.628-.045.124C4.043 20.531 7.835 23 12.225 23z" />
    <path fill="#FBBC05" d="M5.84 14.175A6.65 6.65 0 015.463 12c0-.758.138-1.491.361-2.175l-.006-.147-3.508-2.67-.115.054A10.831 10.831 0 001 12c0 1.772.436 3.447 1.197 4.938l3.642-2.763z" />
    <path fill="#EB4335" d="M12.225 5.253c2.108 0 3.529.892 4.34 1.638l3.167-3.031C17.787 2.088 15.255 1 12.225 1 7.834 1 4.043 3.469 2.197 7.062l3.63 2.763a6.77 6.77 0 016.398-4.572z" />
  </svg>
}

export function GitHubMark({ size = 18, className }: IconProps) {
  return <svg className={className} viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" focusable="false" fill="currentColor" fillRule="evenodd">
    <path d="M12 0c6.63 0 12 5.276 12 11.79-.001 5.067-3.29 9.567-8.175 11.187-.6.118-.825-.25-.825-.56 0-.398.015-1.665.015-3.242 0-1.105-.375-1.813-.81-2.181 2.67-.295 5.475-1.297 5.475-5.822 0-1.297-.465-2.344-1.23-3.169.12-.295.54-1.503-.12-3.125 0 0-1.005-.324-3.3 1.209a11.32 11.32 0 00-3-.398c-1.02 0-2.04.133-3 .398-2.295-1.518-3.3-1.209-3.3-1.209-.66 1.622-.24 2.83-.12 3.125-.765.825-1.23 1.887-1.23 3.169 0 4.51 2.79 5.527 5.46 5.822-.345.294-.66.81-.765 1.577-.69.31-2.415.81-3.495-.973-.225-.354-.9-1.223-1.845-1.209-1.005.015-.405.56.015.781.51.28 1.095 1.327 1.23 1.666.24.663 1.02 1.93 4.035 1.385 0 .988.015 1.916.015 2.196 0 .31-.225.664-.825.56C3.303 21.374-.003 16.867 0 11.791 0 5.276 5.37 0 12 0z" />
  </svg>
}
