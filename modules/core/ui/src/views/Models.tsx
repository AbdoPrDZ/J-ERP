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

export default function Models() {
  return (
    <Page
      name="core.models"
      title="Models"
      model="sys.model"
      searchBar
      create={false}
      update={false}
      delete={false}
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="sys.model" emptyMessage="No models found.">
          <TableField name="name" />
          <TableField name="table_name" />
        </Table>

        <Cards model="sys.model" emptyMessage="No models found.">
          <CardField name="name" />
          <CardField name="table_name" />
        </Cards>

        <Form model="sys.model" title="Model">
          <FormGroup label="Model">
            <FormField name="name" />
            <FormField name="table_name" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
