import {
  Page,
  PageContent,
  Table,
  TableField,
  FormTable,
  Cards,
  CardField,
  Form,
  FormField,
  FormGroup,
  FormTabs,
  FormTab,
} from '@jerp/ui';


export default function Orders() {
  return (
    <Page
      name="sale.orders"
      title="Sale Orders"
      model="sale.order"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sale.order"
          emptyMessage="No sale orders found."
        >
          <TableField name="name" />
          <TableField name="client_id" />
          <TableField name="date_order" />
          <TableField name="state" />
          <TableField name="amount_total" />
        </Table>

        <Cards model="sale.order" emptyMessage="No sale orders found.">
          <CardField name="name" />
          <CardField name="client_id" />
          <CardField name="date_order" />
          <CardField name="state" />
          <CardField name="amount_total" />
        </Cards>

        <Form model="sale.order" title="Sale Order">
          <FormGroup label="Order">
            <FormField name="name" />
            <FormField name="client_id" />
            <FormField name="date_order" />
            <FormField name="state" />
            <FormField name="amount_total" />
          </FormGroup>

          <FormTabs>
            <FormTab label="Lines">
              <FormTable model="sale.order.line" emptyMessage="No lines found.">
                <TableField name="product_id" />
                <TableField name="name" />
                <TableField name="quantity" />
                <TableField name="price_unit" />
                <TableField name="subtotal" />
              </FormTable>
            </FormTab>
            <FormTab label="Notes">
              <FormField name="note" />
            </FormTab>
          </FormTabs>
        </Form>
      </PageContent>
    </Page>
  );
}
