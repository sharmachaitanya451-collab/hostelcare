import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center p-6 text-center">
      <div className="max-w-md space-y-5 bg-[#FFFCF7] p-10 rounded-3xl border border-[#E8DCCF] shadow-sm">
        <div className="h-16 w-16 rounded-2xl bg-[#D94378]/10 text-[#D94378] font-serif font-bold text-3xl flex items-center justify-center mx-auto">
          404
        </div>
        <h1 className="font-serif text-3xl font-bold text-[#292039]">Page Not Found</h1>
        <p className="text-xs sm:text-sm text-[#292039]/70 leading-relaxed">
          The room or page you are looking for has been moved or does not exist in the hostel portal
          directory.
        </p>
        <div className="pt-2">
          <Link
            to="/"
            className="inline-block px-6 py-3 rounded-xl text-xs font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25"
          >
            Return to Homepage
          </Link>
        </div>
      </div>
    </div>
  )
}
