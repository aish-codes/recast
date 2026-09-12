/**
 * Shared bits of the two policy documents.
 *
 * Both pages are long runs of heading-and-paragraph, so the type scale lives
 * here once instead of being retyped down each file — and the two documents
 * cannot drift apart typographically as they get edited.
 */

export function Title({ children, updated }: { children: React.ReactNode; updated: string }) {
  return (
    <>
      <span className="eyebrow">Legal</span>
      <h1 className="h2 mt-3.5">{children}</h1>
      <p className="mt-3 text-[13px] text-muted">Last updated {updated}</p>
    </>
  );
}

export function Lede({ children }: { children: React.ReactNode }) {
  return <p className="lede mt-6 text-[15.5px]">{children}</p>;
}

export function Section({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10 border-t border-line pt-8">
      <h2 className="m-0 flex items-baseline gap-3 text-[18px] font-[640] tracking-[-0.016em]">
        <span className="num text-[13px] font-semibold text-muted">{n}</span>
        {title}
      </h2>
      <div className="mt-3 flex flex-col gap-3.5 text-[14.5px] leading-[1.65] text-muted">
        {children}
      </div>
    </section>
  );
}

export function Bullets({ items }: { items: React.ReactNode[] }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-2 p-0">
      {items.map((item, i) => (
        <li key={i} className="relative pl-[18px]">
          <span
            className="absolute top-[9px] left-0 size-[5px] rounded-full"
            style={{ background: "var(--aline)" }}
          />
          {item}
        </li>
      ))}
    </ul>
  );
}
