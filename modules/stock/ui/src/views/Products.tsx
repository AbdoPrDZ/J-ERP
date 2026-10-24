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

export default function Products() {
  return (
    <Page
      name="stock.products"
      title={t('view.stock.products.title')}
      model="stock.product"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="stock.product" emptyMessage={t('view.stock.products.empty_message')}>
          <TableField name="name" />
          <TableField name="image" />
        </Table>
        <Cards model="stock.product" emptyMessage={t('view.stock.products.empty_message')}>
          <CardField name="name" />
          <CardField name="image" />
        </Cards>
        <Form model="stock.product" title={t('view.stock.products.form.title')}>
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
