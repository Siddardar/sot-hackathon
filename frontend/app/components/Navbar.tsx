const NAV_LINKS = ["How it works", "Privacy", "FAQ"];

export function Navbar() {
  return (
    <nav className="flex items-center justify-between border-b border-hairline px-6 py-[26px] sm:px-14">
      <span className="font-serif text-[20px] font-medium tracking-[-0.01em]">
        Tell
      </span>

      <div className="hidden items-center gap-8 text-[14px] font-medium text-muted md:flex">
        {NAV_LINKS.map((link) => (
          <a
            key={link}
            href="#"
            className="transition-opacity hover:opacity-60"
          >
            {link}
          </a>
        ))}
      </div>

      <button
        type="button"
        className="rounded-full border-[1.5px] border-ink px-5 py-[9px] text-[13px] font-semibold transition-colors hover:bg-ink/[0.06]"
      >
        Sign in
      </button>
    </nav>
  );
}
