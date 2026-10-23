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

export default function Fields() {
  return (
    <Page
      name="core.fields"
      title="Fields"
      model="sys.field"
      labelField="field_name"
      searchBar
      create={false}
      update={false}
      delete={false}
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="sys.field" emptyMessage="No fields found.">
          <TableField name="model" />
          <TableField name="field_name" />
          <TableField name="column_name" />
          <TableField name="ttype" />
          <TableField name="label" />
        </Table>

        <Cards model="sys.field" emptyMessage="No fields found.">
          <CardField name="model" />
          <CardField name="field_name" />
          <CardField name="ttype" />
        </Cards>

        <Form model="sys.field" title="Field">
          <FormGroup label="Field">
            <FormField name="model" />
            <FormField name="field_name" />
            <FormField name="column_name" />
            <FormField name="ttype" />
            <FormField name="label" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
