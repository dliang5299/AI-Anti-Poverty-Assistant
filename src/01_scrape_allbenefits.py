# scrape_benefitscal.py
import asyncio, re, json, argparse, datetime, tempfile, os, csv, hashlib
from urllib.parse import urljoin, urlparse
from typing import List, Optional, Dict, Tuple
from pathlib import Path

from pydantic import BaseModel, Field
from dateutil.tz import gettz
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
import httpx
from pdfminer.high_level import extract_text as pdf_extract_text

NY_TZ = gettz("America/New_York")
PDF_RE   = re.compile(r"\.pdf($|\?)", re.I)

# Heuristics for contact extraction & section tagging
PHONE_RE = re.compile(r"(?:\+?1[\s\.-]?)?\(?\d{3}\)?[\s\.-]?\d{3}[\s\.-]?\d{4}")
EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
ELIG_KWS   = ("eligibility", "who qualifies", "who is eligible", "who can get")
BENEFIT_KWS= ("benefits", "what you get", "services covered", "what it provides", "coverage")
APPLY_KWS  = ("apply", "how to apply", "application", "how do i apply", "how to apply")
RENEW_KWS  = ("renew", "renewal", "recertification", "redetermination")
DOC_KWS    = ("documents", "required documents", "verification", "proof", "forms")
CONTACT_KWS= ("contact", "support", "help", "assistance", "office", "customer service")

# ---------- Data models ----------
class ContactInfo(BaseModel):
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []

class ApplicationProcess(BaseModel):
    steps: List[str] = []
    requirements: List[str] = []
    renewal: List[str] = []

class Section(BaseModel):
    section_id: str
    heading: str
    markdown: str
    order: int = 0

class DocRecord(BaseModel):
    doc_id: str
    source_url: str
    page_title: str
    program_name: str
    captured_at: str
    checksum: str
    # semi-structured extras (helpful for UI/filters, not primary truth)
    support_contact: ContactInfo = Field(default_factory=ContactInfo)
    eligibility_text: str = ""
    benefits_text: str = ""
    application_text: str = ""
    renewal_text: str = ""
    # sections for RAG grounding
    sections: List[Section] = []

class ChunkRecord(BaseModel):
    chunk_id: str
    doc_id: str
    section_id: str
    heading: str
    source_url: str
    captured_at: str
    text: str
    char_count: int
    approx_tokens: int

# ---------- Utilities ----------
def now_iso():
    return datetime.datetime.now(tz=NY_TZ).isoformat()

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", "ignore")).hexdigest()

def slugify(s: str, maxlen: int = 50) -> str:
    s = re.sub(r"[^a-zA-Z0-9\-]+", "-", s.lower()).strip("-")
    return s[:maxlen] or "section"

def clean_list(items: List[str]) -> List[str]:
    out, seen = [], set()
    for x in items or []:
        x = re.sub(r"\s+", " ", x).strip(" -*•\u2022\t")
        if not x: continue
        k = x.lower()
        if k not in seen:
            seen.add(k); out.append(x)
    return out

def contains_kw(text: str, kws: tuple) -> bool:
    t = (text or "").lower()
    return any(kw in t for kw in kws)

def estimate_tokens(text: str) -> int:
    # crude but stable: ~4 chars per token
    return max(1, int(len(text) / 4))

