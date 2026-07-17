import re
from typing import Any, Dict, List, Optional
"""
TRY THIS FOR EDUCATION LOOKUPS
https://ror.readme.io/docs/rest-api
"""
"""TODO: DATES ARE BEING CLASSIFIED AS ENTRY STARTERS -- I DONT WANT DATES TO HAVE ANY PRECEDENCE OVER ANY OTHER SECTION OF THE PARSER"""


# class EducationParser:
#     """Parse the Education section into structured entries."""

#     DEGREE_PATTERNS = [
#         # Full words
#         "bachelor", "master", "doctor", "doctorate", "doctoral",
#         "associate", "diploma", "postgraduate", "undergraduate",
#         # Common abbreviations
#         "phd", "ph.d", "edd", "ed.d", "dba", "d.b.a",
#         "md", "m.d", "do", "d.o", "dds", "d.d.s", "dmd", "d.m.d",
#         "jd", "j.d", "llb", "ll.b", "llm", "ll.m",
#         "mba", "m.b.a", "mpa", "m.p.a", "mph", "m.p.h",
#         "mfa", "m.f.a", "mlis", "msw", "m.s.w",
#         "bs", "b.s", "bsc", "b.sc",
#         "ba", "b.a", "bba", "b.b.a", "bfa", "b.f.a",
#         "beng", "b.eng", "btech", "b.tech",
#         "ms", "m.s", "msc", "m.sc",
#         "ma", "m.a", "med", "m.ed",
#         "meng", "m.eng", "mtech", "m.tech",
#         "mphil", "m.phil", "mres", "m.res",
#         "as", "a.s", "aa", "a.a", "aas", "a.a.s",
#         "major", "minor", "concentration",
#         "honours", "honors", "hons",
#         # Levels
#         "a level", "as level", "gcse", "gcses",
#         "o level", "a-level", "as-level",
#         "ib", "ged", "hnd", "hnc", "btec",
#     ]

#     SCHOOL_PATTERNS = [
#         # English
#         "university", "college", "institute", "school",
#         "academy", "polytechnic", "conservatory",
#         "seminary", "faculty",

#         # French
#         "université", "école", "grande école",

#         # German
#         "universität", "hochschule", "fachhochschule",

#         # Spanish
#         "universidad", "escuela", "instituto",

#         # Portuguese
#         "universidade", "faculdade", "instituto",

#         # Dutch
#         "universiteit", "hogeschool",

#         # Scandinavian
#         "universitet",      # Swedish/Danish/Norwegian
#         "högskola",         # Swedish
#         "høgskole",         # Norwegian
#         "højskole",         # Danish

#         # Italian
#         "università", "politecnico",

#         # Polish
#         "uniwersytet", "politechnika",

#         # Czech / Slovak
#         "univerzita",

#         # Hungarian
#         "egyetem",

#         # Romanian
#         "universitatea",

#         # Finnish
#         "yliopisto",
#         "ammattikorkeakoulu",

#         # Turkish
#         "üniversitesi",
#         "universitesi",

#         # Russian transliterated
#         "universitet",
#         "institut",

#         # Common international brands
#         "technological university",
#         "technical university",
#         "state university",
#         "national university",
#         "medical university",
#         "business school",
#     ]

#     CERT_PATTERNS = [
#         "certification", "certified", "certificate",
#         "license", "credential",
#     ]

#     # Date regex supporting both 2-digit and 4-digit years
#     DATE_STRIP_RE = re.compile(
#         r"\(?\s*"
#         r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s+)?"
#         r"(?:(?:19|20)?\d{2})"
#         r"(?:\s*(?:-|–|—|to)\s*"
#         r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s+)?"
#         r"(?:(?:(?:19|20)?\d{2})|Present|Current|Now|Ongoing))?"
#         r"\s*\)?",
#         re.IGNORECASE,
#     )

#     NEWLINE_TAG_RE = re.compile(r"^\[NEWLINE\]\s*", re.IGNORECASE)

#     # ─────────────────────────────────────────────────────────────
#     # Helpers
#     # ─────────────────────────────────────────────────────────────
#     # New Helpers
#     @staticmethod
#     def _looks_like_complete_entry(block: List[str]) -> bool:

#         f = EducationParser._block_features(block)

#         return (
#             (f["degree"] and f["institution"])
#             or
#             (f["degree"] and f["date"])
#             or
#             (f["institution"] and f["date"])
#         )

#     @staticmethod
#     def _line_score(line: str) -> int:
#         score = 0

#         if EducationParser._is_degree_line(line):
#             score += 1

#         if EducationParser._is_school_line(line):
#             score += 1

