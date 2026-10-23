import { fieldRegistry } from './registry';
import { StringField } from './StringField';
import { IntegerField } from './IntegerField';
import { BooleanField } from './BooleanField';
import { SelectionField } from './SelectionField';
import { FileField } from './FileField';
import { ImageField } from './ImageField';
import { PasswordField } from './PasswordField';

/** Register the built-in field widgets, keyed by the ORM ``ttype``. */
export function registerBuiltinFields(): void {
  fieldRegistry.register('char', StringField);
  fieldRegistry.register('text', StringField);
  fieldRegistry.register('integer', IntegerField);
  fieldRegistry.register('bigint', IntegerField);
  fieldRegistry.register('numeric', IntegerField);
  fieldRegistry.register('boolean', BooleanField);
  fieldRegistry.register('selection', SelectionField);
  fieldRegistry.register('file', FileField);
  fieldRegistry.register('image', ImageField);
  fieldRegistry.register('password', PasswordField);
}

export { fieldRegistry } from './registry';
export type { FieldProps, FieldComponent } from './registry';
export { FileField } from './FileField';
export { ImageField } from './ImageField';
export { PasswordField } from './PasswordField';
