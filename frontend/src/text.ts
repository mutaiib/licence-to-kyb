/**
 * Map API codes and values to interface text. Every string comes from copy.ts.
 * The template-literal keys make the type checker prove that each API code has a string.
 */
import type { FieldState, FormFieldView, ReasonCode, Route, StepView } from './api/client';
import { copy, format, hasCopy, type CopyKey } from './copy';

export function reasonText(
  code: ReasonCode,
  detail: Readonly<Record<string, string>> = {},
): string {
  const key: CopyKey = `reason.${code}`;
  return format(key, detail);
}

export function errorText(code: string): string {
  const key = `error.${code}`;
  return hasCopy(key) ? copy[key] : copy['error.network'];
}

export function stateText(state: FieldState): string {
  const key: CopyKey = `state.${state}`;
  return copy[key];
}

export function routeLabel(route: Route): string {
  const key: CopyKey = `route.${route}`;
  return copy[key];
}

export function routeDetail(route: Route): string {
  const key: CopyKey = `route.${route}.detail`;
  return copy[key];
}

export function fieldLabel(name: string): string {
  const key = `field.${name}`;
  return hasCopy(key) ? copy[key] : name;
}

export function documentLabel(code: string): string {
  const key = `document.${code}`;
  return hasCopy(key) ? copy[key] : code;
}

/** The backend's step names, mapped to the progress labels in docs/ui-copy.md. */
const STEP_KEYS: Readonly<Record<string, CopyKey>> = {
  intake: 'progress.intake',
  preprocess: 'progress.preprocess',
  route: 'progress.route',
  extract: 'progress.extract',
  validate: 'progress.validate',
  resolve: 'progress.resolve',
  gate: 'progress.gate',
  decide: 'progress.gate',
  form: 'progress.form',
  map_form: 'progress.form',
};

export function stepLabel(name: string): string {
  const key = STEP_KEYS[name];
  return key === undefined ? name : copy[key];
}

const STEP_STATE_KEYS: Readonly<Record<StepView['state'], CopyKey>> = {
  pending: 'progress.status.waiting',
  running: 'progress.status.running',
  done: 'progress.status.done',
  skipped: 'progress.status.skipped',
};

export function stepStateText(state: StepView['state']): string {
  return copy[STEP_STATE_KEYS[state]];
}

function isEmpty(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    value === '' ||
    (Array.isArray(value) && value.length === 0)
  );
}

function scalar(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return null;
}

function describeItem(value: unknown): string {
  const plain = scalar(value);
  if (plain !== null) return plain;
  if (typeof value !== 'object' || value === null) return '';
  const record = value as Record<string, unknown>;
  const name = scalar(record.name);
  if (name !== null) {
    const share = scalar(record.share_pct);
    return share === null ? name : `${name} (${share}%)`;
  }
  return [record.code, record.description]
    .map(scalar)
    .filter((part): part is string => part !== null && part !== '')
    .join(' ');
}

/** The field value as text, or null when the licence has no value for the field. */
export function valueText(value: unknown): string | null {
  if (isEmpty(value)) return null;
  if (Array.isArray(value)) {
    const parts = value.map(describeItem).filter((part) => part !== '');
    return parts.length === 0 ? null : parts.join('; ');
  }
  const text = describeItem(value);
  return text === '' ? null : text;
}

/**
 * The text to show for a field value. The API's `status` says whether the licence shows the field:
 * a field that is not on the licence, or not readable, shows that status, never an empty value.
 */
export function fieldValueText(field: FormFieldView, name?: string): string {
  if (field.status === 'not_present') return copy['state.not_present'];
  if (field.status === 'unclear') return copy['state.unclear'];
  if (name === 'legal_form' && typeof field.value === 'string') {
    const key = `legalForm.${field.value}`;
    if (key in copy) return copy[key as keyof typeof copy];
  }
  return valueText(field.value) ?? copy['state.not_present'];
}

/** A field needs the reviewer's attention: open it by default. */
export function isFlagged(field: FormFieldView): boolean {
  return (
    field.state === 'flagged' ||
    field.state === 'needs_examination' ||
    field.status !== 'present' ||
    field.rule_results.length > 0
  );
}
