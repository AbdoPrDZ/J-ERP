import * as React from 'react';
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
  RecordContext,
} from '@jerp/ui';

/** Custom card/form content (not a field): the module's logo. */
function ModuleLogo() {
  const record = React.useContext(RecordContext);
  const logo = (record?.logo as string | undefined) ?? null;
  if (!logo) {
    return null;
  }
  return <img src={logo} alt="" className="h-12 w-12 rounded" />;
}

export default function Modules() {
  return (
    <Page
      name="core.modules"
      title="Modules"
      model="module"
      create={false}
      update={false}
      delete={false}
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="module" emptyMessage="No modules found.">
          <TableField name="name" />
          <TableField name="version" />
          <TableField name="state" />
          <TableField name="summary" />
        </Table>

        <Cards model="module" emptyMessage="No modules found.">
          <CardField name="logo" />
          <CardField name="name" />
          <CardField name="state" widget="badge" badge_colors={{ installed: 'green', install_failed: 'red', not_installed: 'gray' }} />
        </Cards>

        <Form model="module" title="Module">
          <FormField name="logo" />
          <FormGroup label="General">
            <FormField name="name" />
            <FormField name="version" />
            <FormField name="state" />
          </FormGroup>
          <FormGroup label="Details">
            <FormField name="summary" />
            <FormField name="depends" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
