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

export default function Contacts() {
  return (
    <Page
      name="core.contacts"
      title="Contacts"
      model="sys.contact"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="sys.contact" emptyMessage="No contacts found.">
          <TableField name="name" />
          <TableField name="email" />
          <TableField name="phone" />
          <TableField name="country_id" />
          <TableField name="state_id" />
        </Table>

        <Cards model="sys.contact" emptyMessage="No contacts found.">
          <CardField name="image" />
          <CardField name="name" />
          <CardField name="email" />
          <CardField name="phone" />
          <CardField name="country_id" />
          <CardField name="state_id" />
        </Cards>

        <Form model="sys.contact" title="Contact">
          <FormField name="name" />
          <FormGroup label="Contact Info">
            <FormField name="email" />
            <FormField name="phone" />
          </FormGroup>
          <FormGroup label="Address">
            <FormField name="address" />
            <FormField name="country_id" />
            <FormField name="state_id" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
