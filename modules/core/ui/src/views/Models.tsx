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

export default function Models() {
  return (
    <Page
      name="core.models"
      title={t('view.core.models.title')}
      model="sys.model"
      searchBar
      create={false}
      update={false}
      delete={false}
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sys.model"
          emptyMessage={t('view.core.models.empty_message')}
        >
          <TableField name="name" />
          <TableField name="table_name" />
        </Table>

        <Cards
          model="sys.model"
          emptyMessage={t('view.core.models.empty_message')}
        >
          <CardField name="name" />
          <CardField name="table_name" />
        </Cards>

        <Form model="sys.model" title={t('view.core.models.form_title')}>
          <FormGroup label={t('view.core.models.group_model')}>
            <FormField name="name" />
            <FormField name="table_name" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
