/**
 * The icon set from the design reference, traced path-for-path.
 *
 * The mockups draw every icon inline at 24x24 with a 1.5–1.9 stroke and round
 * caps; keeping the exact paths is what makes the implementation read as the
 * same product rather than a lookalike built from a generic icon package.
 */

type P = {
  size?: number;
  className?: string;
  strokeWidth?: number;
  style?: React.CSSProperties;
};

const stroke = (
  { size = 17, className, strokeWidth = 1.6, style }: P,
  children: React.ReactNode,
) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    style={style}
    aria-hidden="true"
  >
    {children}
  </svg>
);

export const IconHome = (p: P) =>
  stroke(
    p,
    <>
      <path d="m3.5 10.5 8.5-7 8.5 7" />
      <path d="M5.5 9.5V20h13V9.5" />
    </>,
  );

export const IconTarget = (p: P) =>
  stroke(
    p,
    <>
      <circle cx="12" cy="12" r="7.5" />
      <circle cx="12" cy="12" r="2.6" />
      <path d="M12 2.2v2.3M12 19.5v2.3M2.2 12h2.3M19.5 12h2.3" />
    </>,
  );

export const IconCalendar = (p: P) =>
  stroke(
    p,
    <>
      <rect x="3.5" y="5" width="17" height="15" rx="2" />
      <path d="M3.5 10h17M8 3.5v3M16 3.5v3" />
    </>,
  );

export const IconBook = (p: P) =>
  stroke(
    p,
    <>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H9v16H5.5A1.5 1.5 0 0 1 4 18.5z" />
      <path d="M12 4h3.5A1.5 1.5 0 0 1 17 5.5v13a1.5 1.5 0 0 1-1.5 1.5H12z" />
      <path d="M19.5 6.5 21 18" />
    </>,
  );

export const IconUser = (p: P) =>
  stroke(
    p,
    <>
      <circle cx="12" cy="8.5" r="3.8" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </>,
  );

export const IconUpload = (p: P) =>
  stroke(
    p,
    <>
      <path d="M12 15.5V3.5m0 0L8 7.5m4-4 4 4" />
      <path d="M3.5 15v3.5a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2V15" />
    </>,
  );

export const IconDownload = (p: P) =>
  stroke(
    p,
    <>
      <path d="M12 3.5v11m0 0 4-4m-4 4-4-4" />
      <path d="M4 17v2a1.8 1.8 0 0 0 1.8 1.8h12.4A1.8 1.8 0 0 0 20 19v-2" />
    </>,
  );

export const IconFile = (p: P) =>
  stroke(
    p,
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
    </>,
  );

export const IconMail = (p: P) =>
  stroke(
    p,
    <>
      <rect x="3.5" y="5.5" width="17" height="13" rx="2" />
      <path d="m4 7.5 8 5.6 8-5.6" />
    </>,
  );

export const IconClock = (p: P) =>
  stroke(
    p,
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7v5.2l3.2 1.9" />
    </>,
  );

export const IconChat = (p: P) =>
  stroke(
    p,
    <path d="M4.5 6.5A2 2 0 0 1 6.5 4.5h11a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H10l-4 3.5V15.5H6.5a2 2 0 0 1-2-2z" />,
  );

export const IconStar = (p: P) =>
  stroke(
    p,
    <path d="M12 3.5 14.6 9l6 .9-4.3 4.2 1 6-5.3-2.8L6.7 20l1-6L3.4 9.9 9.4 9z" />,
  );

export const IconCheck = (p: P) => stroke({ strokeWidth: 2.4, ...p }, <path d="m5 12.5 4.5 4.5L19 7" />);

export const IconPlus = (p: P) =>
  stroke({ strokeWidth: 1.9, ...p }, <path d="M12 5.5v13M5.5 12h13" />);

export const IconClose = (p: P) =>
  stroke({ strokeWidth: 2, ...p }, <path d="M6 6l12 12M18 6 6 18" />);

export const IconArrowRight = (p: P) =>
  stroke({ strokeWidth: 1.8, ...p }, <path d="M5 12h13M13 6l6 6-6 6" />);

export const IconArrowLeft = (p: P) =>
  stroke({ strokeWidth: 1.8, ...p }, <path d="M19 12H5M11 6l-6 6 6 6" />);

