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
import { t } from '@jerp/locale';

export default function OrderLines() {
  return (
    <Page
      name="sale.order_lines"
      title={t('view.sale.order_lines.title')}
      model="sale.order.line"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="sale.order.line" emptyMessage={t('view.sale.order_lines.empty_message')}>
          <TableField name="order_id" />
          <TableField name="product_id" />
          <TableField name="name" />
          <TableField name="quantity" />
          <TableField name="price_unit" />
          <TableField name="subtotal" />
        </Table>

        <Cards model="sale.order.line" emptyMessage={t('view.sale.order_lines.empty_message')}>
          <CardField name="name" />
          <CardField name="order_id" />
          <CardField name="product_id" />
          <CardField name="quantity" />
          <CardField name="subtotal" />
        </Cards>

        <Form model="sale.order.line" title={t('view.sale.order_lines.form.title')}>
          <FormGroup label={t('view.sale.order_lines.form.group_line')}>
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
