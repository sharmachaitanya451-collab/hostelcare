import { useState } from 'react'
import { HostelCareLogo } from './Brand'

export function PublicNavbar({ activeSection, onNavigate, onOpenLogin, onOpenRegister }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const links = [
    { id: 'home', label: 'Home' },
    { id: 'about', label: 'About' },
    { id: 'facilities', label: 'Facilities' },
    { id: 'hostel-life', label: 'Hostel Life' },
    { id: 'how-it-works', label: 'How It Works' },
    { id: 'contact', label: 'Contact' },
  ]

  const handleLinkClick = (id) => {
    onNavigate(id)
    setMobileMenuOpen(false)
  }

  return (
    <header className="sticky top-0 z-40 bg-[#FFFCF7]/90 backdrop-blur-md border-b border-[#F0E4D4]/80 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          {/* Logo */}
          <button
            onClick={() => handleLinkClick('home')}
            className="focus:outline-none text-left cursor-pointer"
          >
            <HostelCareLogo showTagline={true} />
          </button>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center gap-7">
            {links.map((link) => (
              <button
                key={link.id}
                onClick={() => handleLinkClick(link.id)}
                className={`text-sm font-medium transition-colors cursor-pointer ${
                  activeSection === link.id
                    ? 'text-[#D94378] font-semibold'
                    : 'text-[#292039]/80 hover:text-[#D94378]'
                }`}
              >
                {link.label}
              </button>
            ))}
          </nav>

          {/* Desktop Action CTAs */}
          <div className="hidden lg:flex items-center gap-3">
            <button
              onClick={onOpenLogin}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-[#292039] hover:text-[#D94378] hover:bg-[#F7EFE6] transition-colors cursor-pointer border border-[#E8DCCF]"
            >
              Resident Login
            </button>
            <button
              onClick={onOpenRegister}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-[#FFFCF7] bg-[#D94378] hover:bg-[#C23365] shadow-sm shadow-[#D94378]/25 transition-all cursor-pointer"
            >
              New Registration
            </button>
          </div>

          {/* Mobile menu hamburger toggle */}
          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={onOpenLogin}
              className="text-xs px-2.5 py-1.5 font-semibold text-[#D94378] border border-[#D94378]/30 rounded-md"
            >
              Login
            </button>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-[#292039] hover:bg-[#F7EFE6] focus:outline-none"
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                ) : (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-[#F0E4D4] bg-[#FFFCF7] px-4 pt-2 pb-6 space-y-2">
          {links.map((link) => (
            <button
              key={link.id}
              onClick={() => handleLinkClick(link.id)}
              className="block w-full text-left px-3 py-2.5 rounded-md text-base font-medium text-[#292039] hover:bg-[#F7EFE6] hover:text-[#D94378]"
            >
              {link.label}
            </button>
          ))}
          <div className="pt-4 border-t border-[#F0E4D4] flex flex-col gap-2">
            <button
              onClick={() => {
                setMobileMenuOpen(false)
                onOpenLogin()
              }}
              className="w-full text-center py-2.5 rounded-lg text-sm font-semibold border border-[#E8DCCF] text-[#292039]"
            >
              Resident & Staff Login
            </button>
            <button
              onClick={() => {
                setMobileMenuOpen(false)
                onOpenRegister()
              }}
              className="w-full text-center py-2.5 rounded-lg text-sm font-semibold bg-[#D94378] text-[#FFFCF7]"
            >
              Student Self-Registration
            </button>
          </div>
        </div>
      )}
    </header>
  )
}

export function PublicFooter({ onNavigate, onOpenLogin, onOpenAdmin }) {
  return (
    <footer className="bg-[#292039] text-[#FFFCF7] pt-16 pb-12 border-t border-[#3D3252]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 pb-12 border-b border-[#473B5E]">
          {/* Brand Info */}
          <div className="md:col-span-1 space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#D94378] text-[#FFFCF7]">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  className="h-5 w-5"
                >
                  <path d="M4 21V11C4 7 8 4 12 4C16 4 20 7 20 11V21" />
                  <path d="M9 21V13C9 11.5 10.3 10.5 12 10.5C13.7 10.5 15 11.5 15 13V21" />
                </svg>
              </div>
              <span className="font-serif text-2xl font-bold text-[#FFFCF7]">
                Hostel<span className="text-[#F4AA35]">Care</span>
              </span>
            </div>
            <p className="text-sm text-[#D8CEBE] leading-relaxed">
              A place to belong. Dedicated to college hostel residents, wardens, and maintenance
              teams across Indian campuses.
            </p>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#372B4D] text-xs text-[#F4AA35] border border-[#52416F]">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              Academic Session 2026–27
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h4 className="font-serif text-base font-semibold text-[#F4AA35] mb-4">Hostel Life</h4>
            <ul className="space-y-2.5 text-sm text-[#D8CEBE]">
              <li>
                <button
                  onClick={() => onNavigate('about')}
                  className="hover:text-white transition-colors"
                >
                  About Our Hostel
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('facilities')}
                  className="hover:text-white transition-colors"
                >
                  Amenities & Facilities
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('hostel-life')}
                  className="hover:text-white transition-colors"
                >
                  Student Community
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('how-it-works')}
                  className="hover:text-white transition-colors"
                >
                  Registration & Approval
                </button>
              </li>
            </ul>
          </div>

          {/* Resident Support */}
          <div>
            <h4 className="font-serif text-base font-semibold text-[#F4AA35] mb-4">
              Resident Support
            </h4>
            <ul className="space-y-2.5 text-sm text-[#D8CEBE]">
              <li>
                <button onClick={onOpenLogin} className="hover:text-white transition-colors">
                  Resident Portal Login
                </button>
              </li>
              <li>
                <button
                  onClick={() => onNavigate('contact')}
                  className="hover:text-white transition-colors"
                >
                  Maintenance Helpdesk
                </button>
              </li>
              <li>
                <span className="text-slate-400">
                  Night Warden Escalation: Dial 108 from Intercom
                </span>
              </li>
              <li>
                <button
                  onClick={onOpenAdmin}
                  className="text-xs text-[#D94378] hover:underline mt-2 block"
                >
                  Administration Staff Access &rarr;
                </button>
              </li>
            </ul>
          </div>

          {/* Office Contact Note */}
          <div>
            <h4 className="font-serif text-base font-semibold text-[#F4AA35] mb-4">
              Warden Office
            </h4>
            <p className="text-sm text-[#D8CEBE] leading-relaxed mb-3">
              Office Hours: Monday to Saturday
              <br />
              09:30 AM to 01:30 PM &amp; 03:30 PM to 06:30 PM
            </p>
            <p className="text-xs text-[#9E90B0]">
              *For emergency plumbing, electrical fire hazards or medical assistance, please contact
              the ground floor security desk immediately.
            </p>
          </div>
        </div>

        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between text-xs text-[#A89CBF] gap-4">
          <p>
            © {new Date().getFullYear()} HostelCare. Built with Indian collegiate community values.
          </p>
          <p>Dates formatted DD/MM/YYYY • All monetary references in Indian Rupee (₹)</p>
        </div>
      </div>
    </footer>
  )
}
