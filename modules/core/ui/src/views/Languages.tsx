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

export default function Languages() {
  return (
    <Page
      name="core.languages"
      title={t('view.core.languages.title')}
      model="sys.lang"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sys.lang"
          emptyMessage={t('view.core.languages.empty_message')}
        >
          <TableField name="name" />
          <TableField name="code" />
          <TableField name="active" />
          <TableField name="is_default" />
        </Table>

        <Cards
          model="sys.lang"
          emptyMessage={t('view.core.languages.empty_message')}
        >
          <CardField name="name" />
          <CardField name="code"  />
          <CardField name="active" widget="badge" badge_colors={{ true: 'green', false: 'gray' }} />
          <CardField name="is_default" />
        </Cards>

        <Form model="sys.lang" title={t('view.core.languages.form_title')}>
          <FormField name="name" />
          <FormField name="code" />
          <FormField name="active" />
          <FormField name="is_default" />
        </Form>
      </PageContent>
    </Page>
  );
}
