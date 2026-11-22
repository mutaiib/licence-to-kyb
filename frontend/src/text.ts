/**
 * Map API codes and values to interface text. Every string comes from copy.ts.
 * The template-literal keys make the type checker prove that each API code has a string.
 */
import type {
  FieldState,
  FormActivity,
  FormFieldView,
  FormPerson,
  ReasonCode,
  Route,
  StepView,
} from './api/client';
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

/**
 * The backend's step names, mapped to the progress labels in docs/ui-copy.md. The backend sends
 * preprocess, route, extract, validate, map_form and decide today. The other names are used from
 * later user stories: resolve (User Story 4) and gate (User Story 3). No backend step is called
 * intake or form yet.
 */
const STEP_KEYS: Readonly<Record<string, CopyKey>> = {
  intake: 'progress.intake',
  preprocess: 'progress.preprocess',
  route: 'progress.route',
  extract: 'progress.extract',
  validate: 'progress.validate',
  confidence: 'progress.confidence',
  resolve: 'progress.resolve',
  gate: 'progress.gate',
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

/** A person as "Name (60%)", or just the name when the licence prints no share. */
function personText(person: FormPerson): string {
  if (person.name === '') return '';
  if (person.share_pct === undefined || person.share_pct === null) return person.name;
  return `${person.name} (${String(person.share_pct)}%)`;
}

/** An activity as "code description", leaving out the parts that are missing. */
function activityText(activity: FormActivity): string {
  const parts: string[] = [];
  if (activity.code !== null && activity.code !== '') parts.push(activity.code);
  if (activity.description !== null && activity.description !== '') {
    parts.push(activity.description);
  }
  return parts.join(' ');
}

function itemText(item: FormPerson | FormActivity): string {
  return 'name' in item ? personText(item) : activityText(item);
}

/** The field value as text, or null when the licence has no value for the field. */
export function valueText(value: FormFieldView['value']): string | null {
  if (value === null || value === '') return null;
  if (typeof value === 'string') return value;
  const items: (FormPerson | FormActivity)[] = value;
  const parts = items.map(itemText).filter((part) => part !== '');
  return parts.length === 0 ? null : parts.join('; ');
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
    if (hasCopy(key)) return copy[key];
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

/** A flagged field that has no decision yet. The form cannot be approved while one remains. */
export function isUndecided(field: FormFieldView): boolean {
  return field.state === 'flagged' || field.state === 'needs_examination';
}
