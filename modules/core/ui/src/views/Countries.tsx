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

export default function Countries() {
  return (
    <Page
      name="core.countries"
      title="Countries"
      model="sys.country"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="sys.country" emptyMessage="No countries found.">
          <TableField name="name" />
          <TableField name="code" />
          <TableField name="phone_code" />
        </Table>

        <Cards model="sys.country" emptyMessage="No countries found.">
          <CardField name="image" />
          <CardField name="name" />
          <CardField name="code" />
          <CardField name="phone_code" />
        </Cards>

        <Form model="sys.country" title="Country">
          <FormField name="name" />
          <FormField name="code" />
          <FormField name="phone_code" />
        </Form>
      </PageContent>
    </Page>
  );
}
