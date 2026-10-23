import {
  Page,
  PageContent,
  Table,
  TableField,
  Cards,
  Form,
  FormField,
} from '@jerp/ui';

export default function Products() {
  return (
    <Page
      name="stock.products"
      title="Products"
      model="product"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="product" emptyMessage="No products found.">
          <TableField name="name" label="Name" />
          <TableField name="image" label="Image" />
        </Table>
        <Cards model="product" emptyMessage="No products found.">
          <TableField name="name" label="Name" />
          <TableField name="image" label="Image" />
        </Cards>
        <Form model="product" title="Product">
          <FormField name="name" label="Name" />
          <FormField name="image" label="Image" />
        </Form>
      </PageContent>
    </Page>
  );
}