def split_markdown_into_chunks(md: str, target_chars: int = 4000, overlap_chars: int = 600) -> List[str]:
    """
    Chunk markdown by paragraphs/lists to ~target_chars, with overlap.
    Keeps list items intact; avoids cutting mid-paragraph when possible.
    """
    if not md:
        return []
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    chunks = []
    cur = []
    cur_len = 0
    for p in paras:
        p_block = p.strip()
        # if a single paragraph is huge, hard-split by lines
        if len(p_block) > target_chars * 1.25:
            lines = p_block.splitlines()
            buf, blen = [], 0
            for ln in lines:
                if blen + len(ln) + 1 > target_chars and buf:
                    chunks.append("\n".join(buf).strip())
                    # overlap from end of buf
                    overlap_text = "\n".join(buf)[-overlap_chars:]
                    buf, blen = ([overlap_text], len(overlap_text))
                buf.append(ln)
                blen += len(ln) + 1
            if buf:
                chunks.append("\n".join(buf).strip())
            continue

        if cur_len + len(p_block) + 2 <= target_chars:
            cur.append(p_block)
            cur_len += len(p_block) + 2
        else:
            if cur:
                chunks.append("\n\n".join(cur).strip())
                # add overlap: take the last 'overlap_chars' of the chunk
                last = chunks[-1]
                overlap = last[-overlap_chars:] if len(last) > overlap_chars else last
                cur, cur_len = ([overlap], len(overlap))
            cur.append(p_block)
            cur_len += len(p_block) + 2
    if cur:
        chunks.append("\n\n".join(cur).strip())
    return [c for c in chunks if c.strip()]

# ---------- Browser helpers ----------
async def maybe_click_banners(page):
    texts = ["Accept", "I agree", "Got it", "OK", "Close", "Continue"]
    for label in texts:
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            await btn.first.click(timeout=700)
        except Exception:
            pass

async def expand_all_accordions(page, debug: bool=False, max_passes: int=3) -> int:
    expanded = 0
    try:
        await page.evaluate("""() => {
          document.querySelectorAll('details:not([open])').forEach(d => d.setAttribute('open',''));
        }""")
    except Exception:
        pass
    toggles = [
        'button[aria-expanded="false"]',
        '[role="button"][aria-expanded="false"]',
        'a[aria-expanded="false"]',
        '.accordion-button.collapsed',
        '.accordion-header button[aria-expanded="false"]',
        '[data-toggle="collapse"]',
        '[data-bs-toggle="collapse"]',
        '.usa-accordion__button[aria-expanded="false"]',
        '.mat-expansion-panel-header[aria-expanded="false"]',
        '.collapsible[aria-expanded="false"]',
    ]
    for _ in range(max_passes):
        changed = 0
        handles = []
        for sel in toggles:
            try:
                handles += await page.query_selector_all(sel)
            except Exception:
                continue
        # de-dupe by location
        seen = set(); uniq = []
        for h in handles:
            try:
                box = await h.bounding_box()
                key = (box['x'] if box else id(h), box['y'] if box else 0)
            except Exception:
                key = id(h)
            if key not in seen:
                seen.add(key); uniq.append(h)
        for el in uniq:
            try:
                await el.scroll_into_view_if_needed()
                panel_id = await el.get_attribute("aria-controls")
                await el.click(timeout=1500)
                try:
                    await page.wait_for_function(
                        """(e) => e.getAttribute('aria-expanded')==='true'""", arg=el, timeout=1500
                    ); changed += 1
                except Exception:
                    if panel_id:
                        try:
                            await page.wait_for_selector(f"#{panel_id}", state="visible", timeout=1500)
                            changed += 1
                        except Exception:
                            pass
                await page.wait_for_timeout(100)
            except Exception:
                continue
        expanded += changed
        if changed == 0:
            break
    if debug:
        try: await page.screenshot(path="debug_after_accordions.png", full_page=True)
        except Exception: pass
    return expanded

async def extract_text_list(el) -> List[str]:
    parts: List[str] = []
    for li in await el.query_selector_all("li"):
        t = (await li.inner_text() or "").strip()
        if t: parts.append(t)
    for p in await el.query_selector_all("p"):
        t = (await p.inner_text() or "").strip()
        if t: parts.append(t)
    for td in await el.query_selector_all("td, th"):
        t = (await td.inner_text() or "").strip()
        if t: parts.append(t)
    if not parts:
        t = (await el.inner_text() or "").strip()
        if t: parts = [t]
    # de-dupe preserve order
    seen = set(); out = []
    for s in parts:
        if s not in seen:
            seen.add(s); out.append(s)
    return out

