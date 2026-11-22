/**
 * Every interface string in the app. Components read text from here only.
 *
 * The rules (ASD-STE100) and the full key list are in docs/ui-copy.md. The keys here are the keys in
 * that document. API error codes use the key `error.<code>`, and reason codes use `reason.<code>`.
 * `{name}` marks a value that the app inserts (see `format`).
 * scripts/lint_copy.py checks each value in CI.
 */
export const copy = {
  // App shell
  'app.title': 'Trade licence to KYB',
  'app.loading': 'Loading',
  'nav.upload': 'Upload a licence',

  // Sign-in
  'signin.title': 'Sign in',
  'signin.username.label': 'User name',
  'signin.password.label': 'Password',
  'signin.button': 'Sign in',
  'signout.button': 'Sign out',

  // Upload page
  'upload.title': 'Upload a trade licence',
  'upload.instruction':
    'Upload the trade licence. Use a PDF, JPG or PNG file of 10 MB or less, with 5 pages or less.',
  'upload.file.label': 'Licence file',
  'upload.file.placeholder': 'Choose a file',
  'upload.applicantName.label': 'Business name on the application',
  'upload.button': 'Upload',
  'upload.duplicate': 'You uploaded this file before. Open the existing run.',
  'upload.openRun': 'Open the run',

  // Progress
  'progress.title': 'Progress',
  'progress.intake': 'File check',
  'progress.preprocess': 'Page reading',
  'progress.route': 'Document type',
  'progress.extract': 'Field reading',
  'progress.validate': 'Value checks',
  'progress.resolve': 'Second reading of flagged fields',
  'progress.gate': 'Route',
  'progress.form': 'Draft form',
  'progress.status.waiting': 'Waiting',
  'progress.status.running': 'In progress',
  'progress.status.done': 'Done',
  'progress.status.skipped': 'Skipped',

  // Routes
  'route.ready': 'Ready',
  'route.ready.detail':
    'All fields passed the checks. Examine the form. Approve the form. Submit it.',
  'route.needs_review': 'Needs examination',
  'route.needs_review.detail': 'The system flagged some fields. Examine each flagged field.',
  'route.reject': 'Rejected',
  'route.reject.detail': 'The system cannot continue with this case. The reasons are below.',

  // Field states
  'state.passed': 'Passed',
  'state.flagged': 'Flagged',
  'state.approved': 'Approved',
  'state.corrected': 'Corrected',
  'state.overridden': 'Check overridden',
  'state.needs_examination': 'Needs examination',
  'state.entered_by_reviewer': 'Value from reviewer',
  'state.not_present': 'Not on the licence',
  'state.unclear': 'Not readable',
  'legalForm.llc': 'Limited liability company',
  'legalForm.llc_single_owner': 'Single-owner limited liability company',
  'legalForm.sole_establishment': 'Sole establishment',
  'legalForm.civil_company': 'Civil company',
  'legalForm.branch': 'Branch',
  'legalForm.fze': 'Free zone establishment',
  'legalForm.fzco': 'Free zone company',
  'legalForm.fz_llc': 'Free zone limited liability company',
  'legalForm.public_joint_stock': 'Public joint-stock company',
  'legalForm.private_joint_stock': 'Private joint-stock company',
  'legalForm.other': 'Other legal form',

  // Form fields
  'field.legal_name_en': 'English trade name',
  'field.legal_name_ar': 'Arabic trade name',
  'field.legal_form': 'Legal form',
  'field.licence_number': 'Licence number',
  'field.issuing_authority': 'Issuing authority',
  'field.issue_date': 'Issue date',
  'field.expiry_date': 'Expiry date',
  'field.activities': 'Activities',
  'field.registered_address': 'Registered address',
  'field.beneficial_owners': 'Beneficial owners',
  'field.controllers': 'Controllers',
  'field.chamber_number': 'Chamber of commerce number',

  // Required documents
  'document.memorandum_of_association': 'Memorandum of association',
  'document.identity_document': 'Identity document of each owner',
  'document.tenancy_contract_ejari': 'Tenancy contract (Ejari)',
  'document.tenancy_contract_tawtheeq': 'Tenancy contract (Tawtheeq)',
  'document.free_zone_lease': 'Free zone lease',
  'document.parent_company_registration': 'Registration of the parent company',

  // Review page
  'review.title': 'Examine the form',
  'review.instruction': 'Examine each flagged field. Approve or correct the value.',
  'review.form.title': 'KYB form',
  'review.page.label': 'Licence page {page}',
  'review.reasons.title': 'Reasons',
  'review.evidence.label': 'Text on the licence',
  'review.confidence.label': 'Confidence',
  'review.threshold.label': 'Required confidence',
  'review.rationale.label': 'Model explanation',
  'review.rationale.note': 'The model wrote this text. Compare it with the licence.',
  'review.requiredDocuments.title': 'Documents to request',
  'review.approve': 'Approve',
  'review.approve.field': 'Approve {field}',
  'review.correct.field': 'Correct {field}',
  'review.enterValue.field': 'Enter value for {field}',
  'review.save': 'Save',
  'review.cancel': 'Cancel',
  'review.rejected': 'You rejected this case. Reopen the case to examine the form again.',
  'review.retry.help': 'Processing stopped. Retry processing, or enter each value.',
  'review.correct': 'Correct',
  'review.correct.label': 'New value',
  'review.override': 'Override check',
  'review.override.reason.label': 'Reason for the override',
  'review.override.help': 'You can override a check only when the system could not do the check.',
  'review.reject': 'Reject case',
  'review.reject.reason.label': 'Reason for the rejection',
  'review.reject.confirm': 'Reject this case? The system will not submit the form.',
  'review.reopen': 'Reopen case',
  'review.reopen.reason.label': 'Reason to reopen',
  'review.retry': 'Retry processing',
  'review.enterValue': 'Enter value',
  'review.approveForm': 'Approve form',
  'review.approveForm.disabled': 'Approve or correct each flagged field first.',
  'review.remaining': '{count} flagged fields remain.',
  'review.remaining.one': '1 flagged field remains.',
  'review.ready': 'You approved all fields. Submit the form.',
  'review.submit': 'Submit',
  'review.submitted': 'You submitted the form. The stored record matches the approved form.',
  'review.formChanged': 'The form changed after your approval. Approve the form again.',

  // API error codes
  'error.blocking_rule_failed':
    'This value does not pass a required check. Correct the value or reject the case.',
  'error.not_overridable': 'You cannot override this check. Correct the value or reject the case.',
  'error.undecided_fields':
    'Some flagged fields have no decision. Approve or correct each flagged field.',
  'error.stale_version': 'The form changed. Examine the latest form.',
  'error.reason_required': 'Write a reason.',
  'error.not_approved': 'Approve the form before you submit it.',
  'error.not_awaiting_submit': 'This form is not ready to submit.',
  'error.not_rejected': 'You can reopen only a rejected case.',
  'error.session_expired': 'Your session ended. Sign in again.',
  'error.invalid_credentials': 'The user name or password is incorrect. Try again.',
  'error.forbidden': 'The system stopped this request. Load the page again. Try the action again.',
  'error.rate_limited': 'You tried too many times. Wait 1 minute. Try again after that.',
  'error.not_retryable':
    'Retry is possible only after a processing failure, or when the system used all of the daily reading limit. Examine the fields.',
  'error.not_found': 'The system cannot find this run. Upload the licence again.',
  'error.network': 'The system cannot connect to the server. Try again.',

  // Reason codes
  'reason.invalid_type': 'The system cannot read this file type. Use a PDF, JPG or PNG file.',
  'reason.too_large': 'The file is larger than 10 MB. Use a smaller file.',
  'reason.too_many_pages': 'The file has more than 5 pages. Upload only the licence pages.',
  'reason.image_too_large': 'The image is larger than 50 megapixels. Use a smaller image.',
  'reason.unreadable_file': 'The system cannot open this file. Upload a new copy of the licence.',
  'reason.out_of_scope': 'This document is not a trade licence. Upload the trade licence.',
  'reason.unclear_document': 'The system cannot identify this document. Examine the pages.',
  'reason.unknown_authority': 'The system does not know the issuing authority. Examine all fields.',
  'reason.expired': 'The licence expired on {date}. You cannot submit this form.',
  'reason.expiry_uncertain':
    'The expiry date {date} is before today in only one reading. Examine the expiry date.',
  'reason.near_expiry': 'The licence expires in {days} days. Examine the expiry date.',
  'reason.number_format':
    'The licence number does not match the {authority} format. Examine the value.',
  'reason.date_order': 'The dates are not in the right order. Examine the issue and expiry dates.',
  'reason.shares_total':
    'The owner shares total {total}%. The total must be between 99.5% and 100.5%. Examine the owner shares.',
  'reason.sole_owner_count':
    'A sole establishment must have 1 owner. The licence shows {count}. Examine the owners.',
  'reason.legal_form_not_allowed':
    '{authority} does not issue the legal form {form}. Examine the legal form.',
  'reason.arabic_name_missing':
    'The Arabic trade name is missing. {authority} licences show it. Examine the licence.',
  'reason.high_risk_activity': 'The activity "{activity}" needs more checks. Examine the activity.',
  'reason.evidence_mismatch':
    'The system cannot find this value in the text on the licence. Examine the value.',
  'reason.qr_mismatch':
    'The QR code shows licence number {qr}. The licence shows {value}. Examine the licence number.',
  'reason.registry_not_found':
    'The registry has no record of this licence number. Correct the number or reject the case.',
  'reason.registry_expiry_mismatch':
    'The registry shows expiry date {registry}. The licence shows {value}. Examine the expiry date.',
  'reason.registry_unavailable':
    'The system could not do the registry check. Override the check with a reason, or reject the case.',
  'reason.applicant_name_mismatch':
    'The business name on the application does not match the licence. Examine the trade name.',
  'reason.owners_unclear': 'The system cannot read the owners table. Examine the owners.',
  'reason.ubo_needs_examination':
    'The licence shows no owner shares. Find the beneficial owners in the MOA.',
  'reason.low_confidence': 'The system is not sure of this value. Examine the value.',
  'reason.processing_failed':
    'The system could not read the licence. Retry the processing, or enter the values.',
  'reason.budget_exhausted':
    "The system used all of today's reading limit. Retry the processing tomorrow, or enter the values.",
  'reason.fallback_model': 'A backup model read this licence. Examine all fields.',
  'reason.resolver_budget': 'The second reading stopped at its limit. Examine the flagged fields.',
  'reason.verification_failed':
    'The stored record does not match the approved form. Examine the form. Approve it again. Submit it again.',
  'reason.reviewer_rejected': 'A reviewer rejected this case.',
  'reason.other': 'The system flagged this case. Examine all fields.',

  // Runs and trace pages
  'runs.title': 'Runs',
  'runs.column.date': 'Date',
  'runs.column.business': 'Business name',
  'runs.column.route': 'Route',
  'runs.column.status': 'Status',
  'runs.column.cost': 'Cost',
  'runs.column.duration': 'Duration',
  'runs.summary.title': 'Today',
  'runs.summary.refusals': 'Refusal rate',
  'runs.summary.fallbacks': 'Backup model rate',
  'runs.summary.review': 'Examination rate',
  'runs.summary.cost': 'Cost',
  'runs.summary.budget': 'Remaining daily limit',
  'trace.title': 'Run trace',
  'trace.column.step': 'Step',
  'trace.column.model': 'Model',
  'trace.column.tokens': 'Tokens',
  'trace.column.cache': 'Cached tokens',
  'trace.column.latency': 'Duration',
  'trace.column.cost': 'Cost',
  'trace.masked': 'The system hides personal data on this page.',

  // Glossary tooltips
  'glossary.label': 'Meaning of the abbreviation',
  'glossary.kyb':
    'KYB: Know Your Business. These are the checks a provider does before it approves a business.',
  'glossary.ubo':
    'UBO: ultimate beneficial owner. This is a person who owns 25% or more of the business.',
  'glossary.moa':
    'MOA: memorandum of association. This document shows the owners and their shares.',
  'glossary.qr': 'QR: a printed code that the system reads as text.',
  'glossary.fileTypes':
    'PDF, JPG and PNG: the file types that the system can read. PDF is a document file. JPG and PNG are image files.',
} as const satisfies Record<string, string>;

export type CopyKey = keyof typeof copy;

/** True when `key` names a string in the copy file. */
export function hasCopy(key: string): key is CopyKey {
  return Object.hasOwn(copy, key);
}

/** The string for `key`, with each `{name}` replaced by `values[name]` when it is given. */
export function format(key: CopyKey, values: Readonly<Record<string, string>> = {}): string {
  return copy[key].replace(/\{(\w+)\}/g, (match, name: string) => values[name] ?? match);
}
