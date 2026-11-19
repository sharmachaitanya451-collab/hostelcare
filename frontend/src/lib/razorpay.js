/**
 * On-demand loader for Razorpay Standard Checkout (`checkout.js`).
 * Resolves immediately when `window.Razorpay` is already available (including tests).
 */

const RAZORPAY_CHECKOUT_SCRIPT_URL = 'https://checkout.razorpay.com/v1/checkout.js'

let pendingLoadPromise = null

export function loadRazorpayCheckoutScript() {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Razorpay Checkout requires a browser environment.'))
  }

  if (typeof window.Razorpay === 'function') {
    return Promise.resolve(window.Razorpay)
  }

  if (pendingLoadPromise) {
    return pendingLoadPromise
  }

  pendingLoadPromise = new Promise((resolve, reject) => {
    const existingScript = document.querySelector(`script[src="${RAZORPAY_CHECKOUT_SCRIPT_URL}"]`)
    if (existingScript) {
      existingScript.addEventListener(
        'load',
        () => {
          pendingLoadPromise = null
          if (typeof window.Razorpay === 'function') {
            resolve(window.Razorpay)
          } else {
            reject(new Error('Razorpay Checkout failed to initialize.'))
          }
        },
        { once: true },
      )
      existingScript.addEventListener(
        'error',
        () => {
          pendingLoadPromise = null
          reject(new Error('Unable to load Razorpay Checkout script.'))
        },
        { once: true },
      )
      return
    }

    const script = document.createElement('script')
    script.src = RAZORPAY_CHECKOUT_SCRIPT_URL
    script.async = true
    script.onload = () => {
      pendingLoadPromise = null
      if (typeof window.Razorpay === 'function') {
        resolve(window.Razorpay)
      } else {
        reject(new Error('Razorpay Checkout script loaded without window.Razorpay.'))
      }
    }
    script.onerror = () => {
      pendingLoadPromise = null
      script.remove()
      reject(new Error('Unable to load Razorpay Checkout. Please check your connection and retry.'))
    }
    document.body.appendChild(script)
  })

  return pendingLoadPromise
}
