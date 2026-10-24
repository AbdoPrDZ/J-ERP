/**
 * Shared J-ERP UI kit exposed to module view bundles.
 *
 * Module views import this via the ``@jerp/ui`` specifier, which an import map
 * resolves to this module at runtime. React itself is externalized and resolved
 * through the import map to ``react-runtime.js`` (see tools/build-runtime.mjs),
 * so the shell and every module share a single React instance.
 */

export type {
  FieldDescriptor,
  FormSchema,
  ViewProps,
  ActionDescriptor,
  ViewDescriptor,
  RecordType,
  StandardViewProps,
} from './types';

export { App } from './App';
export { t, useLocale } from './i18n';
export type { LocaleLanguage, LocalePayload } from './i18n';
export { useMenu } from './menu';
export type { MenuItem } from './menu';
export { fieldRegistry } from './components/fields/registry';
export { registerBuiltinFields } from './components/fields';
export type { FieldProps, FieldComponent } from './components/fields/registry';
export { viewRegistry, registerBuiltinViews } from './components/views';
export { StandardView } from './components/views';
export {
  Page,
  PageHeader,
  PageContent,
  Breadcrumb,
  Table,
  TableField,
  TableRecordDetails,
  FormTable,
  FormField,
  FormGroup,
  FormTabs,
  FormTab,
  Action,
  ActionHeader,
  ActionContent,
  ActionFooter,
  useAction,
  ActionContext,
  Cards,
  CardField,
  Form,
  RecordContext,
  PageContext,
  usePage,
} from './components/page';
export type {
  PageMeta,
  PageConfig,
  PageProps,
  PageHeaderProps,
  BreadcrumbItem,
  TableProps,
  TableFieldProps,
  TableAction,
  FormTableProps,
  FormProps,
  FormFieldProps,
  FormGroupProps,
  FormTabsProps,
  FormTabProps,
  ActionProps,
  CardsProps,
  CardFieldProps,
} from './components/page';
export { utilsRegistry, registerBuiltinUtils, readJson, formatValue, isLoggedIn, uploadFile, navigateTo } from './utils';
export type { UploadResult } from './utils';
export { api } from './api';
export { model, ModelClient } from './model';
export type { ListParams } from './model';
export { viewsRegistry } from './registry';
export type { ViewModule, ViewLoader } from './registry';
