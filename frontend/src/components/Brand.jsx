export function HostelCareLogo({ className = 'h-9 w-auto', showTagline = false }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* Brand Icon: Arch + Courtyard Lamp motif (SVG rect gradient ensures print/PDF visibility) */}
      <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#D94378] to-[#C95337] shadow-sm shadow-[#D94378]/25 print:shadow-none">
        <svg viewBox="0 0 40 40" fill="none" aria-hidden="true" className="h-10 w-10 rounded-xl">
          <defs>
            <linearGradient id="hostelcare-logo-grad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#D94378" />
              <stop offset="100%" stopColor="#C95337" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="40" height="40" rx="12" fill="url(#hostelcare-logo-grad)" />
          <g
            transform="translate(8, 8)"
            stroke="#FFFCF7"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {/* Indian architectural arch roof */}
            <path d="M4 21V11C4 7 8 4 12 4C16 4 20 7 20 11V21" />
            {/* Inner courtyard doorway & lamp flame */}
            <path d="M9 21V13C9 11.5 10.3 10.5 12 10.5C13.7 10.5 15 11.5 15 13V21" />
            <circle cx="12" cy="7.5" r="1" fill="#F4AA35" stroke="#F4AA35" />
          </g>
        </svg>
      </div>

      <div className="flex flex-col">
        <span className="font-serif text-xl font-bold tracking-tight text-[#292039] leading-none">
          Hostel<span className="text-[#D94378]">Care</span>
        </span>
        {showTagline && (
          <span className="text-[11px] font-medium text-[#368F83] tracking-wider uppercase mt-1">
            A place to belong
          </span>
        )}
      </div>
    </div>
  )
}

export function StatusBadge({ status }) {
  const map = {
    // Complaint Lifecycle Statuses
    Submitted: {
      label: 'Submitted',
      bg: 'bg-amber-50',
      text: 'text-amber-800',
      border: 'border-amber-300',
      dot: 'bg-amber-500',
    },
    submitted: {
      label: 'Submitted',
      bg: 'bg-amber-50',
      text: 'text-amber-800',
      border: 'border-amber-300',
      dot: 'bg-amber-500',
    },
    open: {
      label: 'Submitted',
      bg: 'bg-amber-50',
      text: 'text-amber-800',
      border: 'border-amber-300',
      dot: 'bg-amber-500',
    },
    'Under Review': {
      label: 'Under Review',
      bg: 'bg-purple-50',
      text: 'text-purple-700',
      border: 'border-purple-300',
      dot: 'bg-purple-500',
    },
    under_review: {
      label: 'Under Review',
      bg: 'bg-purple-50',
      text: 'text-purple-700',
      border: 'border-purple-300',
      dot: 'bg-purple-500',
    },
    Assigned: {
      label: 'Assigned',
      bg: 'bg-blue-50',
      text: 'text-blue-700',
      border: 'border-blue-300',
      dot: 'bg-blue-500',
    },
    assigned: {
      label: 'Assigned',
      bg: 'bg-blue-50',
      text: 'text-blue-700',
      border: 'border-blue-300',
      dot: 'bg-blue-500',
    },
    Accepted: {
      label: 'Accepted',
      bg: 'bg-sky-50',
      text: 'text-sky-700',
      border: 'border-sky-300',
      dot: 'bg-sky-500',
    },
    accepted: {
      label: 'Accepted',
      bg: 'bg-sky-50',
      text: 'text-sky-700',
      border: 'border-sky-300',
      dot: 'bg-sky-500',
    },
    Completed: {
      label: 'Completed',
      bg: 'bg-teal-50',
      text: 'text-teal-800',
      border: 'border-teal-300',
      dot: 'bg-teal-500',
    },
    completed: {
      label: 'Completed',
      bg: 'bg-teal-50',
      text: 'text-teal-800',
      border: 'border-teal-300',
      dot: 'bg-teal-500',
    },
    'In Progress': {
      label: 'In Progress',
      bg: 'bg-[#368F83]/15',
      text: 'text-[#246A60]',
      border: 'border-[#368F83]/40',
      dot: 'bg-[#368F83]',
    },
    in_progress: {
      label: 'In Progress',
      bg: 'bg-[#368F83]/15',
      text: 'text-[#246A60]',
      border: 'border-[#368F83]/40',
      dot: 'bg-[#368F83]',
    },
    Resolved: {
      label: 'Resolved',
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      border: 'border-emerald-300',
      dot: 'bg-emerald-500',
    },
    resolved: {
      label: 'Resolved',
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      border: 'border-emerald-300',
      dot: 'bg-emerald-500',
    },
    Closed: {
      label: 'Closed',
      bg: 'bg-slate-100',
      text: 'text-slate-600',
      border: 'border-slate-300',
      dot: 'bg-slate-400',
    },
    closed: {
      label: 'Closed',
      bg: 'bg-slate-100',
      text: 'text-slate-600',
      border: 'border-slate-300',
      dot: 'bg-slate-400',
    },
    Rejected: {
      label: 'Rejected',
      bg: 'bg-rose-50',
      text: 'text-rose-700',
      border: 'border-rose-300',
      dot: 'bg-rose-500',
    },
    rejected: {
      label: 'Rejected',
      bg: 'bg-rose-50',
      text: 'text-rose-700',
      border: 'border-rose-300',
      dot: 'bg-rose-500',
    },
    active: {
      label: 'Active',
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      border: 'border-emerald-300',
      dot: 'bg-emerald-500',
    },
    pending: {
      label: 'Pending Approval',
      bg: 'bg-[#F4AA35]/20',
      text: 'text-[#9E5F05]',
      border: 'border-[#F4AA35]/50',
      dot: 'bg-[#F4AA35]',
    },
    // Fines Statuses
    Pending: {
      label: 'Pending Payment',
      bg: 'bg-[#F4AA35]/15',
      text: 'text-[#B36E08]',
      border: 'border-[#F4AA35]/40',
      dot: 'bg-[#F4AA35]',
    },
    Paid: {
      label: 'Paid',
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      border: 'border-emerald-300',
      dot: 'bg-emerald-500',
    },
    Overdue: {
      label: 'Overdue',
      bg: 'bg-rose-50',
      text: 'text-rose-700',
      border: 'border-rose-300',
      dot: 'bg-rose-500',
    },
    Disputed: {
      label: 'Under Dispute',
      bg: 'bg-purple-50',
      text: 'text-purple-700',
      border: 'border-purple-300',
      dot: 'bg-purple-500',
    },
    Waived: {
      label: 'Waived',
      bg: 'bg-teal-50',
      text: 'text-teal-700',
      border: 'border-teal-300',
      dot: 'bg-teal-500',
    },
    Cancelled: {
      label: 'Cancelled',
      bg: 'bg-slate-100',
      text: 'text-slate-600',
      border: 'border-slate-300',
      dot: 'bg-slate-400',
    },
  }

  const style = map[status] || {
    label: status,
    bg: 'bg-slate-100',
    text: 'text-slate-600',
    border: 'border-slate-200',
    dot: 'bg-slate-400',
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${style.bg} ${style.text} ${style.border}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  )
}

export function PriorityBadge({ priority }) {
  const map = {
    High: 'bg-red-50 text-red-700 border-red-200',
    Medium: 'bg-[#F4AA35]/15 text-[#9E5F05] border-[#F4AA35]/40',
    Low: 'bg-blue-50 text-blue-700 border-blue-200',
  }
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold border ${map[priority] || 'bg-slate-100 text-slate-700 border-slate-200'}`}
    >
      {priority}
    </span>
  )
}
