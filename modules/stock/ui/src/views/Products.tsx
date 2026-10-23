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

export default function Products() {
  return (
    <Page
      name="stock.products"
      title="Products"
      model="stock.product"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="stock.product" emptyMessage="No products found.">
          <TableField name="name" />
          <TableField name="image" />
        </Table>
        <Cards model="stock.product" emptyMessage="No products found.">
          <CardField name="name" />
          <CardField name="image" />
        </Cards>
        <Form model="stock.product" title="Product">
          <FormField name="name" />
          <FormField name="image" />
          <FormGroup label="Pricing">
            <FormField name="standard_price" />
            <FormField name="price" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
