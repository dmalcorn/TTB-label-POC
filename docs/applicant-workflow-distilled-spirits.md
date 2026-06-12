# Applicant Workflow — Distilled Spirits in COLAs Online

*How an industry member (the **applicant**) submits a distilled-spirits label
application in **COLAs Online**, end to end. This documents the **submitter side**
of the COLA process — the system that produces the data the Label Specialist POC later
reads and reviews. It is **not** the Label Specialist workflow.*

**Primary source:** the COLAs Online Industry Member User Manual
([`../ref-docs/colas_ol_oim_um.pdf`](../ref-docs/colas_ol_oim_um.pdf), v3.11.3,
dated 2015-06-11). Section numbers below (e.g. *§3.6.1.3*) refer to that manual.
Supporting detail on Form 5100.31 fields and image mechanics comes from
[`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) (§5, §6).

**Related docs:**
- [`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
  — the CFR rules a Label Specialist checks the submitted fields and label artwork against.
- [`database-schema.md`](./database-schema.md) — the mock COLA schema
  where every field and image described below lands as Label Specialist input.

> **Sourcing rule for this doc:** every step is grounded in the user manual. Where
> a detail is shown only in a figure/screenshot (not in the manual's body text) or
> is not in the manual at all, it is marked **TODO** rather than invented.

---

## 0. Where this fits

COLAs Online is the authenticated, web-based system where an industry member files
an **eApplication** — TTB's electronic equivalent of paper **Form 5100.31**
("Application for and Certification/Exemption of Label/Bottle Approval", OMB
1513-0020). Submitting creates a **database record** that is assigned a **TTB ID**
and can be rendered/printed as a populated Form 5100.31 at any time; the record and
the form are two views of the same submission (Research-Findings §5).

The applicant supplies three things that flow downstream to the reviewer: the
**application field data**, the **label images**, and an **electronic
perjury-certification signature** (discussion-points §15). The Label Specialist POC
consumes exactly these.

---

## 1. Account, Registration & Permit Context (brief)

Before filing, the applicant must be a registered, authenticated COLAs Online user
(*§1.2*, *§3.3*). Key points from the manual:

- **Authenticated system.** COLAs Online requires a username and password to submit
  applications, search, or change profile information (*§1.2*).
- **Registration.** New users register at `https://www.ttbonline.gov/` →
  **Register for TTB Online** → complete the multi-tab **User Registration**
  (Main, Company, Docs/Links, Comments), agree to a perjury statement, and submit;
  TTB then issues a **user ID** the applicant activates by setting a password
  (*§3.3.1–§3.3.3*). After one year of inactivity the user ID is deleted (*§3.3.3*).
- **Two external user roles** (*§1.2*):
  - **External User** — the registered industry member who can **submit**, withdraw,
    and surrender applications and view their status.
  - **External Preparer/Reviewer User** — can **create/save** an application but
    **cannot submit, withdraw, or surrender** it; an External User submits it later.
- **Permit context.** Registration ties the user to one or more company permits. In
  the application itself, the filer picks the governing
  **Plant Registry / Basic Permit / Brewer's No.** (*§3.6.1.3*). This permit is the
  legal identity under which the COLA is requested.

> **TODO:** The manual does not state a Pay.gov or login.gov dependency, nor the
> exact registration approval SLA. Treat external-identity/SSO details as out of
> scope for this POC unless TTB confirms otherwise.

---

## 2. Starting an Application & Entering the Form 5100.31 Fields

From **Home: My eApplications** (the user's home page, listing their 300 most recent
e-filed applications, *§3.5*), the applicant selects **Create an eApplication**
(*§3.6.1*). The create flow is a guided **3-step wizard** preceded by an
acknowledgement gate.

### 2.0 Allowable-Changes Acknowledgement (gate) — *§3.6.1.1*

The applicant must confirm they have read the **list of allowable label revisions**
(checkbox: *"Yes, I have read the list of allowable revisions"*) before proceeding.
This helps them decide whether to **update an existing COLA** or **file a new
application**, then selects **Continue**.

### 2.1 Step 1 of 3 — Application Type — *§3.6.1.2*

All fields in Step 1 are **required**. The applicant selects:

1. **Type of Product** — Wine, Domestic SAKE Application, **Distilled Spirit**, or
   Malt Beverage. → *For this workflow, the applicant selects **Distilled Spirit**.*
   This single choice is what makes the submission "distilled spirits" and drives the
   type-specific fields and rules downstream.
2. **Source of Product** — **Domestic** or **Imported** (was the finished beverage
   produced in the US or internationally).
3. **Type of Application** — **Certificate of Label Approval** (default) or
   **Certificate of Exemption from Label Approval**. (Exemption requires choosing the
   state of sale; an imported COLA disables the state list.)
4. **Resubmission?** — If this re-files a previously **rejected** application, select
   **Yes** and pick/enter the prior **TTB ID** (electronic or paper, rejected within
   the last two years). Default is **No**.

Select **Next** → Step 2.

### 2.2 Step 2 of 3 — COLA Information — *§3.6.1.3*

This is the heart of the Form 5100.31 data entry. For **Distilled Spirit**, an extra
**Distinctive Liquor Bottle Approval** block appears at the top (*§3.6.1.3 step 2*):
if the bottle itself is distinctive, select **Yes** and enter the **Total Bottle
Capacity before closure**.

The applicant then enters (manual step numbers in parentheses):

| Field | Notes from manual (*§3.6.1.3*) |
|---|---|
| **Serial Number** (3) | Applicant-assigned serial number for the application. |
| **Plant Registry / Basic Permit / Brewer's No.** (4) | Choose the governing permit and **Add Permit**; multiple permits may be added (except wineries). If only one valid permit exists, it is pre-selected. |
| **DBA / Trade Name** (5) | Only if used on the label; must match the label and be pre-approved/registered with the TTB NRC. |
| **Brand Name** (6) | Required. The brand under which the product is marketed. |
| **Fanciful Name** (7) | If applicable. |
| **TTB Formula ID** (8) | Optional; select an approved formula tied to the chosen permit. |
| **Net Contents** (9) | Selected from a drop-down and added via **Add Net Contents**; repeat to add multiple container sizes for the same label. |
| **Alcohol Content** (10) | Free text **or** a numeric value; if numeric, must be **0.00–100.00**. |
| **Notes to Specialist** (14) | Optional free text to the reviewing specialist, up to **2000 characters** (cumulative across correction rounds). |

> **Wine-only fields** — **Wine Vintage** (11), **Grape Varietal(s)** (12), and
> **Wine Appellation** (13) appear *only* for Wine applications and are **not shown
> for Distilled Spirit** (*§3.6.1.3* notes). They are listed here only to explain why
> a distilled-spirits record omits them.

**Important applicant guidance the manual calls out** (*§3.6.1.3* note after step 7):
do **not** put a **Product Class/Type** or appellation into the Brand Name or Fanciful
Name field — each has its **own** field, and conflating them gets the application
**returned for correction**. Per the official COLAs Online field glossary
(`../ref-docs/Definition of Terms.txt`, "Product Class/Type"), the applicant **enters the
class/type as a code** (typed or via lookup) — so it **is** a maker-entered application
field the reviewer can diff against the label.

> **Note for the regulatory mapping:** the *class/type designation* **is** captured as a
> Step-2 field (the Product Class/Type code) → it diffs application ↔ OCR. The *Government
> Warning* is **not** a typed field — the applicant attests to the label artwork — so it is
> verified by OCR against the **fixed 27 CFR §16.21 text** (deterministic; the regulation is
> the ground truth), per
> [`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md).
> **Name & address** as it appears on the label derives from the permit identity, not a
> free-text Step-2 field.

Select **Next** → Step 3.

### 2.3 Step 3 of 3 — Upload Labels — *§3.6.1.4*

1. Optionally enter a **translation** of any foreign text / special wording or
   designs appearing on materials affixed to the container (label, bottle, cork,
   etc.).
2. **add/remove Images** → opens the label-image upload page (see §3 below).
3. **add/remove Attachments** → opens "Upload Other Attachments" for supporting docs
   (formulas, SOPs, lab analyses, pre-import/cover letters; DOC/TXT/PDF/JPG/TIFF,
   ≤750 KB, up to 10 — *§3.6.2.2*).

Select **Next** → Verify Application (§4 below).

---

## 3. Uploading Label Images — *§3.6.2.1*

From Step 3, **add/remove Images** opens the **Upload Label Images** page. The
applicant may attach **up to ten files**. Per the manual, the upload loop is:

1. **Browse** to select a file. *(File-picker only — there is no drag-and-drop in
   the current system; Research-Findings §6.)*
2. Confirm each file meets the required specs (manual note under step 2):
   - **File type JPG or TIFF only** — extensions `.jpg` / `.jpeg` / `.jpe` or
     `.tif` / `.tiff`.
   - **≤ 750 KB** each.
   - **Compression/quality ratio = Medium** (7/10 or 70/100).
   - **RGB color mode**, not CMYK.
   - **No surrounding white space or printer's-proof detail** — must be cropped out.
   - *(TIFFs should not be saved with JPG compression.)*
3. **Select the attachment type** from the drop-down — i.e., tag **which label this
   is**: *brand, neck, back,* etc. (manual: *"tell us which label this is (brand,
   neck, back, etc.)"*).
4. **One label per image** (manual note): include only a single label per file.
5. Enter the **label image height and width** — the dimensions of the *image*, not
   the physical label, in `NN.NN` numeric format. *(These dimensions are the scale
   reference the POC can later use for any type-size feasibility check —
   Research-Findings §3.)*
6. **Attach file.** Afterward, click the file link to confirm it uploaded cleanly
   and is **clear and readable**; if corrupted/distorted, remove it, re-save with a
   different compression ratio, and re-upload.
7. Repeat for additional files (**up to 10 total, ≤750 KB each**); **Remove** link
   deletes one. Select **Done** to close.

> **Why multiple tagged images matter for review:** mandatory U.S. elements may
> be distributed across front/brand, back, neck, and strip labels, so the reviewer
> must check required elements across the **union** of all uploaded images, not
> demand every element on one (Research-Findings §4). The per-image **type tag** and
> the **1–10 image** model is precisely why
> [`database-schema.md`](./database-schema.md) carries a label-image set (with type
> and dimensions per image) rather than a single filename.

> **TODO:** The manual does not state whether **PNG** is accepted (it is **not** in
> the documented JPG/TIFF list). The POC mirrors the documented JPG/TIFF baseline;
> any PNG support would be an explicit POC enhancement, to be noted in
> tradeoffs/limitations.

---

## 4. Verify Application & Electronic Perjury Certification — *§3.6.3*

The **Verify Application** page lets the applicant review and edit everything before
sending it to TTB. Steps (*§3.6.3*):

1. **edit step 1 / edit step 2 / edit step 3** buttons jump back to revise any
   section before submitting. *(In "Needs Correction" mode, specific edit buttons may
   be disabled depending on what TTB allows the applicant to change.)*
2. **View images / attachments** via their links to confirm content.
3. **Verify Uploaded Images** link — the applicant must confirm each image against
   the dimensions specified. **Submission is blocked unless this is clicked**
   (manual: *"You will not be allowed to submit the application if you do not select
   the Verify Uploaded Images link."*).
4. **Electronic signature / perjury certification.** The applicant must select the
   **"I agree" checkbox** to concur with the **penalty-of-perjury statement**.
   **Submission is blocked unless "I agree" is checked** (manual: *"You will not be
   allowed to submit the application if you do not select the 'I agree' checkbox."*).
   This checkbox is the **electronic signature** that certifies the application's
   truthfulness — the equivalent of the Part II certification on Form 5100.31
   (Research-Findings §5).
5. **Submit application** sends it to TTB (→ §5). **Only an External User can
   submit**; a Preparer/Reviewer can only **Don't submit yet; save for 30 days**
   (the saved application is deleted after 30 days).

> **TODO — exact perjury wording:** the manual displays the perjury statement only in
> a screenshot (Figure 80), so its verbatim text is **not in the manual's body** and
> is **not reproduced here** to avoid inventing it. The authoritative wording is the
> Form 5100.31 Part II certification — see
> [`../ref-docs/f510031.pdf`](../ref-docs/f510031.pdf). Capture the exact string there
> if the POC needs to display it.

---

## 5. Submission → TTB ID + Receipt → Status Lifecycle — *§3.6.4, §3.7, §3.10*

### 5.1 Immediate confirmation & TTB ID — *§3.6.4*

On **Submit**, the **Application Submitted** confirmation page displays. Per the
manual, it includes:

- the **TTB ID** assigned to the application *(the permanent identifier; assigned at
  submission)*,
- the **primary Permit or Registry No.**, and
- the **Serial Number** the applicant assigned.

From here the applicant can start another eApplication or return to **My
eApplications**. The submission now exists as a tracked record searchable by TTB ID,
serial, permit, brand/fanciful name, type, source, and **COLA Status** (*§3.7.1*).

### 5.2 Status lifecycle

The applicant tracks the submission's **status** from My eApplications / Application
Detail (*§3.5*, *§3.7.3*). The manual references these states by name in its workflow
text (a single enumerated table does not appear in the manual body; the statuses
below are the ones named across §3.6–§3.10, reconciled with Research-Findings §7):

| Status | Meaning (per manual usage) | What the applicant can do next |
|---|---|---|
| **Saved not Submitted** | Created/saved but not yet sent; deleted after 30 days (*§3.6.3*). | Edit and submit, or it auto-deletes at 30 days. |
| **Received** | Submitted, awaiting/under TTB review. | May **Withdraw** while Received (*§3.9*). |
| **Assigned** | Assigned to a TTB specialist for processing. | Wait for the determination. |
| **Approved** | COLA issued; printable COLA available (*§3.7.4*). | May later **Surrender** the COLA (*§3.8*). |
| **Needs Correction** | Returned to the applicant to fix specified issues (*§3.10*). | **Make Corrections** within **30 days** or it is **auto-rejected** (*§3.10*). |
| **Rejected** | Terminal denial. | Must file a **new** application; may reference the prior rejected **TTB ID** as a resubmission (*§3.6.1.2*). |

**Needs Correction specifics** (*§3.10*): the **Make Corrections** link appears only
for that status; the applicant must make **all corrections at once** (no save-and-
continue), may be **restricted from editing** certain steps, and re-runs the
Verify-and-submit flow to resend. The **30-day clock** is enforced —
no correction within 30 days → automatic rejection.

> **Cross-reference:** these applicant-visible states map directly to the
> Label Specialist's **dispositions** (Approved / Needs Correction / Rejected) modeled in
> the POC — see Research-Findings §7 and the disposition notes in
> discussion-points §8. The Label Specialist POC reuses these exact state names rather
> than inventing "Pass/Fail".

> **TODO:** *Withdrawn* and *Surrendered* are confirmation outcomes of applicant
> actions (*§3.8*, *§3.9*) rather than review dispositions; include them in the
> schema's status enum only if the POC models post-approval lifecycle.

---

## 6. What This Means for the Label Specialist POC

Everything the applicant supplies above lands in the central COLA database and
becomes the **Label Specialist's input** — the POC reads it; it does not re-capture it
(discussion-points §1, §15).

Concretely, each submitted distilled-spirits application contributes:

- **Application fields** (Form 5100.31 / Step 1–2): TTB ID, serial number, permit,
  product type = Distilled Spirit, source (domestic/imported), application type,
  DBA/trade name, **brand name**, **fanciful name**, **net contents**, **alcohol
  content**, distinctive-bottle data, formula ID, notes to specialist, and the
  application/decision dates.
- **Label image set**: 1–10 images (JPG/TIFF), each **tagged** brand/neck/back/etc.,
  each with **width × height** dimensions — the artifacts OCR/LLM extraction runs
  against and the source for label-only elements (class/type, Government Warning,
  name & address) that have no typed field.
- **Certification & lifecycle metadata**: the perjury "I agree" signature event and
  the **status** (Received → Assigned → Approved / Needs Correction / Rejected).

The Label Specialist then compares the **applicant-entered fields** against the **text
extracted from the label images**, checks the union of labels against the rules in
[`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md),
and records a disposition. The schema that holds all of this is defined in
[`database-schema.md`](./database-schema.md).

A practical consequence the POC should document: **class/type** *is* a captured application
field (the Product Class/Type code) and diffs application ↔ OCR like brand name. The
**Government Warning**, however, is *not* a typed field — it is verified from OCR against the
fixed 27 CFR §16.21 text (the regulation is the ground truth, a deterministic check). That
single asymmetry is a direct product of how this applicant workflow collects data.

---

## Sources

- **COLAs Online Industry Member User Manual v3.11.3** —
  [`../ref-docs/colas_ol_oim_um.pdf`](../ref-docs/colas_ol_oim_um.pdf)
  (§3.3 registration; §3.5 home; §3.6 submit/create/upload/verify/submitted;
  §3.7 view/search/detail; §3.8 surrender; §3.9 withdraw; §3.10 needs correction).
- **Research Findings** —
  [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md)
  (§5 Form 5100.31 + TTB ID + eApplication; §6 image formats/upload mechanics;
  §4 multi-label; §3 type-size scale; §7 dispositions).
- **Discussion Points & Decisions** —
  [`../ref-docs/discussion-points.md`](../ref-docs/discussion-points.md)
  (§15 request for this write-up; §1 POC reads-only scope; §8 dispositions).
- **TTB Form 5100.31** — [`../ref-docs/f510031.pdf`](../ref-docs/f510031.pdf)
  (Part II perjury certification — authoritative for the exact signature wording).
