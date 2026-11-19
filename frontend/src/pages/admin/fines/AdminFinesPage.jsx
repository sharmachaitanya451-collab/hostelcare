import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../../../context/AppContext'
import { StatusBadge } from '../../../components/Brand'

export function AdminFinesPage() {
  const { fines, finesLoading, finesError, finesPagination, fetchAdminFines } = useApp()
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)

  useEffect(() => {
    const filters = { page, pageSize: 20 }
    if (statusFilter === 'Overdue') {
      filters.overdue = true
    } else if (statusFilter !== 'ALL') {
      filters.status = statusFilter
    }
    if (dateFrom) filters.dateFrom = dateFrom
    if (dateTo) filters.dateTo = dateTo

    fetchAdminFines(filters).catch(() => {})
  }, [fetchAdminFines, statusFilter, dateFrom, dateTo, page])

  const handleRetry = () => {
    const filters = { page, pageSize: 20 }
    if (statusFilter === 'Overdue') {
      filters.overdue = true
    } else if (statusFilter !== 'ALL') {
      filters.status = statusFilter
    }
    if (dateFrom) filters.dateFrom = dateFrom
    if (dateTo) filters.dateTo = dateTo
    fetchAdminFines(filters).catch(() => {})
  }

  // Calculate metrics
  const totalFinesCount = finesPagination?.total ?? fines.length
  const pendingCount = fines.filter((f) => f.status === 'Pending' || f.status === 'Overdue').length
  const disputedCount = fines.filter((f) => f.status === 'Disputed').length
  const totalAmountIssued = fines.reduce((sum, f) => sum + f.amount, 0)
  const totalAmountPending = fines
    .filter((f) => f.status === 'Pending' || f.status === 'Overdue' || f.status === 'Disputed')
    .reduce((sum, f) => sum + f.amount, 0)

  // Categories for filter
  const categories = Array.from(new Set(fines.map((f) => f.category).filter(Boolean)))

  // Filtered list
  const filteredFines = fines.filter((fine) => {
    const q = (searchTerm || '').toLowerCase()
    const matchesSearch =
      (fine.studentName || '').toLowerCase().includes(q) ||
      (fine.studentRoll || '').toLowerCase().includes(q) ||
      (fine.room || '').toLowerCase().includes(q) ||
      String(fine.id || '')
        .toLowerCase()
        .includes(q) ||
      (fine.referenceNo || '').toLowerCase().includes(q) ||
      (fine.description || '').toLowerCase().includes(q)

    const matchesStatus =
      statusFilter === 'ALL' ||
      (statusFilter === 'Overdue'
        ? fine.isOverdue || fine.status === 'Overdue'
        : fine.status === statusFilter)
    const matchesCategory = categoryFilter === 'ALL' || fine.category === categoryFilter

    return matchesSearch && matchesStatus && matchesCategory
  })

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <span className="text-[11px] font-bold text-[#D94378] uppercase tracking-wider">
            Hostel Administration &amp; Disciplinary Cell
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            Fines &amp; Disciplinary Records
          </h1>
          <p className="text-xs text-[#292039]/70 mt-1">
            Issue penalties, process student dispute hearings, and manage hostel dues collection
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Link
            to="/admin/violations"
            className="px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFCF7] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6] transition-colors"
          >
            📊 Violation Insights
          </Link>
          <Link
            to="/admin/fine-disputes"
            className="px-3.5 py-2 rounded-xl border border-purple-300 bg-purple-50 text-xs font-semibold text-purple-900 hover:bg-purple-100 transition-colors flex items-center gap-1.5"
          >
            <span>⚖️ Dispute Queue</span>
            {disputedCount > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-purple-600 text-white text-[10px] font-bold">
                {disputedCount}
              </span>
            )}
          </Link>
          <Link
            to="/admin/fines/new"
            className="px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold hover:bg-[#C23365] shadow-xs transition-colors flex items-center gap-1.5"
          >
            <span>+ Issue New Fine</span>
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[11px] text-[#292039]/60 block font-medium">
            Total Fines Issued
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-[#292039]">{totalFinesCount}</span>
            <span className="text-[10px] text-[#292039]/60 font-mono">(₹{totalAmountIssued})</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[11px] text-[#292039]/60 block font-medium">Pending Recovery</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-[#D94378]">
              ₹{totalAmountPending}
            </span>
            <span className="text-[10px] text-[#292039]/60">({pendingCount} notices)</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[11px] text-[#292039]/60 block font-medium">
            Pending Student Disputes
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-purple-700">{disputedCount}</span>
            <span className="text-[10px] text-purple-600">awaiting review</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[11px] text-[#292039]/60 block font-medium">
            Collection Clearance
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-[#368F83]">
              {fines.filter((f) => f.status === 'Paid').length}
            </span>
            <span className="text-[10px] text-emerald-700">receipts generated</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="relative w-full md:w-80">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by student, roll no, room, ID..."
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
          />
          <svg
            className="w-4 h-4 text-[#292039]/40 absolute left-3 top-2.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(1)
            }}
            aria-label="Filter by status"
            className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
          >
            <option value="ALL">All Statuses</option>
            <option value="Pending">Pending Payment</option>
            <option value="Paid">Paid</option>
            <option value="Disputed">Under Dispute</option>
            <option value="Overdue">Overdue</option>
            <option value="Waived">Waived</option>
            <option value="Cancelled">Cancelled</option>
          </select>

          {/* Category filter */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            aria-label="Filter by category"
            className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
          >
            <option value="ALL">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>

          <input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value)
              setPage(1)
            }}
            aria-label="Issue date from"
            className="px-2.5 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value)
              setPage(1)
            }}
            aria-label="Issue date to"
            className="px-2.5 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
          />
        </div>
      </div>

      {/* Error State */}
      {finesError && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-between gap-4">
          <p className="text-xs text-red-700 font-medium">{finesError}</p>
          <button
            type="button"
            onClick={handleRetry}
            className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-semibold hover:bg-red-700 transition-colors shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading State */}
      {finesLoading && fines.length === 0 ? (
        <div className="p-10 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center space-y-2">
          <p className="font-serif text-base font-bold text-[#292039]">Loading fines...</p>
          <p className="text-xs text-[#292039]/60">Fetching disciplinary and payment records.</p>
        </div>
      ) : totalFinesCount === 0 && !finesError ? (
        <div className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center space-y-2">
          <p className="font-serif text-base font-bold text-[#292039]">
            No Disciplinary Records on File
          </p>
          <p className="text-xs text-[#292039]/65">
            No fines or disciplinary penalties match the current records.
          </p>
        </div>
      ) : (
        <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F7EFE6] text-[#292039]/80 font-semibold border-b border-[#E8DCCF]">
                <tr>
                  <th className="py-3 px-4">Fine ID</th>
                  <th className="py-3 px-4">Student</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Description Snippet</th>
                  <th className="py-3 px-4">Amount</th>
                  <th className="py-3 px-4">Due Date</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E8DCCF]/60">
                {filteredFines.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-[#292039]/60">
                      No fines found matching your search or filters.
                    </td>
                  </tr>
                ) : (
                  filteredFines.map((fine) => (
                    <tr key={fine.id} className="hover:bg-[#FFFDF9] transition-colors">
                      <td className="py-3.5 px-4 font-mono font-bold text-[#292039]">
                        {fine.referenceNo || fine.id}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-[#292039]">{fine.studentName}</div>
                        <div className="text-[10px] text-[#292039]/60 font-mono">
                          {fine.studentRoll} • {fine.room}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-[#292039]/80">{fine.category}</td>
                      <td
                        className="py-3.5 px-4 text-[#292039]/90 max-w-xs truncate"
                        title={fine.description}
                      >
                        {fine.description}
                      </td>
                      <td className="py-3.5 px-4 font-serif font-bold text-[#D94378]">
                        ₹{fine.amount}
                      </td>
                      <td className="py-3.5 px-4 text-[#292039]/70">{fine.dueDate}</td>
                      <td className="py-3.5 px-4">
                        <StatusBadge status={fine.status} />
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          to={`/admin/fines/${fine.id}`}
                          className="px-3 py-1.5 rounded-lg border border-[#D8CEBE] hover:bg-[#F7EFE6] text-[#292039] font-medium transition-colors"
                        >
                          Manage
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {finesPagination && finesPagination.totalPages > 1 && (
            <div className="px-4 py-3 border-t border-[#E8DCCF] bg-[#FFFDF9] flex items-center justify-between text-xs text-[#292039]/75">
              <span>
                Page {finesPagination.page} of {finesPagination.totalPages} ({finesPagination.total}{' '}
                total)
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={page <= 1 || finesLoading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-3 py-1.5 rounded-lg border border-[#D8CEBE] disabled:opacity-40 hover:bg-[#F7EFE6]"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= finesPagination.totalPages || finesLoading}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 rounded-lg border border-[#D8CEBE] disabled:opacity-40 hover:bg-[#F7EFE6]"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
