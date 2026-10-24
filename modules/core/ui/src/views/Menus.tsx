import {
  Page,
  PageContent,
  Table,
  TableField,
  Form,
  FormField,
  FormGroup,
} from '@jerp/ui';
import { t } from '@jerp/locale';

export default function Menus() {
  return (
    <Page
      name="core.menus"
      title={t('view.core.menus.title')}
      model="sys.menu"
      searchBar
      create
      update
      delete
      views={['list']}
    >
      <PageContent>
        <Table
          model="sys.menu"
          emptyMessage={t('view.core.menus.empty_message')}
        >
          <TableField name="label" />
          <TableField name="parent_id" />
          <TableField name="module" />
          <TableField name="view" />
          <TableField name="sequence" />
          <TableField name="auth" />
        </Table>

        <Form model="sys.menu" title={t('view.core.menus.form_title')}>
          <FormGroup label={t('view.core.menus.group_entry')}>
            <FormField name="code" />
            <FormField name="module" />
            <FormField name="label" />
            <FormField name="parent_id" />
            <FormField name="sequence" />
            <FormField name="auth" />
            <FormField name="description" />
          </FormGroup>
          <FormGroup label={t('view.core.menus.group_target')}>
            <FormField name="view" />
            <FormField name="href" />
            <FormField name="img" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