#         if EducationParser._extract_year(line):
#             score += 1

#         return score


#     @staticmethod
#     def _block_score(block: List[str]) -> int:
#         features = EducationParser._block_features(block)
#         return sum(features.values())

#     @staticmethod
#     def _block_features(block: List[str]) -> Dict[str, bool]:

#         has_degree = False
#         has_institution = False
#         has_date = False

#         for line in block:

#             if EducationParser._is_degree_line(line):
#                 has_degree = True

#             if EducationParser._is_school_line(line):
#                 has_institution = True

#             if EducationParser._extract_year(line):
#                 has_date = True

#         return {
#             "degree": has_degree,
#             "institution": has_institution,
#             "date": has_date,
#         }

#     # @staticmethod
#     # def _is_valid_education_block(block: List[str]) -> bool:

#     #     features = EducationParser._block_features(block)

#     #     score = sum(features.values())

#     #     return score >= 2

#     @staticmethod
#     def _is_valid_education_block(block: List[str]) -> bool:

#         features = EducationParser._block_features(block)

#         score = 0

#         if features["date"]:
#             score += 2

#         if features["degree"]:
#             score += 1

#         if features["institution"]:
#             score += 1

#         return score >= 2
            
#     @staticmethod
#     def _is_school_line(line: str) -> bool:
#         return EducationParser._contains_any(
#             line,
#             EducationParser.SCHOOL_PATTERNS
#         )

#     @staticmethod
#     def _is_degree_line(line: str) -> bool:
#         return EducationParser._contains_any(
#             line,
#             EducationParser.DEGREE_PATTERNS
#         )

#     @staticmethod
#     def _is_anchor(line: str) -> bool:
#         """
#         Likely start of an education entry.
#         """

#         if EducationParser._is_degree_line(line):
#             return True

#         if EducationParser._is_school_line(line):
#             return True

#         words = line.split()

#         # Exchange programs, fellowships, study abroad, etc.
#         if 1 <= len(words) <= 10:
#             capitalized = sum(
#                 1 for w in words
#                 if w and w[0].isupper()
#             )

#             if capitalized / max(len(words), 1) >= 0.6:
#                 return True

#         return False

#     # @staticmethod
#     # def _build_education_blocks(lines: List[str]) -> List[List[str]]:
#     #     """
#     #     Builds logical education entries.

#     #     Split when:
#     #     1. Existing block already looks like a valid education record
#     #     2. Incoming line itself looks like the start of another record
#     #     """

#     #     blocks = []
#     #     current = []

#     #     for line in lines:

#     #         cleaned = line.strip()

#     #         if not cleaned:
#     #             continue

#     #         if not current:
#     #             current.append(cleaned)
#     #             continue

#     #         current_score = EducationParser._block_score(current)
#     #         incoming_score = EducationParser._line_score(cleaned)

#     #         incoming_degree = EducationParser._is_degree_line(cleaned)
#     #         incoming_school = EducationParser._is_school_line(cleaned)

#     #         should_split = False

#     #         # Existing entry already looks complete
#     #         if current_score >= 2:

#     #             # New line independently looks like another education record
#     #             if incoming_score >= 2:
#     #                 should_split = True

#     #             # Common pattern:
#     #             # Master of Science ...
#     #             # Bachelor of Commerce ...
#     #             elif incoming_degree and incoming_school:
#     #                 should_split = True

#     #             # Degree-start following another degree entry
#     #             elif (
#     #                 incoming_degree
#     #                 and any(
#     #                     EducationParser._is_degree_line(x)
#     #                     for x in current
#     #                 )
#     #             ):
#     #                 should_split = True

#     #         if should_split:
#     #             blocks.append(current)
#     #             current = [cleaned]
#     #         else:
#     #             current.append(cleaned)

#     #     if current:
#     #         blocks.append(current)

#     #     return blocks
#     @staticmethod
#     def _build_education_blocks(lines: List[str]) -> List[List[str]]:
#         """
#         Groups lines into logical education entries.

#         Start a new block when the current block already looks like
#         a complete education record and the incoming line looks like
#         the beginning of another record.
#         """

#         blocks = []
#         current = []

#         for line in lines:

#             cleaned = line.strip()

#             if not cleaned:
#                 continue

#             if not current:
#                 current.append(cleaned)
#                 continue

#             incoming_degree = EducationParser._is_degree_line(cleaned)
#             incoming_school = EducationParser._is_school_line(cleaned)
#             incoming_date = bool(
#                 EducationParser._extract_year(cleaned)
#             )

#             current_features = EducationParser._block_features(current)

#             should_split = False

#             if EducationParser._looks_like_complete_entry(current):

