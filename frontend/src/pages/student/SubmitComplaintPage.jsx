import { useEffect, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useApp } from '../../context/AppContext'

const MAX_PHOTOS = 3
const MAX_PHOTO_BYTES = 5 * 1024 * 1024
const ALLOWED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])
const ALLOWED_IMAGE_EXT_RE = /\.(jpe?g|png|webp)$/i

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function isAllowedClientImage(file) {
  if (!file) return false
  if (file.type) {
    return ALLOWED_IMAGE_TYPES.has(file.type.toLowerCase())
  }
  return ALLOWED_IMAGE_EXT_RE.test(file.name || '')
}

export function SubmitComplaintPage() {
  const { user, blocks, addComplaint } = useApp()
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const previewUrlsRef = useRef([])
  const redirectTimerRef = useRef(null)

  const hasActiveRoom =
    user?.hasActiveRoom !== false &&
    Boolean(user?.room && user.room !== 'Unassigned' && user.room !== 'Unallocated')

  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('') // optional
  const [customCategory, setCustomCategory] = useState('')
  const [priority, setPriority] = useState('Medium')
  const [locationType, setLocationType] = useState(hasActiveRoom ? 'room' : 'common_area')
  const [locationDetail, setLocationDetail] = useState('')
  const [blockCode, setBlockCode] = useState(user?.blockCode || '')
  const [description, setDescription] = useState('')
  const [selectedPhotos, setSelectedPhotos] = useState([])
  const [photoError, setPhotoError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    previewUrlsRef.current = selectedPhotos.map((p) => p.previewUrl).filter(Boolean)
  }, [selectedPhotos])

  useEffect(() => {
    return () => {
      if (redirectTimerRef.current !== null) {
        clearTimeout(redirectTimerRef.current)
        redirectTimerRef.current = null
      }
      if (typeof URL.revokeObjectURL === 'function') {
        previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url))
      }
    }
  }, [])

  const handlePhotoSelection = (e) => {
    const incoming = Array.from(e.target.files || [])
    if (e.target) {
      e.target.value = ''
    }
    if (incoming.length === 0) return

    setPhotoError('')
    const errors = []
    const nextPhotos = [...selectedPhotos]
    const existingKeys = new Set(
      selectedPhotos.map((p) => `${p.name}:${p.size}:${p.file.lastModified}`),
    )

    for (const file of incoming) {
      const dedupeKey = `${file.name}:${file.size}:${file.lastModified}`
      if (existingKeys.has(dedupeKey)) {
        errors.push(`"${file.name}" is already attached.`)
        continue
      }
      if (!isAllowedClientImage(file)) {
        errors.push(`"${file.name}" is not a supported JPEG, PNG, or WebP image.`)
        continue
      }
      if (file.size <= 0) {
        errors.push(`"${file.name}" is empty.`)
        continue
      }
      if (file.size > MAX_PHOTO_BYTES) {
        errors.push(`"${file.name}" exceeds the 5 MB per-photo limit.`)
        continue
      }
      if (nextPhotos.length >= MAX_PHOTOS) {
        errors.push(`You may attach at most ${MAX_PHOTOS} photos per complaint.`)
        break
      }

      const previewUrl = typeof URL.createObjectURL === 'function' ? URL.createObjectURL(file) : ''
      existingKeys.add(dedupeKey)
      nextPhotos.push({
        id: `${dedupeKey}-${Math.random().toString(36).slice(2, 8)}`,
        file,
        name: file.name,
        size: file.size,
        previewUrl,
      })
    }

    setSelectedPhotos(nextPhotos)
    if (errors.length > 0) {
      setPhotoError(errors.join(' '))
    }
  }

  const handleRemovePhoto = (photoId) => {
    setPhotoError('')
    setSelectedPhotos((prev) => {
      const target = prev.find((p) => p.id === photoId)
      if (target?.previewUrl && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(target.previewUrl)
      }
      return prev.filter((p) => p.id !== photoId)
    })
  }

  const todayStr = new Date().toLocaleDateString('en-GB')
  const studentRoom = hasActiveRoom ? user?.room : 'Unassigned'
  const studentBlock =
    user?.block ||
    (studentRoom.startsWith('A') ? 'Block A' : studentRoom.startsWith('B') ? 'Block B' : 'Hostel')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (submitting || success) return
    setErrorMsg('')

    if (!title.trim()) {
      setErrorMsg('Complaint title is required.')
      return
    }

    if (locationType === 'room' && !hasActiveRoom) {
      setErrorMsg(
        'Room-specific complaints require an active room allocation. Please select Common Area instead.',
      )
      return
    }

    if (locationType === 'common_area' && !locationDetail.trim()) {
      setErrorMsg(
        'Please specify the common-area location (e.g., 2nd floor corridor water cooler, reading hall).',
      )
      return
    }

    if (!description.trim() || description.trim().length < 5) {
      setErrorMsg('Please describe the problem in your own words.')
      return
    }

    const finalCategory =
      category === 'Other' && customCategory.trim()
        ? customCategory.trim()
        : category.trim() || null

    setSubmitting(true)
    try {
      const created = await addComplaint({
        title: title.trim(),
        category: finalCategory,
        priority,
        locationType,
        locationDetail: locationType === 'common_area' ? locationDetail.trim() : null,
        blockCode: locationType === 'common_area' && blockCode ? blockCode : null,
        description: description.trim(),
        photos: selectedPhotos.map((p) => p.file),
      })
      setSuccess(true)
      const targetId = created?.id || created?.reference_no || ''
      if (redirectTimerRef.current !== null) {
        clearTimeout(redirectTimerRef.current)
      }
      redirectTimerRef.current = setTimeout(() => {
        redirectTimerRef.current = null
        navigate(targetId ? `/student/complaints/${targetId}` : '/student/complaints')
      }, 400)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to submit complaint. Please check your input.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="pb-4 border-b border-[#F0E4D4] space-y-1">
        <Link
          to="/student/complaints"
          className="text-xs font-semibold text-[#D94378] hover:underline flex items-center gap-1"
        >
          &larr; Back to Complaints
        </Link>
        <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
          Submit Maintenance Complaint
        </h1>
        <p className="text-xs text-[#292039]/70">
          Describe any hostel or room maintenance issue in your own words. The warden office will
          review and dispatch duty technicians.
        </p>
      </div>

      {/* Auto-associated Identity Badge */}
      <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
        <div>
          <span className="text-[#292039]/60 block text-[11px]">Logged Resident Identity:</span>
          <span className="font-bold text-[#292039]">
            {user?.fullName || 'Resident Student'}
          </span>{' '}
          <span className="font-mono text-[#292039]/70">({user?.rollNumber || '2026CSB1042'})</span>
        </div>
        <div className="sm:text-right">
          <span className="text-[#292039]/60 block text-[11px]">Associated Allotment:</span>
          {hasActiveRoom ? (
            <>
              <span className="font-bold text-[#D94378]">Room {studentRoom}</span>{' '}
              <span className="text-[#292039]/70 font-medium">({studentBlock})</span>
            </>
          ) : (
            <span className="font-bold text-amber-800">
              No Active Room Allocation (Common-Area Eligible)
            </span>
          )}
        </div>
      </div>

      {success && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-800 text-xs font-semibold flex items-center gap-2">
          <span className="text-base">✓</span>
          <span>Complaint submitted successfully! Redirecting to ticket status...</span>
        </div>
      )}

      {errorMsg && (
        <div
          role="alert"
          className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs"
        >
          {errorMsg}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-5"
      >
        {/* Location Type Selector (Room vs Common Area per D5/ADR-019) */}
        <div>
          <label className="block text-xs font-semibold text-[#292039] mb-1.5">
            Problem Location Type *
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              type="button"
              disabled={!hasActiveRoom}
              onClick={() => setLocationType('room')}
              className={`p-3 rounded-xl border text-left transition-all ${
                locationType === 'room'
                  ? 'border-[#D94378] bg-[#D94378]/10 text-[#292039]'
                  : !hasActiveRoom
                    ? 'border-[#E8DCCF] bg-slate-100/70 text-[#292039]/40 cursor-not-allowed'
                    : 'border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]/80 hover:border-[#292039]/40 cursor-pointer'
              }`}
            >
              <div className="text-xs font-bold">
                🏠 My Allotted Room {hasActiveRoom ? `(${studentRoom})` : '(Requires Active Room)'}
              </div>
              <div className="text-[11px] opacity-75 mt-0.5">
                {hasActiveRoom
                  ? `Automatically linked to Room ${studentRoom} (${studentBlock})`
                  : 'Room-specific issues require an active room allocation'}
              </div>
            </button>

            <button
              type="button"
              onClick={() => setLocationType('common_area')}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                locationType === 'common_area'
                  ? 'border-[#368F83] bg-[#368F83]/10 text-[#292039]'
                  : 'border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]/80 hover:border-[#292039]/40'
              }`}
            >
              <div className="text-xs font-bold">🏛️ Common Area / Wing Facility</div>
              <div className="text-[11px] opacity-75 mt-0.5">
                Corridors, water coolers, washrooms, mess, or study halls
              </div>
            </button>
          </div>
        </div>

        {locationType === 'common_area' && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 rounded-2xl bg-[#F7EFE6]/60 border border-[#E8DCCF]">
            <div className="sm:col-span-2">
              <label
                htmlFor="common-area-location-detail"
                className="block text-xs font-semibold text-[#292039] mb-1.5"
              >
                Common Area Location Detail *
              </label>
              <input
                id="common-area-location-detail"
                type="text"
                required
                placeholder="e.g. 2nd Floor Corridor near Water Cooler, Common Reading Hall..."
                value={locationDetail}
                onChange={(e) => setLocationDetail(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#368F83] bg-[#FFFDF9]"
              />
            </div>

            <div>
              <label
                htmlFor="common-area-block"
                className="block text-xs font-semibold text-[#292039] mb-1.5"
              >
                Hostel Block (Optional)
              </label>
              <select
                id="common-area-block"
                value={blockCode}
                onChange={(e) => setBlockCode(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#368F83] bg-[#FFFDF9]"
              >
                <option value="">(Any / Campus-wide)</option>
                {blocks.map((b) => (
                  <option key={b.code} value={b.code}>
                    {b.name} ({b.code})
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-[#292039] mb-1.5">
            Complaint Title *
          </label>
          <input
            type="text"
            required
            placeholder="e.g. Broken bed frame, Faulty ceiling fan, Water leakage, Damaged door lock..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold text-[#292039]">
                Suggested Category
              </label>
              <span className="text-[10px] text-slate-500 font-medium">(Optional)</span>
            </div>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
            >
              <option value="">(None / General problem)</option>
              <option value="Electrical">Electrical (Fan, Switchboard, Light)</option>
              <option value="Plumbing">Plumbing (Water leakage, Tap, Washroom)</option>
              <option value="Furniture">Furniture (Bed, Study Chair, Almirah)</option>
              <option value="Cleaning">Cleaning &amp; Housekeeping</option>
              <option value="Internet">Internet &amp; Campus Wi-Fi</option>
              <option value="General maintenance">General maintenance (Door, Window, Wall)</option>
              <option value="Other">Other Specific Category</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#292039] mb-1.5">
              Priority Level *
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
            >
              <option value="Low">Low (Routine, minor wear and tear)</option>
              <option value="Medium">Medium (Disrupting regular study or comfort)</option>
              <option value="High">
                High (Urgent: safety hazard, no water, sparks, lock broken)
              </option>
            </select>
          </div>
        </div>

        {category === 'Other' && (
          <div>
            <label className="block text-xs font-semibold text-[#292039] mb-1.5">
              Specify Category (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g. Corridor lighting, Mesh screen repair..."
              value={customCategory}
              onChange={(e) => setCustomCategory(e.target.value)}
              className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
            />
          </div>
        )}

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-xs font-semibold text-[#292039]">
              Detailed Problem Description *
            </label>
            <span className="text-[10px] text-[#D94378] font-semibold uppercase">
              Free-Text in your own words
            </span>
          </div>
          <textarea
            rows={5}
            required
            placeholder="Explain any hostel-related issue in your own words (e.g. Faulty ceiling fan clattering loudly, broken bed leg making it tilt, bathroom tap leaking onto floor, no water supply in washroom, damaged lock bolt sticking)..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
          />
          <p className="text-[11px] text-[#292039]/60 mt-1">
            You are not restricted to predefined categories. Describe the problem fully so duty
            staff bring the right tools.
          </p>
        </div>

        {/* Optional Photo Attachments (Up to 3, max 5 MB each, JPEG/PNG/WebP) */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="complaint-photo-upload"
              className="block text-xs font-semibold text-[#292039]"
            >
              Problem Photos <span className="font-normal text-[#292039]/60">(Optional)</span>
            </label>
            <span className="text-[11px] font-mono text-[#292039]/60">
              {selectedPhotos.length}/{MAX_PHOTOS} attached
            </span>
          </div>

          <div className="p-4 rounded-2xl border border-dashed border-[#D8CEBE] bg-[#FFFDF9] space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="text-xs text-[#292039]/75">
                <p className="font-semibold text-[#292039]">
                  Attach up to 3 photos to help staff inspect the issue
                </p>
                <p className="text-[11px] text-[#292039]/60 mt-0.5">
                  Accepted formats: JPEG, PNG, WebP • Max 5 MB per photo
                </p>
              </div>
              <input
                ref={fileInputRef}
                id="complaint-photo-upload"
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp"
                disabled={selectedPhotos.length >= MAX_PHOTOS || submitting || success}
                onChange={handlePhotoSelection}
                className="text-xs text-[#292039] file:mr-3 file:py-2 file:px-3.5 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-[#F7EFE6] file:text-[#292039] hover:file:bg-[#E8DCCF] file:cursor-pointer disabled:opacity-50"
              />
            </div>

            {photoError && (
              <div
                role="alert"
                className="p-2.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs"
              >
                {photoError}
              </div>
            )}

            {selectedPhotos.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                {selectedPhotos.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border border-[#E8DCCF] bg-white overflow-hidden flex flex-col"
                  >
                    <div className="aspect-[4/3] bg-[#F7EFE6]/60 flex items-center justify-center overflow-hidden">
                      {item.previewUrl ? (
                        <img
                          src={item.previewUrl}
                          alt={item.name}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <span className="text-[11px] text-[#292039]/60">Image selected</span>
                      )}
                    </div>
                    <div className="p-2 flex items-center justify-between gap-2 text-[11px] border-t border-[#F0E4D4]">
                      <div className="min-w-0">
                        <p className="font-semibold text-[#292039] truncate" title={item.name}>
                          {item.name}
                        </p>
                        <p className="text-[10px] text-[#292039]/60 font-mono">
                          {formatFileSize(item.size)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemovePhoto(item.id)}
                        aria-label={`Remove ${item.name}`}
                        className="px-2 py-1 rounded-lg bg-rose-50 text-rose-700 hover:bg-rose-100 font-semibold shrink-0 cursor-pointer"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="p-3.5 rounded-2xl bg-[#F7EFE6] border border-[#E8DCCF] text-xs text-[#292039]/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>📅</span>
            <span>
              Submission Date: <strong className="text-[#292039]">{todayStr}</strong>{' '}
              (system-generated)
            </span>
          </div>
          <span className="text-[11px] text-[#368F83] font-semibold">Immediate Dispatch Queue</span>
        </div>

        <div className="pt-2 flex items-center justify-end gap-3">
          <Link
            to="/student/complaints"
            className="px-5 py-2.5 rounded-xl text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6] transition-colors"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={submitting || success}
            className="px-6 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#D94378] hover:bg-[#C23365] disabled:opacity-60 shadow-md shadow-[#D94378]/25 transition-all cursor-pointer"
          >
            {submitting ? 'Submitting Complaint...' : 'Submit Maintenance Complaint'}
          </button>
        </div>
      </form>
    </div>
  )
}
