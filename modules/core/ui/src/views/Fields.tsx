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

export default function Fields() {
  return (
    <Page
      name="core.fields"
      title={t('view.core.fields.title')}
      model="sys.field"
      labelField="field_name"
      searchBar
      create={false}
      update={false}
      delete={false}
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sys.field"
          emptyMessage={t('view.core.fields.empty_message')}
        >
          <TableField name="model" />
          <TableField name="field_name" />
          <TableField name="column_name" />
          <TableField name="ttype" />
          <TableField name="label" />
        </Table>

        <Cards
          model="sys.field"
          emptyMessage={t('view.core.fields.empty_message')}
        >
          <CardField name="model" />
          <CardField name="field_name" />
          <CardField name="ttype" />
        </Cards>

        <Form model="sys.field" title={t('view.core.fields.form_title')}>
          <FormGroup label={t('view.core.fields.group_field')}>
            <FormField name="model" />
            <FormField name="field_name" />
            <FormField name="column_name" />
            <FormField name="ttype" />
            <FormField name="label" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
