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

export default function States() {
  return (
    <Page
      name="core.states"
      title="States"
      model="sys.state"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="sys.state" emptyMessage="No states found.">
          <TableField name="name" />
          <TableField name="code" />
          <TableField name="country_id" />
        </Table>

        <Cards model="sys.state" emptyMessage="No states found.">
          <CardField name="name" />
          <CardField name="code" />
          <CardField name="country_id" />
        </Cards>

        <Form model="sys.state" title="State">
          <FormField name="name" />
          <FormField name="code" />
          <FormField name="country_id" />
        </Form>
      </PageContent>
    </Page>
  );
}