#                 # New degree line after a completed record
#                 if incoming_degree:
#                     should_split = True

#                 # # Institution line after a completed record
#                 # elif (
#                 #     incoming_school
#                 #     and current_features["date"]
#                 # ):
#                 #     should_split = True

#                 # Entire incoming line independently looks like
#                 # a complete education entry.
#                 elif (
#                     (incoming_degree and incoming_school)
#                     or
#                     (incoming_degree and incoming_date)
#                     or
#                     (incoming_school and incoming_date)
#                 ):
#                     should_split = True

#             if should_split:
#                 blocks.append(current)
#                 current = [cleaned]
#             else:
#                 current.append(cleaned)

#         if current:
#             blocks.append(current)

#         return blocks

#     @staticmethod
#     def _parse_school_block(block: List[str]) -> Dict[str, Any]:

#         header_parts = []
#         year = ""

#         for line in block:

#             detected_year = EducationParser._extract_year(line)

#             if detected_year and not year:
#                 year = detected_year

#             cleaned = EducationParser._strip_dates(line)

#             if cleaned:
#                 header_parts.append(cleaned)

#         # remove duplicates while preserving order
#         seen = set()
#         unique_parts = []

#         for part in header_parts:
#             key = part.lower()
#             if key not in seen:
#                 unique_parts.append(part)
#                 seen.add(key)

#         return {
#             "type": "school",
#             "school": {
#                 "institution_header": " | ".join(unique_parts),
#                 "year": year,
#             }
#         }
#     # end of helper block


#     @staticmethod
#     def _strip_dates(value: str) -> str:
#         if not value:
#             return value
#         cleaned = value.replace("\xa0", " ")
#         cleaned = EducationParser.DATE_STRIP_RE.sub("", cleaned)
#         cleaned = re.sub(r"\s{2,}", " ", cleaned)
#         cleaned = cleaned.strip(" \t-–—,|()")
#         return cleaned

#     @staticmethod
#     def _contains_any(line: str, patterns: List[str]) -> bool:
#         line_l = line.lower()
#         for p in patterns:
#             if re.search(rf"\b{re.escape(p.lower())}\b", line_l):
#                 return True
#         return False

#     @staticmethod
#     def _extract_year(line: str) -> str:
#         if not line:
#             return ""
#         m = EducationParser.DATE_STRIP_RE.search(line)
#         if not m:
#             return ""
#         return m.group(0).strip(" \t()[]{}").strip()

#     @staticmethod
#     def _append_unique(existing: str, new_part: str) -> str:
#         """Append new_part to existing with ' | ' separator, avoiding duplicates."""
#         if not existing:
#             return new_part
#         existing_parts = [p.strip() for p in existing.split(" | ") if p.strip()]
#         if any(p.lower() == new_part.lower() for p in existing_parts):
#             return existing
#         return existing + " | " + new_part

#     @staticmethod
#     def _has_content(entry: Dict) -> bool:
#         if entry.get("type") == "school":
#             school = entry.get("school", {})
#             return any(str(v).strip() for v in school.values())
#         if entry.get("type") == "certification":
#             cert = entry.get("certification", {})
#             return any(str(v).strip() for v in cert.values())
#         return False

#     # ─────────────────────────────────────────────────────────────
#     # Main entry point
#     # ─────────────────────────────────────────────────────────────
#     # @staticmethod
#     # def parse(text: str) -> List[Dict[str, Any]]:
#     #     """
#     #     Output schema:

#     #     [
#     #         {
#     #             "type": "school",
#     #             "school": {
#     #                 "institution_header": "University of Birmingham | PhD: Cancer Sciences",
#     #                 "year": "Sept 09 - Sept 13"
#     #             }
#     #         },
#     #         {
#     #             "type": "certification",
#     #             "certification": {
#     #                 "name": "...",
#     #                 "year": ""
#     #             }
#     #         }
#     #     ]
#     #     """
#     #     entries: List[Dict[str, Any]] = []

#     #     lines = [
#     #         line.strip()
#     #         for line in text.split("\n")
#     #         if line.strip()
#     #     ]

#     #     current_school: Optional[Dict[str, Any]] = None
#     #     current_cert: Optional[Dict[str, Any]] = None
#     #     pending_date: Optional[str] = None
#     #     year_confirmed = False  # True when year was set by a date AFTER content

#     #     def finalize_school() -> None:
#     #         nonlocal current_school, year_confirmed
#     #         if current_school and EducationParser._has_content(current_school):
#     #             entries.append(current_school)
#     #         current_school = None
#     #         year_confirmed = False

