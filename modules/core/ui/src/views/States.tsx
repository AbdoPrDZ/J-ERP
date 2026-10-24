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

export default function States() {
  return (
    <Page
      name="core.states"
      title={t('view.core.states.title')}
      model="sys.state"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sys.state"
          emptyMessage={t('view.core.states.empty_message')}
        >
          <TableField name="name" />
          <TableField name="code" />
          <TableField name="country_id" />
        </Table>

        <Cards
          model="sys.state"
          emptyMessage={t('view.core.states.empty_message')}
        >
          <CardField name="name" />
          <CardField name="code" />
          <CardField name="country_id" />
        </Cards>

        <Form model="sys.state" title={t('view.core.states.form_title')}>
          <FormField name="name" />
          <FormField name="code" />
          <FormField name="country_id" />
        </Form>
      </PageContent>
    </Page>
  );
}
