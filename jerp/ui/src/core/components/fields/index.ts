import { fieldRegistry } from './registry';
import { StringField } from './StringField';
import { TextField } from './TextField';
import { IntegerField } from './IntegerField';
import { FloatField } from './FloatField';
import { BooleanField } from './BooleanField';
import { DateField } from './DateField';
import { SelectionField } from './SelectionField';
import { Many2oneField } from './Many2oneField';
import { FileField } from './FileField';
import { ImageField } from './ImageField';
import { PasswordField } from './PasswordField';

/** Register the built-in field widgets, keyed by the ORM ``ttype``. */
export function registerBuiltinFields(): void {
  fieldRegistry.register('char', StringField);
  fieldRegistry.register('text', TextField);
  fieldRegistry.register('integer', IntegerField);
  fieldRegistry.register('bigint', IntegerField);
  fieldRegistry.register('numeric', FloatField);
  fieldRegistry.register('double', FloatField);
  fieldRegistry.register('boolean', BooleanField);
  fieldRegistry.register('date', DateField);
  fieldRegistry.register('selection', SelectionField);
  fieldRegistry.register('many2one', Many2oneField);
  fieldRegistry.register('file', FileField);
  fieldRegistry.register('image', ImageField);
  fieldRegistry.register('password', PasswordField);
}

export { fieldRegistry } from './registry';
export type { FieldProps, FieldComponent } from './registry';
export { FileField } from './FileField';
export { ImageField } from './ImageField';
export { PasswordField } from './PasswordField';
export { FloatField } from './FloatField';
export { DateField } from './DateField';
export { TextField } from './TextField';
export { Many2oneField } from './Many2oneField';
