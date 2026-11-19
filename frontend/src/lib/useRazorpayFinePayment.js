import { useCallback, useState } from 'react'
import { loadRazorpayCheckoutScript } from './razorpay'

/**
 * Shared hook to run student-initiated Razorpay Standard Checkout (Test Mode)
 * for a disciplinary fine with double-submit protection and server-side verification.
 */
export function useRazorpayFinePayment({
  createRazorpayOrder,
  verifyRazorpayPayment,
  recordRazorpayAttemptFailure,
  onSuccess,
}) {
  const [payingFineId, setPayingFineId] = useState(null)
  const [paymentPhase, setPaymentPhase] = useState('idle')
  const [paymentError, setPaymentError] = useState('')
  const [paymentNotice, setPaymentNotice] = useState('')

  const clearPaymentFeedback = useCallback(() => {
    setPaymentError('')
    setPaymentNotice('')
  }, [])

  const startOnlinePayment = useCallback(
    async (fine) => {
      if (!fine || paymentPhase !== 'idle') return
      const fineId = fine.referenceNo || fine.id
      setPayingFineId(fineId)
      setPaymentPhase('creating_order')
      setPaymentError('')
      setPaymentNotice('')

      try {
        const order = await createRazorpayOrder(fineId)
        if (!order?.orderId || !order?.keyId) {
          throw new Error('Unable to initialize Razorpay payment order.')
        }

        const RazorpayCtor = await loadRazorpayCheckoutScript()
        setPaymentPhase('checkout_open')

        let terminalHandled = false
        const rzp = new RazorpayCtor({
          key: order.keyId,
          amount: order.amountPaise,
          currency: order.currency || 'INR',
          name: order.name || 'HostelCare',
          description: order.description || `Fine Settlement — ${fineId}`,
          order_id: order.orderId,
          prefill: order.prefill || {},
          notes: order.notes || { fineReference: fineId },
          theme: { color: '#D94378' },
          handler: async (response) => {
            terminalHandled = true
            setPaymentPhase('verifying')
            setPaymentError('')
            try {
              const verified = await verifyRazorpayPayment(fineId, {
                razorpay_order_id: response?.razorpay_order_id || order.orderId,
                razorpay_payment_id: response?.razorpay_payment_id,
                razorpay_signature: response?.razorpay_signature,
              })
              const receiptRef = verified?.receipt?.receiptNumber
              setPaymentNotice(
                receiptRef
                  ? `Payment verified! Official receipt ${receiptRef} has been generated.`
                  : 'Payment verified and recorded successfully.',
              )
              if (onSuccess) {
                await onSuccess(verified)
              }
            } catch (err) {
              setPaymentError(
                err?.message ||
                  'Payment signature verification failed. Please check your fine status before retrying.',
              )
            } finally {
              setPaymentPhase('idle')
              setPayingFineId(null)
            }
          },
          modal: {
            ondismiss: async () => {
              if (terminalHandled) return
              terminalHandled = true
              try {
                if (recordRazorpayAttemptFailure) {
                  await recordRazorpayAttemptFailure(fineId, {
                    razorpay_order_id: order.orderId,
                    cancelled: true,
                  })
                }
              } catch {
                // Best-effort cancellation logging
              } finally {
                setPaymentNotice('Checkout cancelled. No payment was captured.')
                setPaymentPhase('idle')
                setPayingFineId(null)
              }
            },
          },
        })

        if (typeof rzp.on === 'function') {
          rzp.on('payment.failed', async (failureResp) => {
            terminalHandled = true
            const errDetails = failureResp?.error || {}
            try {
              if (recordRazorpayAttemptFailure) {
                await recordRazorpayAttemptFailure(fineId, {
                  razorpay_order_id: errDetails?.metadata?.order_id || order.orderId,
                  razorpay_payment_id: errDetails?.metadata?.payment_id || null,
                  error_code: errDetails?.code || 'payment_failed',
                  error_description: errDetails?.description || 'Payment failed in checkout.',
                  cancelled: false,
                })
              }
            } catch {
              // Best-effort failure logging
            } finally {
              setPaymentError(
                errDetails?.description ||
                  'Online payment failed. Please retry or contact the Warden office.',
              )
              setPaymentPhase('idle')
              setPayingFineId(null)
            }
          })
        }

        rzp.open()
      } catch (err) {
        setPaymentError(err?.message || 'Unable to start online payment.')
        setPaymentPhase('idle')
        setPayingFineId(null)
      }
    },
    [
      createRazorpayOrder,
      onSuccess,
      paymentPhase,
      recordRazorpayAttemptFailure,
      verifyRazorpayPayment,
    ],
  )

  return {
    payingFineId,
    paymentPhase,
    paymentError,
    paymentNotice,
    isProcessingPayment: paymentPhase !== 'idle',
    clearPaymentFeedback,
    startOnlinePayment,
  }
}
