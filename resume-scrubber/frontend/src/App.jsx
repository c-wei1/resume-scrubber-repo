import { useState, useRef, useMemo } from 'react'
import ReactQuill from 'react-quill'
import 'react-quill/dist/quill.snow.css'
import './quill-custom.css'

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#f1f5f9',
    fontFamily: "'Segoe UI', system-ui, sans-serif",
  },
  card: {
    background: '#fff',
    borderRadius: 12,
    padding: '40px 48px',
    width: '100%',
    maxWidth: 480,
    boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
  },
  title: { fontSize: 22, fontWeight: 700, marginBottom: 6, color: '#0f172a' },
  subtitle: { fontSize: 14, color: '#64748b', marginBottom: 32, marginTop: 0 },
  dropzone: (active) => ({
    border: `2px dashed ${active ? '#2563eb' : '#cbd5e1'}`,
    borderRadius: 8,
    padding: '36px 24px',
    textAlign: 'center',
    cursor: 'pointer',
    background: active ? '#eff6ff' : '#f8fafc',
    transition: 'all .15s',
    userSelect: 'none',
  }),
  dropLabel: (active) => ({
    fontSize: 14,
    color: active ? '#2563eb' : '#94a3b8',
    margin: 0,
    fontWeight: active ? 600 : 400,
  }),
  fileName: { fontSize: 14, color: '#16a34a', fontWeight: 600, margin: 0 },
  error: { color: '#dc2626', fontSize: 13, marginTop: 10, marginBottom: 0 },
  button: (disabled) => ({
    marginTop: 20,
    width: '100%',
    padding: '12px 0',
    background: disabled ? '#e2e8f0' : '#2563eb',
    color: disabled ? '#94a3b8' : '#fff',
    border: 'none',
    borderRadius: 7,
    fontSize: 15,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'background .15s',
  }),
  buttonSecondary: (disabled) => ({
    marginTop: 10,
    width: '100%',
    padding: '12px 0',
    background: disabled ? '#e2e8f0' : '#2563eb',
    color: disabled ? '#94a3b8' : '#fff',
    border: 'none',
    borderRadius: 7,
    fontSize: 15,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'background .15s',
  }),
  buttonTertiary: {
    marginTop: 10,
    width: '100%',
    padding: '12px 0',
    background: '#0f172a',
    color: '#fff',
    border: 'none',
    borderRadius: 7,
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background .15s',
  },
  success: {
    marginTop: 14,
    padding: '10px 14px',
    background: '#f0fdf4',
    border: '1px solid #bbf7d0',
    borderRadius: 6,
    fontSize: 13,
    color: '#15803d',
  },
  inputGroup: {
    marginBottom: 12,
  },
  label: {
    display: 'block',
    fontSize: 13,
    fontWeight: 600,
    color: '#374151',
    marginBottom: 4,
  },
  input: {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid #d1d5db',
    borderRadius: 6,
    fontSize: 14,
    boxSizing: 'border-box',
    outline: 'none',
  },
  fieldError: {
    color: '#dc2626',
    fontSize: 12,
    marginTop: 4,
    marginBottom: 0,
    fontWeight: 500,
  },
}