#     #     def finalize_cert() -> None:
#     #         nonlocal current_cert
#     #         if current_cert and EducationParser._has_content(current_cert):
#     #             entries.append(current_cert)
#     #         current_cert = None

#     #     for line in lines:
#     #         has_degree = EducationParser._contains_any(line, EducationParser.DEGREE_PATTERNS)
#     #         has_school = EducationParser._contains_any(line, EducationParser.SCHOOL_PATTERNS)
#     #         has_cert = EducationParser._contains_any(line, EducationParser.CERT_PATTERNS)
#     #         year = EducationParser._extract_year(line)

#     #         # ── Certification branch ─────────────────────────────
#     #         if has_cert:
#     #             finalize_school()
#     #             pending_date = None
#     #             if current_cert is None:
#     #                 current_cert = {
#     #                     "type": "certification",
#     #                     "certification": {"name": "", "year": ""}
#     #                 }
#     #             if not current_cert["certification"]["name"]:
#     #                 current_cert["certification"]["name"] = line
#     #             if year and not current_cert["certification"]["year"]:
#     #                 current_cert["certification"]["year"] = year
#     #             continue

#     #         # ── Degree and/or school on same line ────────────────
#     #         if has_degree or has_school:
#     #             finalize_cert()

#     #             # Start a new entry when:
#     #             # 1. A new degree keyword and current already has a degree, OR
#     #             # 2. A school-only line and current entry is already complete (has year)
#     #             if has_degree and current_school is not None:
#     #                 existing = current_school["school"]["institution_header"]
#     #                 if EducationParser._contains_any(existing, EducationParser.DEGREE_PATTERNS):
#     #                     finalize_school()
#     #             elif (has_school and not has_degree
#     #                   and current_school is not None
#     #                   and year_confirmed):
#     #                 # School-only line after a fully confirmed entry → new entry
#     #                 finalize_school()

#     #             if current_school is None:
#     #                 current_school = {
#     #                     "type": "school",
#     #                     "school": {"institution_header": "", "year": ""}
#     #                 }
#     #                 # Attach pending date if we had one
#     #                 if pending_date:
#     #                     current_school["school"]["year"] = pending_date
#     #                     pending_date = None

#     #             # Append line to institution_header (strip any dates from it)
#     #             header_text = EducationParser._strip_dates(line)
#     #             if header_text:
#     #                 current_school["school"]["institution_header"] = (
#     #                     EducationParser._append_unique(
#     #                         current_school["school"]["institution_header"],
#     #                         header_text,
#     #                     )
#     #                 )

#     #             if year and not current_school["school"]["year"]:
#     #                 current_school["school"]["year"] = year
#     #             continue

#     #         # ── Date-only or date continuation line ──────────────
#     #         if year:
#     #             if current_school is not None and not current_school["school"]["year"]:
#     #                 # Fill year on current entry (date came after content)
#     #                 current_school["school"]["year"] = year
#     #                 year_confirmed = True
#     #             elif current_school is not None and current_school["school"]["year"]:
#     #                 # Current entry already has a year — this date belongs
#     #                 # to the next entry. Finalize current and store as pending.
#     #                 finalize_school()
#     #                 pending_date = year
#     #             elif current_cert is not None and not current_cert["certification"]["year"]:
#     #                 current_cert["certification"]["year"] = year
#     #             else:
#     #                 # No current entry — store as pending for next entry
#     #                 pending_date = year
#     #             continue

#     #         # ── Continuation: unrecognized short line ────────────
#     #         # Could be a sub-detail (e.g. "A level: 3A's"); skip it
#     #         # since it doesn't contain degree/school/cert keywords.

#     #     finalize_school()
#     #     finalize_cert()
#     #     return entries
#     @staticmethod
#     def parse(text: str) -> List[Dict[str, Any]]:

#         lines = [
#             line.strip()
#             for line in text.split("\n")
#             if line.strip()
#         ]

#         # Stop when we hit a likely non-education subsection.
#         stop_headers = {
#             "current courses",
#             "courses",
#             "training",
#             "professional development",
#         }

#         education_lines = []

#         for line in lines:
#             if line.lower().strip() in stop_headers:
#                 break

#             education_lines.append(line)

#         blocks = EducationParser._build_education_blocks(
#             education_lines
#         )

#         entries = []

#         for block in blocks:
#             joined = " ".join(block).lower()
#             if EducationParser._contains_any(
#                 joined,
#                 EducationParser.CERT_PATTERNS
#             ):
#                 continue
#             if not EducationParser._is_valid_education_block(block):
#                 continue

#             entries.append(
#                 EducationParser._parse_school_block(block)
#             )

#         return entries
