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

export default function OrderLines() {
  return (
    <Page
      name="sale.order_lines"
      title="Order Lines"
      model="sale.order.line"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="sale.order.line" emptyMessage="No order lines found.">
          <TableField name="order_id" />
          <TableField name="product_id" />
          <TableField name="name" />
          <TableField name="quantity" />
          <TableField name="price_unit" />
          <TableField name="subtotal" />
        </Table>

        <Cards model="sale.order.line" emptyMessage="No order lines found.">
          <CardField name="name" />
          <CardField name="order_id" />
          <CardField name="product_id" />
          <CardField name="quantity" />
          <CardField name="subtotal" />
        </Cards>

        <Form model="sale.order.line" title="Order Line">
          <FormGroup label="Line">
            <FormField name="order_id" />
            <FormField name="product_id" />
            <FormField name="name" />
            <FormField name="quantity" />
            <FormField name="price_unit" />
            <FormField name="subtotal" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
