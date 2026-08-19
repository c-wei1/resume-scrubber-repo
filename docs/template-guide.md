# Template Form Guide

How to use, update, or replace the company CV template that the "Use Template" workflow populates.

## Template Requirements

| Requirement | Value |
|-------------|-------|
| **Filename Pattern** | `FRM-*-CV Template.docx` |
| **Location** | `backend/` directory (same level as `app.py`) |
| **Format** | `.docx` (Office Open XML). `.doc`, `.pdf`, and other formats are **not** supported. |

The template file is resolved by glob match in `backend/app.py`:

```python
TEMPLATE_GLOB = "FRM-*-CV Template.docx"
template_matches = sorted(Path(__file__).resolve().parent.glob(TEMPLATE_GLOB))
```

For `/populate-template` to succeed, there must be exactly one matching template file:

- If zero files match, the endpoint returns `500`.
- If multiple files match, the endpoint returns `500` and lists the matching filenames.

## Updating the Template Form

Use this process when replacing the company CV template file.

1. Put the new `.docx` in `backend/`.
2. Name it so it matches `FRM-*-CV Template.docx`.
3. Ensure no second template file also matches this pattern.
4. Confirm required placeholder tags still exist (see section below).
5. Test with one resume via `POST /populate-template`.

Recommended verification command:

```bash
ls backend/FRM-*-CV\ Template.docx
```

This command should print exactly one file.

## Placeholder Tags

The template must contain the following plain-text placeholder tags. During population the backend finds each tag in the document XML and replaces it with the corresponding content.

| Placeholder | Replaced With | Populated By |
|-------------|--------------|--------------|
| `INSERT_NAME` | Employee name (from form) | `app.py` |
| `INSERT_TITLE` | Job title (from form) | `app.py` |
| `INSERT_DEPARTMENT` | Department (from form) | `app.py` |
| `INSERT_RESPONSIBILITIES` | Current responsibilities (rich text from Quill editor) | `app.py` |
| `INSERT_EXPERIENCES` | Work experience extracted from the source resume | `populate_template.py` |
| `INSERT_EDUCATION` | Education entries extracted from the source resume | `populate_template.py` |
| `INSERT_CERTIFICATES` | Certifications (currently cleared; reserved for future use) | `populate_template.py` |

### Where to place tags in a new template

Type each tag as literal text in the template wherever the corresponding content should appear. For example, place `INSERT_NAME` in the cell or paragraph where the employee's name goes, and `INSERT_EXPERIENCES` where the work history section begins.

> **Tip:** After typing a tag, select it and apply the font/size you want the populated content to inherit — the replacement logic preserves the run formatting of the original tag.

### Word run-splitting

Word frequently splits a single typed string across multiple `<w:r>` (run) elements in the underlying XML. The backend automatically coalesces split runs before searching for placeholders, so the tags will be found even if Word has internally fragmented them.

## Changing the Placeholder Tags

If you need to rename a tag (e.g. change `INSERT_NAME` to `EMPLOYEE_NAME`), update **both** the template file and the corresponding Python source.

### Metadata placeholders (`INSERT_NAME`, `INSERT_TITLE`, `INSERT_DEPARTMENT`, `INSERT_RESPONSIBILITIES`)

These are handled in **`backend/app.py`**.

1. Find the coalesce list (~line 101):
   ```python
   for ph in ["INSERT_NAME", "INSERT_TITLE", "INSERT_DEPARTMENT",
              "INSERT_RESPONSIBILITIES"]:
       _coalesce_runs_for_placeholder(root, ph)
   ```
2. Update the string in the list.
3. Find the corresponding replacement block below it (~lines 108–120) and update the string literal in the `if` / `.replace()` calls.

### Content placeholders (`INSERT_EDUCATION`, `INSERT_EXPERIENCES`, `INSERT_CERTIFICATES`)

These are handled in **`backend/populate_template.py`** inside the `DocxPopulator` class.

| Placeholder | Where to update |
|-------------|----------------|
| `INSERT_EDUCATION` | `populate_template_files()` method — appears in the coalesce loop (~line 202) and in the `_replace_placeholder_with_xml` / `_replace_placeholder_text` calls (~lines 209, 216). |
| `INSERT_CERTIFICATES` | Same coalesce loop (~line 202) and `_replace_placeholder_text` call (~line 219). |
| `INSERT_EXPERIENCES` | Class constant `_EXPERIENCE_PLACEHOLDERS` (~line 368). All experience replacement logic references this list. |

### Checklist for renaming a tag

1. Update the tag text inside the active template file in `backend/`.
2. Update the matching string literal(s) in the Python source file(s) listed above.
3. Rebuild the frontend (`cd frontend && npm run build`) if the static assets are served from `backend/static/`.
4. Run the test suite to verify nothing broke: `pytest tests/`.