async def scrape_html_sections(page) -> List[Section]:
    """Return ordered list of Section objects for current page (HTML)."""
    sections: List[Section] = []
    headings = await page.query_selector_all("h1, h2, h3, h4")
    order = 0
    for h in headings:
        title = ((await h.inner_text()) or "").strip()
        if not title:
            continue
        # gather sibling nodes until next heading
        section_nodes = []
        node = h
        while True:
            nxt_handle = await node.evaluate_handle("el => el.nextElementSibling")
            nxt_el = nxt_handle.as_element()
            if not nxt_el: break
            try:
                tag_prop = await nxt_el.get_property("tagName")
                tag = (await tag_prop.json_value() or "").lower()
            except Exception:
                break
            if tag in ("h1","h2","h3","h4"): break
            section_nodes.append(nxt_el)
            node = nxt_el
        texts: List[str] = []
        for n in section_nodes:
            texts.extend(await extract_text_list(n))
        if texts:
            md_lines = [f"- {ln}" if len(ln) <= 240 else ln for ln in clean_list(texts)]
            sec_md = f"## {title}\n\n" + "\n".join(md_lines)
            order += 1
            sections.append(Section(section_id=f"{order:03d}-{slugify(title)}",
                                    heading=title, markdown=sec_md, order=order))
    # Fallback: whole body as one section if no headings yielded content
    if not sections:
        body = await page.query_selector("body")
        if body:
            all_text = (await body.inner_text()) or ""
            lines = [ln.strip() for ln in all_text.splitlines() if ln.strip()]
            if lines:
                md_lines = [f"- {ln}" if len(ln) <= 240 else ln for ln in clean_list(lines)]
                sections.append(Section(section_id="001-page", heading="Page", markdown="## Page\n\n" + "\n".join(md_lines), order=1))
    return sections