export const IconChevronDown = (p: P) =>
  stroke({ strokeWidth: 2, ...p }, <path d="m6 9 6 6 6-6" />);

export const IconChevronRight = (p: P) =>
  stroke({ strokeWidth: 1.8, ...p }, <path d="m9 6 6 6-6 6" />);

export const IconInfo = (p: P) =>
  stroke(
    { strokeWidth: 2, ...p },
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 7.6v.1" />
    </>,
  );

export const IconWarning = (p: P) =>
  stroke(
    { strokeWidth: 1.8, ...p },
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 8v4.6M12 16v.1" />
    </>,
  );

export const IconAlert = (p: P) =>
  stroke(
    { strokeWidth: 1.8, ...p },
    <>
      <path d="M12 8.5v4.6M12 16.6v.1" />
      <path d="M10.3 4.2 2.9 17a2 2 0 0 0 1.7 3h14.8a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z" />
    </>,
  );

/** The ATS / machine-readable mark: brackets around a line. */
export const IconBrackets = (p: P) =>
  stroke(
    { strokeWidth: 1.7, ...p },
    <>
      <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" />
      <path d="M4.5 12h15" />
    </>,
  );

export const IconShield = (p: P) =>
  stroke(
    { strokeWidth: 1.5, ...p },
    <>
      <path d="M12 3.2 19 6v6c0 4.4-3 8.2-7 9-4-.8-7-4.6-7-9V6l7-2.8z" />
      <path d="m9 12 2.2 2.2L15.5 10" />
    </>,
  );

export const IconLock = (p: P) =>
  stroke(
    { strokeWidth: 1.5, ...p },
    <>
      <rect x="4" y="10" width="16" height="10.5" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>,
  );

export const IconPencil = (p: P) =>
  stroke(
    { strokeWidth: 1.6, ...p },
    <>
      <path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3z" />
      <path d="m13.5 6.5 4 4" />
    </>,
  );

export const IconSend = (p: P) =>
  stroke(
    { strokeWidth: 1.6, ...p },
    <>
      <path d="M21 3 10.6 13.4" />
      <path d="M21 3 14.2 21l-3.6-7.6L3 9.8 21 3z" />
    </>,
  );

export const IconMenu = (p: P) =>
  stroke({ strokeWidth: 1.7, ...p }, <path d="M4 7h16M4 12h16M4 17h16" />);

export const IconSliders = (p: P) =>
  stroke(
    { strokeWidth: 1.6, ...p },
    <>
      <path d="M4 7h9M18.5 7h1.5M4 17h4.5M14 17h6" />
      <circle cx="15.5" cy="7" r="2.4" />
      <circle cx="11" cy="17" r="2.4" />
    </>,
  );

/** Filled marks — the sparkle is the product's "tailor" gesture. */
export const IconSparkle = ({ size = 18, className, style }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} style={style} aria-hidden="true">
    <path d="M12 3.2 13.7 9 19.5 10.7 13.7 12.4 12 18.2 10.3 12.4 4.5 10.7 10.3 9 12 3.2z" />
    <path d="M18.8 15.4l.6 2 2 .6-2 .6-.6 2-.6-2-2-.6 2-.6.6-2z" />
  </svg>
);

export const IconSpark = ({ size = 13, className, style }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} style={style} aria-hidden="true">
    <path d="M12 3.2 13.7 9 19.5 10.7 13.7 12.4 12 18.2 10.3 12.4 4.5 10.7 10.3 9 12 3.2z" />
  </svg>
);

/** The indeterminate ring used by the tailoring screen. */
export const Spinner = ({ size = 32 }: { size?: number }) => (
  <svg className="spin" width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <circle cx="16" cy="16" r="13" stroke="#e3e8ed" strokeWidth="3" />
    <path d="M16 3a13 13 0 0 1 13 13" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
  </svg>
);

export const SpinnerSmall = ({ size = 14 }: { size?: number }) => (
  <svg className="spin" width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <circle cx="8" cy="8" r="5.6" stroke="rgba(255,255,255,.34)" strokeWidth="2.4" />
    <path d="M8 2.4a5.6 5.6 0 0 1 5.6 5.6" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
  </svg>
);
