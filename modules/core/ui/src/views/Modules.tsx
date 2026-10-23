import * as React from 'react';
import {
  Page,
  PageContent,
  Table,
  TableField,
  Cards,
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
          <TableField name="name" label="Name" />
          <TableField name="version" label="Version" />
          <TableField name="state" label="Status" />
          <TableField name="summary" label="Description" />
        </Table>

        <Cards model="module" emptyMessage="No modules found.">
          <ModuleLogo />
          <TableField name="name" label="Name" />
          <TableField name="state" label="Status" />
        </Cards>

        <Form model="module" title="Module">
          <ModuleLogo />
          <FormGroup label="General">
            <FormField name="name" label="Name" />
            <FormField name="version" label="Version" />
            <FormField name="state" label="Status" />
          </FormGroup>
          <FormGroup label="Details">
            <FormField name="summary" label="Description" />
            <FormField name="depends" label="Depends on" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
