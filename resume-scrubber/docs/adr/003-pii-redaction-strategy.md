# ADR-003: PII Redaction Strategy


## Context

Resumes contain PII that must be removed before documents are uploaded to regulated content management systems (Veeva Vault). PII types include:

- Phone numbers (international formats, extensions, parenthesized area codes)
- Email addresses
- URLs / hyperlinks
- Home addresses (multilingual: English, Germanic, Romance, Scandinavian, etc.)
- Images (profile photos)
- Document metadata (author, last modified by, subject, etc.)

False positives are costly — redacting valid content (e.g., a year "2016" mistaken for a phone fragment) degrades resume quality. False negatives are also costly — leaked PII violates compliance requirements.

## Decision

Use a **multi-stage regex + validation** approach with separate strategies per PII type:

### Phone Numbers
1. First-pass regex captures digit sequences with optional international prefixes (`+XX`), area codes in parentheses, separators (dash, dot, space), and extensions
2. Validation gate: extracted digit count must be 7–15 (per E.164 standard)
3. This prevents "2016" or "Bachelor" from being flagged

### Email Addresses
- Standard regex: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`

### URLs
- Match `http://`, `https://`, `www.`, and bare domain URLs with common TLDs (`.com`, `.org`, `.net`, `.io`, `.dev`, `.me`, `.co`, `.info`, `.biz`)
- Catches URLs like `linkedin.com/in/user` without protocol prefix

### City / State Locations
- Pattern matches `City, ST` format (e.g., "San Francisco, CA", "New York, NY")
- Uses US state codes, Australian state codes, and Canadian province codes
- Redacted as PII spans alongside phone/email/URL

### Addresses (`address_identifier.py`)
Multi-signal scoring system:
1. **Postal codes**: UK (`SW1A 1AA`), Canadian (`K1A 0B1`), US 5-digit/ZIP+4, Dutch (`1234 AB`), generic international
2. **House numbers**: 1–5 digit with optional letter suffix
3. **Street types**: Post-suffixes (English: Street, Avenue; Germanic: strasse, gata), pre-prefixes (Romance: Rue, Via, Calle), fused forms (Titlecase stem + suffix)
4. **Scoring**: Signals combined; line removed if score exceeds threshold

### Images
- Remove `<w:drawing>` and `<w:pict>` OOXML elements
- Preserve text content inside shape/text-box elements

### Hyperlinks
- Unwrap `<w:hyperlink>` elements: blank the display text, remove the link wrapper
- Runs before paragraph-level PII scrubbing

### Metadata
- Clear `author`, `lastModifiedBy`, `subject`, `title`, `keywords`, `description` from `docProps/core.xml` and `docProps/app.xml`

## Consequences

### Positive
- High precision: validation gates prevent common false positives (years, degree numbers)
- Multilingual: address detection covers 10+ language families
- Comprehensive: body text, hyperlinks, images, and metadata all scrubbed
- Non-destructive: text formatting and paragraph structure preserved around redacted spans

### Negative
- Regex-based detection may miss heavily obfuscated formats (e.g., "five five five, one two three four")
- Address detection requires at least one strong signal (postal code or street type); isolated house numbers not detected
- Post-processing user warning is still necessary — the tool cannot guarantee 100% PII removal

### Alternatives Considered
- **Named Entity Recognition for PII**: Higher recall but lower precision for phone/address; introduces ML dependency for a task where regex is sufficient
- **Cloud-based PII APIs** (Google DLP, AWS Comprehend): Adds external dependency, network latency, and data-leaves-premises concerns in regulated environments
- **Manual review only**: Does not scale; humans miss embedded metadata and hyperlinks
