import {
  Page,
  PageContent,
  Table,
  TableField,
  Cards,
  CardField,
  Form,
  FormField,
  FormGroup,
} from '@jerp/ui';
import { t } from '@jerp/locale';

export default function Modules() {
  return (
    <Page
      name="core.modules"
      title={t('core.modules.title')}
      model="module"
      create={false}
      update={false}
      delete={false}
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="module" emptyMessage={t('core.modules.empty_message')}>
          <TableField name="name" />
          <TableField name="version" />
          <TableField name="state" />
          <TableField name="summary" />
        </Table>

        <Cards model="module" emptyMessage={t('core.modules.empty_message')}>
          <CardField name="logo" />
          <CardField name="name" />
          <CardField name="state" widget="badge" badge_colors={{ installed: 'green', install_failed: 'red', not_installed: 'gray' }} />
        </Cards>

        <Form model="module" title={t('core.modules.title')}>
          <FormField name="logo" />
          <FormGroup label="General">
            <FormField name="name" />
            <FormField name="version" />
            <FormField name="state" />
          </FormGroup>
          <FormGroup label="Details">
            <FormField name="summary" />
            <FormField name="depends" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
