# Investigation: ABV, Net Contents, and the public registry

> **TL;DR (corrected 2026-06-15)** — Alcohol Content and Net Contents **ARE
> retrievable from the public COLA Registry** — they render as **form boxes 12 and
> 13 on the printable form**, but **only on the older TTB F 5100.31 template**.
> Newer e-filed forms renumber those boxes away and omit ABV/net from the public
> view, so coverage is uneven by filing era and product type. An earlier draft of
> this note concluded "the public registry never publishes them" — that was wrong;
> it was based on a small sample that happened to be *newer-form* records. We now
> **harvest records that actually carry the data** (see
> `../targetsetup/scripts/cola_harvest.py`) and **simulate ABV/net only as a
> fallback** for a record whose form omits them. Grape varietal, wine vintage, and
> country of origin are also published (on the *detail* page).

## The question

When building field-match checks, we compare each **application value** (what the
applicant filed) against the **on-label value** (what OCR reads from the image).
This works cleanly for Brand Name, Class/Type, Origin, and Applicant. For **Alcohol
Content (ABV)** and **Net Contents**, the first records we scraped had no such
field — so we asked:

1. Does COLA Online even capture ABV / Net Contents?
2. If so, are they exposed anywhere in the **public** registry we can read?

## What we found

### 1. COLA Online *does* capture them (at filing time)

The COLA Online Industry Member User Manual (`ref-docs/colas_ol_oim_um.pdf`,
"Create Application — Step 2 of 3: COLA Information", p.55–58) shows both fields
as explicit applicant inputs:

- **Net Contents** — a drop-down ("Select Net Contents" → *Add Net Contents*).
- **Alcohol Content** — a numeric field (0.00 – 100.00).

### 2. The **public** registry exposes them — on the printable form, older template

There are **two** public views, and **two** form templates:

- **Detail page** (`viewColaDetails.do?action=publicDisplaySearchBasic`) — clean
  key:value metadata: Status, Vendor Code, Serial, Class/Type Code, **Origin Code
  (country of origin)**, Brand, Fanciful, Type of Application, Total Bottle
  Capacity, **Grape Varietal(s)**, **Wine Vintage**, Formula, Approval Date,
  Qualifications, Applicant (Plant Registry/Permit), Contact, Phone. *(No ABV/net
  here — but it DOES carry grape varietal, wine vintage, and origin, which an
  earlier parser missed because it lacked the `Grape Varietal(s):` / `Wine Vintage:`
  labels and folded them into `Total Bottle Capacity`.)*
- **Printable form** (`viewColaDetails.do?action=publicFormDisplay`) — the official
  TTB F 5100.31 rendering. **This is where ABV/net live — when the older template
  was used:**
  - **Older template** (e.g. ttbid `14313001000020`, SHINE): `… 12. NET CONTENTS
    750 MILLILITERS  13. ALCOHOL CONTENT 75.5  14. WINE APPELLATION  15. WINE
    VINTAGE  16. PHONE …`. **Box 12 = Net Contents, Box 13 = Alcohol Content, with
    real values.**
  - **Newer e-filed template** (e.g. ttbid `23332001000799`, GALLIVANT): renumbers
    to `11. WINE APPELLATION  12. PHONE  13. EMAIL  15. (container boilerplate)` —
    **no Net Contents / Alcohol Content box at all** (zero `ALCOHOL CONTENT`
    occurrences; the only `net contents` hit is Box 15 boilerplate).

So the field's presence depends on **which form template the COLA was filed under**
(roughly: older / paper-style filings carry it; recent e-filings don't). A
**2026-06-15 live probe** across eras found high net+ABV hit rates in, e.g., wine
~2010–2013, spirits ~2014–2017, malt ~2013–2017 — every type has windows where the
data is present.

### 3. Box 15 boilerplate is NOT a net-contents value

On the newer template the only "net contents" text is the instruction:

> *"15. SHOW ANY INFORMATION THAT IS BLOWN, BRANDED, OR EMBOSSED ON THE CONTAINER
> (e.g., net contents) **ONLY IF IT DOES NOT APPEAR ON THE LABELS AFFIXED
> BELOW.**"*

The parser ignores this (it only accepts a `NN. NET CONTENTS <value> NN. ALCOHOL
CONTENT <number>` box pattern), so a newer-form record correctly returns blank
ABV/net rather than a false value.

## How we probed it (reproducible)

Headless Playwright fetches of the public **printable form** for real TTB IDs of
each product type across multiple approval-date eras, HTML stripped to text, then a
search for the `NN. NET CONTENTS … NN. ALCOHOL CONTENT …` box pattern (and for bare
`ALCOHOL CONTENT` / `NET CONTENTS` occurrences). Older-template records returned
real Box 12/13 values; newer-template records returned none. See
`../targetsetup/scripts/cola_harvest.py` (the harvester that encodes this) and the
"How to retrieve" guide next to it.

## Design decision — prefer real data; simulate only as a fallback

| Field | Application value source | Behavior in this POC |
|---|---|---|
| Brand Name | Public registry (detail page) | Field-match vs OCR |
| Fanciful Name | Public registry (detail page) | Field-match vs OCR |
| Class/Type | Public registry (cleaned of TTB code filler) | Field-match vs OCR |
| Grape Varietal | **Public registry (detail page)** | Field-match vs OCR |
| Country of Origin | **Public registry (`Origin Code`)** | Anchors the import check |
| Applicant (name/address) | Public registry (Plant Registry/Permit block) | Field-match vs OCR |
| Government Warning | §16.21 statute (fixed) | Deterministic; no LLM |
| **Alcohol Content** | **Public registry (form Box 13) when present; else simulated** | Field-match vs OCR |
| **Net Contents** | **Public registry (form Box 12) when present; else simulated** | Field-match vs OCR |

### When we still simulate

For a record whose (newer) form omits Box 12/13, the applicant *did* file ABV/net
in COLA Online — the public registry just doesn't surface them. There we **author
those two fields from the actual label** (most to match, a deliberate few off, to
exercise the tool's catch). The label images are the irreplaceable real artifact;
ABV/net are the only application values we ever simulate, and only when the public
form lacks them. In a production deployment wired to TTB's internal filing system,
all of these come straight from the applicant's record and the same checks run
unchanged.
