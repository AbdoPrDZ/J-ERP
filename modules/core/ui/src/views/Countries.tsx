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

export default function Countries() {
  return (
    <Page
      name="core.countries"
      title={t('view.core.countries.title')}
      model="sys.country"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sys.country"
          emptyMessage={t('view.core.countries.empty_message')}
        >
          <TableField name="name" />
          <TableField name="code" />
          <TableField name="phone_code" />
        </Table>

        <Cards
          model="sys.country"
          emptyMessage={t('view.core.countries.empty_message')}
        >
          <CardField name="image" />
          <CardField name="name" />
          <CardField name="code" />
          <CardField name="phone_code" />
        </Cards>

        <Form model="sys.country" title={t('view.core.countries.form_title')}>
          <FormField name="name" />
          <FormField name="code" />
          <FormField name="phone_code" />
        </Form>
      </PageContent>
    </Page>
  );
}
