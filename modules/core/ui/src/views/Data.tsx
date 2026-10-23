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

export default function Data() {
  return (
    <Page
      name="core.data"
      title="Data"
      model="sys.data"
      labelField="key"
      searchBar
      create={false}
      update={false}
      delete={false}
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="sys.data" emptyMessage="No external identifiers found.">
          <TableField name="module" />
          <TableField name="model" />
          <TableField name="name" />
          <TableField name="key" />
          <TableField name="res_id" />
        </Table>

        <Cards model="sys.data" emptyMessage="No external identifiers found.">
          <CardField name="key" />
          <CardField name="model" />
          <CardField name="res_id" />
        </Cards>

        <Form model="sys.data" title="External Identifier">
          <FormGroup label="Reference">
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
