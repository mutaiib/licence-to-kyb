# Research notes

These are domain facts about UAE trade licences and KYB onboarding. The schemas, profiles and rules depend on them. Each fact lists how firm it is.

## Licence layout

### Abu Dhabi (ADDED / ADRA)

Firm. Read field by field from a publicly posted licence.

- **Layout:** each row has the English label on the left, the value in the middle and the Arabic label on the right. The title is "Abu Dhabi Economic Licence / رخصة أبوظبي الاقتصادية".
- **Licence number:** `CN-` + 7 digits, for example `CN-1002016`. There is also a separate Unified Licence No., for example `501-1988-100005279`.
- **Dates:** establishment, issue and expiry, in DD/MM/YYYY.
- **Legal form:** English and Arabic, for example "Public Joint-Stock / شركة مساهمة عامة".
- **Trade name:** English and Arabic.
- **Owners and representatives:** name, nationality, role. Shares may be absent.
- **Activities:** a code plus a bilingual description, for example `6419001.1` "Commercial Bank – Local". The codes look ISIC-derived.
- **Other numbers:** the Abu Dhabi Chamber number, and the MOHRE and ICP establishment numbers.
- **Verification:** a QR code, and the text "verify via TAHAQAQ on tamm.abudhabi".

### Dubai mainland (DET)

Moderately firm.

- **Fields:** licence number, main licence number, register number, Dubai Chamber number, and a D-U-N-S number on some licences.
- **People:** a table of members (partners or managers), with name, nationality, role and share.
- **Categories:** commercial, professional, industrial, tourism.
- **Legal forms:** LLC, LLC single owner, sole establishment, civil company, branch.
- **Activity codes:** ISIC-derived and written inconsistently, for example `7490.88` and `8620010`.

### Free zones (DMCC, IFZA, JAFZA and others)

Less firm.

- **Fields:** licence number near the top, company name, legal form (FZE, FZCO / FZ-LLC, branch), activities, shareholders with nationality and share, manager, address, issue and expiry dates (usually annual), and a QR code that links to the authority's register.
- **DMCC numbering:** examples look like `DMCC-30894`.
- **IFZA numbering:** no published number format was found.

**Schema implication:** the licence number, register number and Dubai Unified Licence number are different identifiers. The schema keeps them in separate fields.

## Public verification

| Authority | Service |
|---|---|
| Dubai (mainland and free zones) | **Dubai Unified Licence (DUL).** Each business has a DUL number and a QR code. A cancelled licence still resolves, and shows as cancelled. |
| DET | Licence information e-service. Search by English name, Arabic name or licence number. Returns status, expiry, legal type, activities and address. |
| Abu Dhabi | TAHAQAQ on TAMM. The QR code points to it. |
| DMCC | Public register. |

**Practice:** search by licence number, not by name. The authority's register is the source of truth; the paper copy is only a claim. This project uses a mock registry with the same shape.

## Downstream consumers of a licence

| Consumer | What it uses from the licence | What it requests in addition |
|---|---|---|
| Payment provider (Stripe UAE) | A valid licence issued in the UAE. Every owner of 25% or more is verified. Every manager on the licence is added as a controller. | MOA for an LLC, showing owners and shares. A bank letter less than 6 months old. A power of attorney for a representative not on the licence. |
| Payment provider (Network International) | Licence details | IDs of owners of 25% or more and of controllers, constitutional documents, IBAN proof, VAT certificate. |
| Corporate bank account (Emirates NBD, Wio) | Licence, with activities that match the application | MOA, board resolution if the MOA does not grant banking powers, establishment card, passport, Emirates ID and visa for each shareholder and signatory, and a registered tenancy contract: Ejari in Dubai, Tawtheeq in Abu Dhabi, or a free-zone lease. |
| VAT registration (FTA EmaraTax) | Licence number, issuing authority, issue and expiry dates, legal name, every licence under that name | Scanned licence PDF, up to 15 MB. |

## Validation rules seen in practice

1. **Expiry:** reject an expired licence. Some providers also block onboarding when fewer than 30 days remain.
2. **Cross-document consistency:** the name, owners, shares and managers must agree between the licence and the MOA.
3. **Ownership thresholds:** 25% for most payment providers, 10% for some.
4. **Legal form and signing authority:** the signatory's authority must follow from the legal form, the MOA or a board resolution.
5. **High-risk activities:** general trading (risk of trade-based money laundering), precious metals and stones, virtual assets, and cash-intensive businesses.
6. **Number format by authority:** ADDED `^CN-\d{7}$` is confirmed from examples. The DET and DMCC formats are inferred.
7. **Paper vs. register:** a licence number with no register record, or an expiry date that differs from the register, stops onboarding.

## Data available for testing

- **No public dataset of trade licence images exists.** Test documents are synthetic (see [test cases](../specs/001-licence-to-kyb/test-cases.md)).
- **One real licence is usable:** a listed bank publishes its own Abu Dhabi licence on its website. It is downloaded at eval time and not committed.
- **Related public datasets for key-value extraction:** IBM KVP10k and BuDDIE.

## Sources

- ADCB commercial licence (public PDF): https://www.adcb.com/ar/Images/adcb-commercial-license.pdf
- Dubai Pulse, DET licence dataset: https://www.dubaipulse.gov.ae/data/ded-licenses/ded_license_master-open
- Dubai Unified Licence launch: https://mediaoffice.ae/en/news/2023/December/11-12/Dubai-Department-of-Economy-and-Tourism-launches-Dubai-Unified-Licence
- JAFZA guide to the Dubai Unified Licence: https://www.jafza.ae/resource-centre/guides/the-dubai-unified-license/
- ADDED TAHAQAQ: https://added.gov.ae/Our-Initiatives/Tahaqaq
- DMCC public register: https://dmcc.ae/public-register
- Reading a Dubai free-zone licence: https://dubaisouthbh.com/blogs/read-dubai-free-zone-license-certificate
- Verifying a UAE trade licence: https://www.meydanfz.ae/blog/verify-uae-trade-license
- Stripe UAE business verification: https://support.stripe.com/questions/uae-business-verification-requirements
- Emirates NBD business account FAQ: https://www.emiratesnbd.com/-/media/enbd/files/bub/bb_dao_faqs.pdf
- Wio business account guide: https://arnifi.com/blog/wio-business-account-setup-guide/
- Network International business payments: https://network.ae/en/processing-solutions/business-payments
- Alaan KYB onboarding FAQ: https://help.alaanpay.com/en/articles/13544271-faq-for-kyb-onboarding
- UAE VAT registration: https://tallysolutions.com/mena/uae-vat/apply-for-vat-registration-in-uae/
- CBUAE guidance on trade-based money laundering: https://centralbank.ae/media/50uhfenk/guidance-for-licensed-financial-institutions-on-risks-related-to-trade-based-money-laundering-tbml-and-transshipment-26-november-2025.pdf
- DET activity list: https://virtuzone.com/blog/ded-activity-list/
- IBM KVP10k dataset: https://huggingface.co/datasets/ibm/KVP10k
