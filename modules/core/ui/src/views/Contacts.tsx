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

export default function Contacts() {
  return (
    <Page
      name="core.contacts"
      title={t('view.core.contacts.title')}
      model="sys.contact"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sys.contact"
          emptyMessage={t('view.core.contacts.empty_message')}
        >
          <TableField name="name" />
          <TableField name="email" />
          <TableField name="phone" />
          <TableField name="country_id" />
          <TableField name="state_id" />
        </Table>

        <Cards
          model="sys.contact"
          emptyMessage={t('view.core.contacts.empty_message')}
        >
          <CardField name="image" />
          <CardField name="name" />
          <CardField name="email" />
          <CardField name="phone" />
          <CardField name="country_id" />
          <CardField name="state_id" />
        </Cards>

        <Form model="sys.contact" title={t('view.core.contacts.form_title')}>
          <FormField name="name" />
          <FormGroup label={t('view.core.contacts.group_contact_info')}>
            <FormField name="email" />
            <FormField name="phone" />
          </FormGroup>
          <FormGroup label={t('view.core.contacts.group_address')}>
            <FormField name="address" />
            <FormField name="country_id" />
            <FormField name="state_id" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