export default function App() {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [populating, setPopulating] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const [donePopulate, setDonePopulate] = useState(false)
  const [emptySections, setEmptySections] = useState([])
  const [name, setName] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [department, setDepartment] = useState('')
  const [responsibilities, setResponsibilities] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [showWarning, setShowWarning] = useState(false)
  const [outputFormat, setOutputFormat] = useState('keep')
  const [downloadedFileName, setDownloadedFileName] = useState('')
  const inputRef = useRef()
  const nameRef = useRef()
  const jobTitleRef = useRef()
  const departmentRef = useRef()
  const responsibilitiesRef = useRef()
  const fileRef = useRef()

  const getPlainTextLength = (html) => {
    const tmp = document.createElement('div')
    tmp.innerHTML = html
    return (tmp.textContent || tmp.innerText || '').trim().length
  }

  const responsibilitiesCharCount = getPlainTextLength(responsibilities)
  const responsibilitiesTooShort = responsibilitiesCharCount > 0 && responsibilitiesCharCount < 150

  const quillModules = useMemo(() => ({
    toolbar: {
      container: [
        [{ 'list': 'ordered' }, { 'list': 'bullet' }],
        [{ 'indent': '-1' }, { 'indent': '+1' }],
        ['bold', 'italic', 'underline'],
        ['clean'],
      ],
    },
  }), [])

  const quillFormats = ['list', 'indent', 'bold', 'italic', 'underline']

  const validateFields = () => {
    const errors = {}
    if (!name.trim()) errors.name = 'Name is required'
    if (!jobTitle.trim()) errors.jobTitle = 'Job Title is required'
    if (!department.trim()) errors.department = 'Department is required'
    if (!responsibilities.trim() || getPlainTextLength(responsibilities) === 0) errors.responsibilities = 'Current Responsibilities at Gilead is required'
    else if (responsibilitiesTooShort) errors.responsibilities = 'Current Responsibilities must be at least 150 characters.'
    if (!file) errors.file = 'Resume file is required'
    return errors
  }

  const scrollToFirstError = (errors) => {
    const fieldOrder = [
      { key: 'name', ref: nameRef },
      { key: 'jobTitle', ref: jobTitleRef },
      { key: 'department', ref: departmentRef },
      { key: 'responsibilities', ref: responsibilitiesRef },
      { key: 'file', ref: fileRef },
    ]
    for (const field of fieldOrder) {
      if (errors[field.key] && field.ref.current) {
        field.ref.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
        break
      }
    }
  }

  const accept = (f) => {
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.docx')) {
      setError('Only .docx files are supported.')
      setFile(null)
      return
    }
    setFile(f)
    setError(null)
    setFieldErrors((prev) => ({ ...prev, file: undefined }))
    setDone(false)
    setDonePopulate(false)
    setEmptySections([])
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    accept(e.dataTransfer.files[0])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errors = validateFields()
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      scrollToFirstError(errors)
      return
    }
    setFieldErrors({})

    if (outputFormat === 'template') {
      handlePopulate()
      return
    }

    setLoading(true)
    setError(null)
    setDone(false)

    const body = new FormData()
    body.append('file', file)
    body.append('name', name)
    body.append('title', jobTitle)
    body.append('department', department)
    body.append('responsibilities', responsibilities)

    try {
      const res = await fetch('/remove-images', { method: 'POST', body })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error || `Server error ${res.status}`)
      }

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const downloadName = `clean_${file.name}`
      const a = document.createElement('a')
      a.href = url
      a.download = downloadName
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setDownloadedFileName(downloadName)
      setDone(true)
      setShowWarning(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handlePopulate = async () => {
    const errors = validateFields()
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      scrollToFirstError(errors)
      return
    }
    setFieldErrors({})

    setPopulating(true)
    setError(null)
    setDonePopulate(false)
    setEmptySections([])

    const body = new FormData()
    body.append('file', file)
    body.append('name', name)
    body.append('title', jobTitle)
    body.append('department', department)
    body.append('responsibilities', responsibilities)

    try {
      const res = await fetch('/populate-template', { method: 'POST', body })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error || `Server error ${res.status}`)
      }

      const emptyHeader = res.headers.get('X-Empty-Sections')
      if (emptyHeader) {
        setEmptySections(emptyHeader.split(',').map(s => s.trim()))
      }

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const downloadName = `populated_${file.name}`
      const a = document.createElement('a')
      a.href = url
      a.download = downloadName
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setDownloadedFileName(downloadName)
      setDonePopulate(true)
      setShowWarning(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setPopulating(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Resume Processor</h1>
        <p style={styles.subtitle}>
          Upload your resume as a .docx file to receive a GVault-ready CV
        </p>

        <form onSubmit={handleSubmit}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 12, marginTop: 0 }}>Step 1: Fill in Your Information</h3>
          <div style={styles.inputGroup} ref={nameRef}>
            <label style={styles.label}>Name <span style={{ color: '#dc2626' }}>*</span></label>
            <input style={{ ...styles.input, ...(fieldErrors.name ? { borderColor: '#dc2626' } : {}) }} value={name} onChange={(e) => { setName(e.target.value); setFieldErrors((prev) => ({ ...prev, name: undefined })) }} placeholder="e.g. John Smith" />
            {fieldErrors.name && <p style={styles.fieldError}>{fieldErrors.name}</p>}
          </div>
          <div style={styles.inputGroup} ref={jobTitleRef}>
            <label style={styles.label}>Job Title <span style={{ color: '#dc2626' }}>*</span></label>
            <input style={{ ...styles.input, ...(fieldErrors.jobTitle ? { borderColor: '#dc2626' } : {}) }} value={jobTitle} onChange={(e) => { setJobTitle(e.target.value); setFieldErrors((prev) => ({ ...prev, jobTitle: undefined })) }} placeholder="e.g. Senior Manager" />
            {fieldErrors.jobTitle && <p style={styles.fieldError}>{fieldErrors.jobTitle}</p>}
          </div>
          <div style={styles.inputGroup} ref={departmentRef}>
            <label style={styles.label}>Department <span style={{ color: '#dc2626' }}>*</span></label>
            <input style={{ ...styles.input, ...(fieldErrors.department ? { borderColor: '#dc2626' } : {}) }} value={department} onChange={(e) => { setDepartment(e.target.value); setFieldErrors((prev) => ({ ...prev, department: undefined })) }} placeholder="e.g. Regulatory Affairs" />
            {fieldErrors.department && <p style={styles.fieldError}>{fieldErrors.department}</p>}
          </div>
          <div style={styles.inputGroup} ref={responsibilitiesRef}>
            <label style={styles.label}>Current Responsibilities at Gilead <span style={{ color: '#dc2626' }}>*</span></label>
            <div style={{ border: fieldErrors.responsibilities ? '1px solid #dc2626' : '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden' }}>
              <ReactQuill
                theme="snow"
                value={responsibilities}
                onChange={(val) => { setResponsibilities(val); setFieldErrors((prev) => ({ ...prev, responsibilities: undefined })) }}
                modules={quillModules}
                formats={quillFormats}
                placeholder={'• Collaborate with cross-functional teams to support project execution and business objectives.\n• Analyze data and processes to identify improvements and recommend solutions.\n• Create documentation, reports, and presentations to support team initiatives and decision-making.'}
                style={{ minHeight: 150 }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginTop: 4 }}>
              <span style={{ fontSize: 11, color: '#94a3b8' }}>
                {responsibilitiesCharCount} characters
              </span>
            </div>
            {fieldErrors.responsibilities && <p style={styles.fieldError}>{fieldErrors.responsibilities}</p>}
            {!fieldErrors.responsibilities && responsibilitiesTooShort && (
              <p style={styles.fieldError}>
                Error: Current Responsibilities should have a minimum of 150 characters.
              </p>
            )}
          </div>

          <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 12, marginTop: 20 }}>Step 2: Upload Your Resume</h3>
          <div ref={fileRef}>
            <div
              style={styles.dropzone(dragging || !!file)}
              onClick={() => inputRef.current.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".docx"
                style={{ display: 'none' }}
                onChange={(e) => accept(e.target.files[0])}
              />
              {file ? (
                <p style={styles.fileName}>&#x2713; {file.name}</p>
              ) : (
                <p style={styles.dropLabel(dragging)}>
                  {dragging ? 'Drop it here' : 'Click or drag & drop a .docx file'}
                </p>
              )}
            </div>
            {fieldErrors.file && <p style={styles.fieldError}>{fieldErrors.file}</p>}
          </div>

          {error && <p style={styles.error}>{error}</p>}

          {(done || donePopulate) && (
            <div style={styles.success}>
              Downloaded as: <strong>{downloadedFileName}</strong>
            </div>
          )}

          {emptySections.length > 0 && (
            <div style={{ marginTop: 10, padding: '10px 14px', background: '#fef9c3', border: '1px solid #fde047', borderRadius: 6, fontSize: 13, color: '#854d0e' }}>
              {emptySections.map(section => (
                <p key={section} style={{ margin: '4px 0' }}>
                  ⚠ No <strong>{section}</strong> section detected — please add a header for <strong>{section}</strong> in the original resume and re-upload, or fill out <strong>{section}</strong> in <strong>{downloadedFileName}</strong> before continuing to <strong>Step 5</strong>.
                </p>
              ))}
            </div>
          )}

          <div style={{ marginTop: 20, marginBottom: 12 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 8, marginTop: 0 }}>Step 3: Select Your Output Format</h3>
            <label style={{ display: 'flex', alignItems: 'center', fontSize: 14, color: '#1e293b', cursor: 'pointer', marginBottom: 6 }}>
              <input type="radio" name="outputFormat" value="keep" checked={outputFormat === 'keep'} onChange={() => setOutputFormat('keep')} style={{ marginRight: 8 }} />
              Keep my resume format
            </label>
            <label style={{ display: 'flex', alignItems: 'center', fontSize: 14, color: '#1e293b', cursor: 'pointer' }}>
              <input type="radio" name="outputFormat" value="template" checked={outputFormat === 'template'} onChange={() => setOutputFormat('template')} style={{ marginRight: 8 }} />
              Use provided CV template
            </label>
          </div>

          <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 12, marginTop: 20 }}>Step 4: Download</h3>
          <button type="submit" disabled={loading || populating} style={styles.button(loading || populating)}>
            {loading || populating ? 'Processing...' : 'Download'}
          </button>
        </form>

        <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 12, marginTop: 20 }}>Step 5: Upload CV to GVault</h3>
        <button
          type="button"
          style={styles.buttonTertiary}
          onClick={() => window.open('https://login.veevavault.com/auth', '_blank')}
        >
          Upload CV
        </button>
      </div>

      {showWarning && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: '32px 36px', maxWidth: 420, width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', marginTop: 0, marginBottom: 12 }}>
              ⚠️ Please Review Your CV
            </h2>
            <p style={{ fontSize: 14, color: '#374151', lineHeight: 1.6, margin: '0 0 8px' }}>
              Before submitting, carefully check the returned CV to ensure no personal data remains, including:
            </p>
            <ul style={{ fontSize: 14, color: '#374151', lineHeight: 1.8, margin: '0 0 20px', paddingLeft: 20 }}>
              <li>Personal email addresses</li>
              <li>Home addresses</li>
              <li>Website links (LinkedIn, personal sites, etc.)</li>
              <li>Phone numbers</li>
            </ul>
            <button
              onClick={() => setShowWarning(false)}
              style={{ width: '100%', padding: '10px 0', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 7, fontSize: 15, fontWeight: 600, cursor: 'pointer' }}
            >
              I understand
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
