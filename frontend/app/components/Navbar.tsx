const NAV_LINKS = [
  { label: "How it works", href: "#how-it-works" },
  { label: "Export chats", href: "#export-guide" },
  { label: "FAQ", href: "#faq" },
];

export function Navbar() {
  return (
    <nav className="flex items-center justify-between border-b border-hairline px-6 py-[26px] sm:px-14">
      <span className="font-serif text-[20px] font-medium tracking-[-0.01em]">
        Glasshouse
      </span>

      <div className="hidden items-center gap-8 text-[14px] font-medium text-muted md:flex">
        {NAV_LINKS.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className="transition-opacity hover:opacity-60"
          >
            {link.label}
          </a>
        ))}
      </div>
    </nav>
  );
}
