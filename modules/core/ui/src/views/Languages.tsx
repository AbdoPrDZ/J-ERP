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

export default function Languages() {
  return (
    <Page
      name="core.languages"
      title="Languages"
      model="sys.lang"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="sys.lang" emptyMessage="No languages found.">
          <TableField name="name" />
          <TableField name="code" />
          <TableField name="active" />
          <TableField name="is_default" />
        </Table>

        <Cards model="sys.lang" emptyMessage="No languages found.">
          <CardField name="name" />
          <CardField name="code"  />
          <CardField name="active" widget="badge" badge_colors={{ true: 'green', false: 'gray' }} />
          <CardField name="is_default" />
        </Cards>

        <Form model="sys.lang" title="Language">
          <FormField name="name" />
          <FormField name="code" />
          <FormField name="active" />
          <FormField name="is_default" />
        </Form>
      </PageContent>
    </Page>
  );
}
