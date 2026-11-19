import { useState } from 'react'
import { NavLink, Link, Outlet, useNavigate } from 'react-router-dom'
import { HostelCareLogo } from '../components/Brand'

export function PublicLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const navigate = useNavigate()

  const links = [
    { to: '/', label: 'Home' },
    { to: '/about', label: 'About' },
    { to: '/facilities', label: 'Facilities' },
    { to: '/hostel-life', label: 'Hostel Life' },
    { to: '/how-it-works', label: 'How It Works' },
    { to: '/contact', label: 'Contact' },
  ]

  return (
    <div className="min-h-screen bg-[#FFFCF7] text-[#292039] flex flex-col font-sans selection:bg-[#F4AA35]/30">
      {/* ------------------------------------------------------------------- */}
      {/* Public Navbar                                                       */}
      {/* ------------------------------------------------------------------- */}
      <header className="sticky top-0 z-40 bg-[#FFFCF7]/95 backdrop-blur-md border-b border-[#F0E4D4]/80 transition-all">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-20">
            {/* Logo */}
            <Link to="/" className="focus:outline-none text-left cursor-pointer">
              <HostelCareLogo showTagline={true} />
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-7">
              {links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  className={({ isActive }) =>
                    `text-sm font-medium transition-colors ${
                      isActive
                        ? 'text-[#D94378] font-bold border-b-2 border-[#D94378] pb-1'
                        : 'text-[#292039]/80 hover:text-[#D94378]'
                    }`
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>

            {/* Desktop Action CTAs */}
            <div className="hidden lg:flex items-center gap-3">
              <Link
                to="/login"
                className="px-4 py-2 rounded-lg text-sm font-semibold text-[#292039] hover:text-[#D94378] hover:bg-[#F7EFE6] transition-colors border border-[#E8DCCF]"
              >
                Resident Login
              </Link>
              <Link
                to="/register"
                className="px-4 py-2 rounded-lg text-sm font-semibold text-[#FFFCF7] bg-[#D94378] hover:bg-[#C23365] shadow-sm shadow-[#D94378]/25 transition-all"
              >
                New Registration
              </Link>
            </div>

            {/* Mobile menu button */}
            <div className="flex md:hidden items-center gap-2">
              <Link
                to="/login"
                className="text-xs px-2.5 py-1.5 font-semibold text-[#D94378] border border-[#D94378]/30 rounded-md"
              >
                Login
              </Link>
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
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `block w-full text-left px-3 py-2.5 rounded-md text-base font-medium ${
                    isActive
                      ? 'bg-[#F7EFE6] text-[#D94378] font-bold'
                      : 'text-[#292039] hover:bg-[#F7EFE6] hover:text-[#D94378]'
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
            <div className="pt-4 border-t border-[#F0E4D4] flex flex-col gap-2">
              <Link
                to="/login"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2.5 rounded-lg text-sm font-semibold border border-[#E8DCCF] text-[#292039]"
              >
                Resident &amp; Staff Login
              </Link>
              <Link
                to="/register"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2.5 rounded-lg text-sm font-semibold bg-[#D94378] text-[#FFFCF7]"
              >
                Student Self-Registration
              </Link>
            </div>
          </div>
        )}
      </header>

      {/* ------------------------------------------------------------------- */}
      {/* Route Outlet                                                        */}
      {/* ------------------------------------------------------------------- */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* ------------------------------------------------------------------- */}
      {/* Public Footer                                                       */}
      {/* ------------------------------------------------------------------- */}
      <footer className="bg-[#292039] text-[#FFFCF7] pt-16 pb-12 border-t border-[#3D3252] mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-10 pb-12 border-b border-[#473B5E]">
            {/* Brand Column */}
            <div className="space-y-4">
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
              <h4 className="font-serif text-base font-semibold text-[#F4AA35] mb-4">
                Hostel Life
              </h4>
              <ul className="space-y-2.5 text-sm text-[#D8CEBE]">
                <li>
                  <Link to="/about" className="hover:text-white transition-colors">
                    About Our Hostel
                  </Link>
                </li>
                <li>
                  <Link to="/facilities" className="hover:text-white transition-colors">
                    Amenities &amp; Facilities
                  </Link>
                </li>
                <li>
                  <Link to="/hostel-life" className="hover:text-white transition-colors">
                    Student Community
                  </Link>
                </li>
                <li>
                  <Link to="/how-it-works" className="hover:text-white transition-colors">
                    Registration &amp; Approval
                  </Link>
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
                  <Link to="/login" className="hover:text-white transition-colors">
                    Resident Portal Login
                  </Link>
                </li>
                <li>
                  <Link to="/contact" className="hover:text-white transition-colors">
                    Maintenance Helpdesk
                  </Link>
                </li>
                <li>
                  <span className="text-slate-400">Night Warden Escalation: Dial 108</span>
                </li>
                <li>
                  <button
                    onClick={() => navigate('/admin/dashboard')}
                    className="text-xs text-[#D94378] hover:underline mt-2 block cursor-pointer"
                  >
                    Administration Staff Console &rarr;
                  </button>
                </li>
              </ul>
            </div>

            {/* Warden Office Note */}
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
                *All room repairs, electrical hazards and plumbing emergencies are prioritized via
                portal tracking.
              </p>
            </div>
          </div>

          <div className="pt-8 flex flex-col sm:flex-row items-center justify-between text-xs text-[#A89CBF] gap-4">
            <p>
              © {new Date().getFullYear()} HostelCare. Built with Indian collegiate community
              values.
            </p>
            <p>Dates formatted DD/MM/YYYY • All monetary references in Indian Rupee (₹)</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
