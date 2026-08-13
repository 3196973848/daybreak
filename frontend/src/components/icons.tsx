import type { ReactNode } from 'react'

function Svg({ children, size = 16 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export function IconArrowLeft({ size }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M19 12H5" />
      <path d="M12 19l-7-7 7-7" />
    </Svg>
  )
}

export function IconArrowRight({ size }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M5 12h14" />
      <path d="M12 5l7 7-7 7" />
    </Svg>
  )
}

export function IconTrash({ size }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M3 6h18" />
      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" />
      <path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </Svg>
  )
}

export function IconCheck({ size }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M20 6L9 17l-5-5" />
    </Svg>
  )
}

export function IconX({ size }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M18 6L6 18" />
      <path d="M6 6l12 12" />
    </Svg>
  )
}

export function IconCalendar({ size }: { size?: number }) {
  return (
    <Svg size={size}>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4" />
      <path d="M8 2v4" />
      <path d="M3 10h18" />
    </Svg>
  )
}

export function IconClipboard({ size }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" />
      <path d="M9 12h6" />
      <path d="M9 16h6" />
    </Svg>
  )
}

export function IconChevronDown({ size }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M6 9l6 6 6-6" />
    </Svg>
  )
}

export function IconTarget({ size }: { size?: number }) {
  return (
    <Svg size={size}>
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </Svg>
  )
}
