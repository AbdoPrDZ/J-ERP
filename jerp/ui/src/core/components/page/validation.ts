import type { FieldDescriptor } from '../../types';

export type FormErrors = Record<string, string>;

const INTEGER_TYPES = new Set(['integer', 'bigint', 'many2one', 'file', 'image']);
const NUMBER_TYPES = new Set(['integer', 'bigint', 'many2one', 'file', 'image', 'numeric', 'double']);
const STRING_TYPES = new Set(['char', 'text', 'password', 'selection']);

function isMissing(field: FieldDescriptor, value: unknown): boolean {
  if (value === null || value === undefined) {
    return true;
  }
  if (typeof value === 'string') {
    return value.trim() === '';
  }
  if (
    ['many2one', 'file', 'image'].includes(field.ttype) &&
    Number(value) === 0
  ) {
    return true;
  }
  return false;
}

/** Validate one field value; returns an error message or null. */
export function validateField(
  field: FieldDescriptor,
  value: unknown,
): string | null {
  const label = field.label || field.name;
  if (field.readonly) {
    return null;
  }
  const missing = isMissing(field, value);

  if (field.required && missing && !field.has_default) {
    return `${label} is required.`;
  }
  if (missing) {
    return null;
  }

  if (STRING_TYPES.has(field.ttype) && field.size) {
    if (String(value).length > field.size) {
      return `${label} must be at most ${field.size} characters.`;
    }
  }

  if (INTEGER_TYPES.has(field.ttype) && !Number.isInteger(Number(value))) {
    return `${label} must be a whole number.`;
  }

  if (NUMBER_TYPES.has(field.ttype) && !Number.isFinite(Number(value))) {
    return `${label} must be a number.`;
  }

  if (field.ttype === 'selection' && field.selection?.length) {
    const valid = field.selection.some(
      ([key]) => String(key) === String(value),
    );
    if (!valid) {
      return `${label} has an invalid option.`;
    }
  }

  if (field.ttype === 'date' || field.ttype === 'timestamp') {
    if (Number.isNaN(Date.parse(String(value)))) {
      return `${label} must be a valid date.`;
    }
  }

  if (
    field.ttype === 'char' &&
    /email|e-mail/i.test(field.name) &&
    !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value))
  ) {
    return `${label} must be a valid email address.`;
  }

  return null;
}

/** Validate a list of fields; returns errors keyed by field name. */
export function validateValues(
  entries: Array<{ field: FieldDescriptor; value: unknown }>,
): FormErrors {
  const errors: FormErrors = {};
  for (const entry of entries) {
    const message = validateField(entry.field, entry.value);
    if (message) {
      errors[entry.field.name] = message;
    }
  }
  return errors;
}
