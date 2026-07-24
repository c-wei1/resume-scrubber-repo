import { useState, useRef } from 'react'

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
}

export default function App() {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [populating, setPopulating] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const [donePopulate, setDonePopulate] = useState(false)
  const [name, setName] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [department, setDepartment] = useState('')
  const [validationMsg, setValidationMsg] = useState(null)
  const inputRef = useRef()

  const getMissingFields = () => {
    const missing = []
    if (!name.trim()) missing.push('Name')
    if (!jobTitle.trim()) missing.push('Job Title')
    if (!department.trim()) missing.push('Department')
    if (!file) missing.push('Resume file')
    return missing
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
    setDone(false)
    setDonePopulate(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    accept(e.dataTransfer.files[0])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const missing = getMissingFields()
    if (missing.length > 0) {
      setValidationMsg(`Please provide: ${missing.join(', ')}`)
      return
    }
    setValidationMsg(null)

    setLoading(true)
    setError(null)
    setDone(false)

    const body = new FormData()
    body.append('file', file)
    body.append('name', name)
    body.append('title', jobTitle)
    body.append('department', department)

    try {
      const res = await fetch('/remove-images', { method: 'POST', body })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error || `Server error ${res.status}`)
      }

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `scrubbed_${file.name}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handlePopulate = async () => {
    const missing = getMissingFields()
    if (missing.length > 0) {
      setValidationMsg(`Please provide: ${missing.join(', ')}`)
      return
    }
    setValidationMsg(null)

    setPopulating(true)
    setError(null)
    setDonePopulate(false)

    const body = new FormData()
    body.append('file', file)
    body.append('name', name)
    body.append('title', jobTitle)
    body.append('department', department)

    try {
      const res = await fetch('/populate-template', { method: 'POST', body })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error || `Server error ${res.status}`)
      }

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `populated_${file.name}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setDonePopulate(true)
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
          Upload a .docx resume to scrub PII or populate a CV template.
        </p>

        <form onSubmit={handleSubmit}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Name <span style={{ color: '#dc2626' }}>*</span></label>
            <input style={styles.input} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. John Smith" />
          </div>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Job Title <span style={{ color: '#dc2626' }}>*</span></label>
            <input style={styles.input} value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} placeholder="e.g. Senior Manager" />
          </div>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Department <span style={{ color: '#dc2626' }}>*</span></label>
            <input style={styles.input} value={department} onChange={(e) => setDepartment(e.target.value)} placeholder="e.g. Regulatory Affairs" />
          </div>

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

          {error && <p style={styles.error}>{error}</p>}
          {validationMsg && <p style={styles.error}>{validationMsg}</p>}

          {done && (
            <div style={styles.success}>
              Redacted file download started — check your downloads folder.
            </div>
          )}

          {donePopulate && (
            <div style={styles.success}>
              Populated template download started — check your downloads folder.
            </div>
          )}

          <button type="submit" disabled={loading || populating} style={styles.button(loading || populating)}>
            {loading ? 'Redacting...' : 'Redact sensitive information & Download'}
          </button>
        </form>

        <button
          type="button"
          disabled={loading || populating}
          style={styles.buttonSecondary(loading || populating)}
          onClick={handlePopulate}
        >
          {populating ? 'Populating...' : 'Populate Template & Download'}
        </button>

        <button
          type="button"
          style={styles.buttonTertiary}
          onClick={() => window.open('https://login.veevavault.com/auth', '_blank')}
        >
          Upload CV
        </button>
      </div>
    </div>
  )
}