# ---------- PDF helper ----------
async def pdf_to_sections(url: str) -> List[Section]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        r = await client.get(url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()
        if "pdf" not in ctype and not PDF_RE.search(url):
            # Not a PDF; return empty → caller will treat it as HTML instead
            return []
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
            tf.write(r.content); tmp_path = tf.name
    try:
        text = pdf_extract_text(tmp_path) or ""
        lines = [ln.strip() for ln in text.splitlines()]
        lines = [ln for ln in lines if ln]
        md_lines = [f"- {ln}" if len(ln) <= 240 else ln for ln in lines]
        sec_md = "## Document\n\n" + "\n".join(md_lines)
        return [Section(section_id="001-document", heading="Document", markdown=sec_md, order=1)]
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass

# ---------- Main page scraper ----------
async def scrape_seed(page, url: str, skip_pdf_seeds: bool, debug: bool=False) -> DocRecord:
    captured_at = now_iso()
    doc_id = sha256_hex(url)
    # If seed is a PDF and not skipped: extract PDF
    if PDF_RE.search(url) and not skip_pdf_seeds:
        sections = await pdf_to_sections(url)
        page_title = url.rsplit("/", 1)[-1] or "PDF"
        program_name = re.sub(r"\.pdf(\?.*)?$", "", page_title, flags=re.I)
    else:
        # HTML path
        await page.goto(url, wait_until="networkidle")
        await maybe_click_banners(page)
        await expand_all_accordions(page, debug=debug)
        if debug:
            try:
                fname = f"debug_{url.split('//')[-1].replace('/','_')}.png"
                await page.screenshot(path=fname, full_page=True)
            except Exception:
                pass
        sections = await scrape_html_sections(page)
        # Titles
        t = await page.title()
        page_title = (t or "").strip() or url
        # Program name → prefer <h1>
        p_h1 = await page.query_selector("h1, h1 *")
        program_name = (await p_h1.inner_text() or "").strip() if p_h1 else page_title
        program_name = re.sub(r"\s*Details$", "", program_name, flags=re.I).strip()

    # Build semi-structured fields from sections
    elig_text = []; bene_text = []; apply_text = []; renew_text = []
    contact = ContactInfo()
    for sec in sections:
        hl = sec.heading.lower()
        md = sec.markdown
        # extract phones/emails
        contact.phones += PHONE_RE.findall(md)
        contact.emails += EMAIL_RE.findall(md)
        # classify section text
        body_text = re.sub(r"^##[^\n]+\n*", "", md).strip()
        if contains_kw(hl, ELIG_KWS):   elig_text.append(body_text)
        if contains_kw(hl, BENEFIT_KWS):bene_text.append(body_text)
        if contains_kw(hl, APPLY_KWS):  apply_text.append(body_text)
        if contains_kw(hl, RENEW_KWS):  renew_text.append(body_text)
        if contains_kw(hl, CONTACT_KWS):
            # keep links that look like support
            pass

    # Page-wide anchors that look like support/apply/renew (HTML only)
    support_urls: List[str] = []
    try:
        if not PDF_RE.search(url):
            for a in await page.query_selector_all("a[href]"):
                href = await a.get_attribute("href")
                if not href: continue
                txt = ((await a.inner_text()) or "").lower()
                if any(k in txt for k in ("contact","office","help","support","apply","renew","find office","forms","download")):
                    support_urls.append(urljoin(url, href))
    except Exception:
        pass

    contact = ContactInfo(
        phones=sorted(set(clean_list(contact.phones))),
        emails=sorted(set(clean_list(contact.emails))),
        urls=list(dict.fromkeys(support_urls))[:20],
    )

    # Compute checksum over concatenated section text
    checksum = sha256_hex("\n\n".join(sec.markdown for sec in sections))

    doc = DocRecord(
        doc_id=doc_id,
        source_url=url,
        page_title=page_title,
        program_name=program_name,
        captured_at=captured_at,
        checksum=checksum,
        support_contact=contact,
        eligibility_text="\n\n".join(elig_text).strip(),
        benefits_text="\n\n".join(bene_text).strip(),
        application_text="\n\n".join(apply_text).strip(),
        renewal_text="\n\n".join(renew_text).strip(),
        sections=sections
    )
    return doc

# ---------- Runner ----------
async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", nargs="+", help="One or more URLs to scrape (HTML/PDF)")
    ap.add_argument("--urls-file", type=str, help="Path to a text file with one URL per line")
    ap.add_argument("--out", required=True, help="Basename for outputs; writes .docs.jsonl, .chunks.jsonl, .csv")
    ap.add_argument("--max", type=int, default=10000, help="Max seeds to process")
    ap.add_argument("--headful", action="store_true", help="Run with a visible browser")
    ap.add_argument("--debug", action="store_true", help="Save screenshots + print extra logs")
    ap.add_argument("--skip-pdf-seeds", action="store_true", help="Ignore PDF seeds (do not parse PDFs)")

    # Chunking knobs (tune if you like)
    ap.add_argument("--chunk-target-chars", type=int, default=4000, help="Approx chars per chunk (~1000 tokens)")
    ap.add_argument("--chunk-overlap-chars", type=int, default=600, help="Overlap chars between consecutive chunks")

    args = ap.parse_args()

    # Resolve outputs
    out_base = Path(args.out)
    if out_base.suffix.lower() in (".jsonl", ".json", ".csv"):
        out_base = out_base.with_suffix("")
    docs_path   = out_base.with_suffix(".docs.jsonl")
    chunks_path = out_base.with_suffix(".chunks.jsonl")
    csv_path    = out_base.with_suffix(".csv")

    # Build seeds
    seeds: List[str] = []
    if args.urls_file:
        with open(args.urls_file, "r", encoding="utf-8") as fh:
            seeds = [ln.strip() for ln in fh if ln.strip() and not ln.strip().startswith("#")]
    elif args.urls:
        seeds = args.urls
    else:
        raise SystemExit("Please provide --urls or --urls-file")

    seeds = seeds[: args.max]

    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/122.0.0.0 Safari/537.36")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=not args.headful,
            args=["--disable-blink-features=AutomationControlled","--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=ua,
            locale="en-US",
            timezone_id="America/Los_Angeles",
            viewport={"width": 1366, "height": 900},
            ignore_https_errors=True,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()

        # writers
        docs_f   = open(docs_path, "w", encoding="utf-8")
        chunks_f = open(chunks_path, "w", encoding="utf-8")

        # CSV accumulator
        csv_rows: List[Dict[str, str]] = []

        def csv_flat(s: Optional[List[str] or str]) -> str:
            if s is None: return ""
            if isinstance(s, list): return " | ".join(s)
            return str(s)

        processed = 0
        for i, url in enumerate(seeds, 1):
            try:
                doc = await scrape_seed(page, url, skip_pdf_seeds=args.skip_pdf_seeds, debug=args.debug)

                # Write DOC row
                docs_f.write(json.dumps(doc.model_dump(), ensure_ascii=False) + "\n")

                # Make CHUNKS (per section)
                for sec in doc.sections:
                    md = sec.markdown or ""
                    # Remove heading line from chunk body (keep heading in metadata)
                    body_md = re.sub(r"^##[^\n]+\n*", "", md).strip()
                    # If empty, use original
                    if not body_md: body_md = md
                    pieces = split_markdown_into_chunks(body_md,
                                                       target_chars=args.chunk_target_chars,
                                                       overlap_chars=args.chunk_overlap_chars)
                    for idx, piece in enumerate(pieces, 1):
                        chunk_id = f"{doc.doc_id}:{sec.section_id}:{idx:03d}"
                        rec = ChunkRecord(
                            chunk_id=chunk_id,
                            doc_id=doc.doc_id,
                            section_id=sec.section_id,
                            heading=sec.heading,
                            source_url=doc.source_url,
                            captured_at=doc.captured_at,
                            text=piece,
                            char_count=len(piece),
                            approx_tokens=estimate_tokens(piece),
                        )
                        chunks_f.write(json.dumps(rec.model_dump(), ensure_ascii=False) + "\n")

                # CSV preview row
                csv_rows.append({
                    "program_name": doc.program_name,
                    "page_title": doc.page_title,
                    "source_url": doc.source_url,
                    "captured_at": doc.captured_at,
                    "checksum": doc.checksum,
                    "sections_count": str(len(doc.sections)),
                    "phones": csv_flat(doc.support_contact.phones),
                    "emails": csv_flat(doc.support_contact.emails),
                    "support_urls": csv_flat(doc.support_contact.urls[:10]),
                    "eligibility_excerpt": (doc.eligibility_text[:300] + "…") if len(doc.eligibility_text) > 300 else doc.eligibility_text,
                    "apply_excerpt": (doc.application_text[:300] + "…") if len(doc.application_text) > 300 else doc.application_text,
                })

                processed += 1
                print(f"[{i}/{len(seeds)}] OK  {doc.program_name}  ({len(doc.sections)} sections)")
                await asyncio.sleep(0.4)

            except Exception as e:
                print(f"[{i}] ERROR {url}: {e}")

        docs_f.close(); chunks_f.close()

        # Write CSV
        if csv_rows:
            fieldnames = ["program_name","page_title","source_url","captured_at","checksum",
                          "sections_count","phones","emails","support_urls",
                          "eligibility_excerpt","apply_excerpt"]
            with open(csv_path, "w", encoding="utf-8", newline="") as cf:
                w = csv.DictWriter(cf, fieldnames=fieldnames)
                w.writeheader()
                for r in csv_rows:
                    w.writerow(r)

        await browser.close()

        print(f"\nWrote:\n  - {docs_path}\n  - {chunks_path}\n  - {csv_path}\nProcessed {processed} pages.")

if __name__ == "__main__":
    asyncio.run(main())