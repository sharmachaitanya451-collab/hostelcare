import { useState } from 'react'

export function MockPaymentModal({ fine, isOpen, onClose, onSuccess }) {
  const [method, setMethod] = useState('upi')
  const [upiId, setUpiId] = useState('aarav@okhdfcbank')
  const [selectedBank, setSelectedBank] = useState('State Bank of India')
  const [isProcessing, setIsProcessing] = useState(false)
  const [paymentResult, setPaymentResult] = useState(null) // null | 'success' | 'failure'
  const [simulateOutcome, setSimulateOutcome] = useState('success') // 'success' | 'failure'

  if (!isOpen || !fine) return null

  const handlePay = () => {
    setIsProcessing(true)
    setPaymentResult(null)

    setTimeout(() => {
      setIsProcessing(false)
      if (simulateOutcome === 'success') {
        setPaymentResult('success')
        if (onSuccess) {
          onSuccess({
            method:
              method === 'upi'
                ? `UPI (${upiId}) - Mock Razorpay`
                : method === 'netbanking'
                  ? `NetBanking (${selectedBank}) - Mock Razorpay`
                  : 'Debit/Credit Card - Mock Razorpay',
          })
        }
      } else {
        setPaymentResult('failure')
      }
    }, 1200)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs animate-in fade-in">
      <div className="bg-[#FFFCF7] w-full max-w-lg rounded-3xl border border-[#E8DCCF] shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-gradient-to-r from-[#292039] to-[#3D3252] text-[#FFFCF7] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-[#D94378] flex items-center justify-center font-bold text-white text-xs">
              ₹
            </div>
            <div>
              <h3 className="font-serif text-base font-bold">HostelCare Payment Gateway</h3>
              <p className="text-[10px] text-[#F4AA35] font-mono tracking-wider">
                MOCK RAZORPAY ENVIRONMENT
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[#D8CEBE] hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Mock Environment Disclaimer */}
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2.5">
            <span className="text-base shrink-0">⚠️</span>
            <div>
              <p className="font-semibold">Simulated Gateway Boundary</p>
              <p className="text-[11px] text-amber-800">
                This is a mock payment integration for evaluation. No actual financial transaction
                or bank debit will take place.
              </p>
            </div>
          </div>

          {/* Result view if finished */}
          {paymentResult === 'success' ? (
            <div className="text-center py-6 space-y-4">
              <div className="w-14 h-14 rounded-full bg-emerald-100 text-emerald-600 mx-auto flex items-center justify-center">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <div className="space-y-1">
                <h4 className="font-serif text-xl font-bold text-[#292039]">Payment Successful</h4>
                <p className="text-xs text-[#292039]/70">
                  Hostel disciplinary dues of ₹{fine.amount} cleared successfully.
                </p>
              </div>
              <div className="p-4 rounded-2xl bg-[#F7EFE6] border border-[#E8DCCF] text-left text-xs space-y-1.5 font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">Fine Reference:</span>
                  <span className="font-bold text-[#292039]">{fine.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Amount Paid:</span>
                  <span className="font-bold text-emerald-700">₹{fine.amount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Gateway Status:</span>
                  <span className="font-bold text-emerald-600">CAPTURED</span>
                </div>
              </div>
              <button
                onClick={onClose}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white bg-[#368F83] hover:bg-[#2B7369] transition-all cursor-pointer"
              >
                Close &amp; View Updated Status
              </button>
            </div>
          ) : paymentResult === 'failure' ? (
            <div className="text-center py-6 space-y-4">
              <div className="w-14 h-14 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
              <div className="space-y-1">
                <h4 className="font-serif text-xl font-bold text-[#292039]">Payment Declined</h4>
                <p className="text-xs text-[#292039]/70">
                  Simulated bank transaction failed (declined by card issuer or UPI switch timeout).
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setPaymentResult(null)}
                  className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-[#292039] bg-[#E8DCCF] hover:bg-[#D8CEBE] transition-all"
                >
                  Try Again
                </button>
                <button
                  onClick={onClose}
                  className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#292039] hover:bg-[#3D3252] transition-all"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Order Summary */}
              <div className="p-4 rounded-2xl bg-[#F7EFE6] border border-[#E8DCCF] space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#292039]/70">Fine ID:</span>
                  <span className="font-mono font-semibold text-[#292039]">{fine.id}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#292039]/70">Violation Category:</span>
                  <span className="font-medium text-[#292039]">{fine.category}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#292039]/70">Student Resident:</span>
                  <span className="font-medium text-[#292039]">
                    {fine.studentName} ({fine.studentRoll})
                  </span>
                </div>
                <div className="border-t border-[#E8DCCF] pt-2 flex justify-between items-center">
                  <span className="text-sm font-semibold text-[#292039]">
                    Total Amount Payable:
                  </span>
                  <span className="font-serif text-xl font-bold text-[#D94378]">
                    ₹{fine.amount}
                  </span>
                </div>
              </div>

              {/* Payment Mode Selector */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-[#292039]">
                  Select Payment Instrument
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setMethod('upi')}
                    className={`py-2 px-3 rounded-xl border text-xs font-semibold flex flex-col items-center gap-1 transition-all ${
                      method === 'upi'
                        ? 'border-[#D94378] bg-[#D94378]/10 text-[#D94378]'
                        : 'border-[#E8DCCF] bg-white text-[#292039]/80'
                    }`}
                  >
                    <span>📱 UPI QR / VPA</span>
                    <span className="text-[10px] text-slate-500 font-normal">GPay, PhonePe</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setMethod('netbanking')}
                    className={`py-2 px-3 rounded-xl border text-xs font-semibold flex flex-col items-center gap-1 transition-all ${
                      method === 'netbanking'
                        ? 'border-[#D94378] bg-[#D94378]/10 text-[#D94378]'
                        : 'border-[#E8DCCF] bg-white text-[#292039]/80'
                    }`}
                  >
                    <span>🏦 NetBanking</span>
                    <span className="text-[10px] text-slate-500 font-normal">All Major Banks</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setMethod('card')}
                    className={`py-2 px-3 rounded-xl border text-xs font-semibold flex flex-col items-center gap-1 transition-all ${
                      method === 'card'
                        ? 'border-[#D94378] bg-[#D94378]/10 text-[#D94378]'
                        : 'border-[#E8DCCF] bg-white text-[#292039]/80'
                    }`}
                  >
                    <span>💳 Card / RuPay</span>
                    <span className="text-[10px] text-slate-500 font-normal">
                      Debit &amp; Credit
                    </span>
                  </button>
                </div>
              </div>

              {/* Method Details */}
              {method === 'upi' && (
                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-[#292039]">
                    Virtual Payment Address (VPA)
                  </label>
                  <input
                    type="text"
                    value={upiId}
                    onChange={(e) => setUpiId(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-white"
                  />
                </div>
              )}

              {method === 'netbanking' && (
                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-[#292039]">Select Bank</label>
                  <select
                    value={selectedBank}
                    onChange={(e) => setSelectedBank(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-white"
                  >
                    <option>State Bank of India (SBI)</option>
                    <option>HDFC Bank</option>
                    <option>ICICI Bank</option>
                    <option>Punjab National Bank</option>
                    <option>Canara Bank</option>
                    <option>Bank of Baroda</option>
                  </select>
                </div>
              )}

              {method === 'card' && (
                <div className="space-y-2">
                  <div className="p-3 rounded-xl bg-slate-100 text-xs font-mono text-slate-700">
                    Card: 4111 •••• •••• 1111 (Mock Visa / RuPay)
                  </div>
                </div>
              )}

              {/* Simulation outcome toggle for test evaluator */}
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs flex items-center justify-between">
                <span className="text-slate-600">Simulate Response:</span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setSimulateOutcome('success')}
                    className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                      simulateOutcome === 'success'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    Success
                  </button>
                  <button
                    type="button"
                    onClick={() => setSimulateOutcome('failure')}
                    className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                      simulateOutcome === 'failure'
                        ? 'bg-rose-600 text-white'
                        : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    Failure
                  </button>
                </div>
              </div>

              {/* Submit Pay */}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isProcessing}
                  className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-[#292039] bg-[#E8DCCF] hover:bg-[#D8CEBE] transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handlePay}
                  disabled={isProcessing}
                  className="flex-2 py-2.5 rounded-xl text-sm font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {isProcessing ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Contacting Bank Gateway...</span>
                    </>
                  ) : (
                    <span>Pay ₹{fine.amount} Now</span>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
