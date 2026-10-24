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
import { t } from '@jerp/locale';


export default function Orders() {
  return (
    <Page
      name="sale.orders"
      title={t('view.sale.orders.title')}
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
          emptyMessage={t('view.sale.orders.empty_message')}
        >
          <TableField name="name" />
          <TableField name="client_id" />
          <TableField name="date_order" />
          <TableField name="state" />
          <TableField name="amount_total" />
        </Table>

        <Cards model="sale.order" emptyMessage={t('view.sale.orders.empty_message')}>
          <CardField name="name" />
          <CardField name="client_id" />
          <CardField name="date_order" />
          <CardField name="state" />
          <CardField name="amount_total" />
        </Cards>

        <Form model="sale.order" title={t('view.sale.orders.form.title')}>
          <FormGroup label={t('view.sale.orders.form.group_general')}>
            <FormField name="name" />
            <FormField name="client_id" />
            <FormField name="date_order" />
            <FormField name="state" />
            <FormField name="amount_total" />
          </FormGroup>

          <FormTabs>
            <FormTab label={t('view.sale.orders.form.tabs.lines.label')}>
              <FormTable model="sale.order.line" emptyMessage={t('view.sale.orders.form.tabs.lines.empty_message')}>
                <TableField name="product_id" />
                <TableField name="name" />
                <TableField name="quantity" />
                <TableField name="price_unit" />
                <TableField name="subtotal" />
              </FormTable>
            </FormTab>
            <FormTab label={t('view.sale.orders.form.tabs.notes.label')}>
              <FormField name="note" />
            </FormTab>
          </FormTabs>
        </Form>
      </PageContent>
    </Page>
  );
}
