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

export default function Data() {
  return (
    <Page
      name="core.data"
      title={t('view.core.data.title')}
      model="sys.data"
      labelField="key"
      searchBar
      create={false}
      update={false}
      delete={false}
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sys.data"
          emptyMessage={t('view.core.data.empty_message')}
        >
          <TableField name="module" />
          <TableField name="model" />
          <TableField name="name" />
          <TableField name="key" />
          <TableField name="res_id" />
        </Table>

        <Cards
          model="sys.data"
          emptyMessage={t('view.core.data.empty_message')}
        >
          <CardField name="key" />
          <CardField name="model" />
          <CardField name="res_id" />
        </Cards>

        <Form model="sys.data" title={t('view.core.data.form_title')}>
          <FormGroup label={t('view.core.data.group_reference')}>
            <FormField name="module" />
            <FormField name="model" />
            <FormField name="name" />
            <FormField name="key" />
            <FormField name="res_id" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
