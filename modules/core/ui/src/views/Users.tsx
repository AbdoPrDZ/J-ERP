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
  Action,
  ActionHeader,
  ActionContent,
  ActionFooter,
  useAction,
  RecordContext,
  model,
} from '@jerp/ui';

/** Self-contained modal content for the "Change Password" action. */
function ChangePassword() {
  const [password, setPassword] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const record = React.useContext(RecordContext);
  const action = useAction();

  const submit = async () => {
    if (!password || busy || !record?.id) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await model('user').update(record.id as number, { password });
      setPassword('');
      action?.close();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <ActionHeader>Change Password</ActionHeader>
      <ActionContent>
        {error ? (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            New password
          </span>
          <input
            type="password"
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
      </ActionContent>
      <ActionFooter>
        <button
          type="button"
          className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
          onClick={() => action?.close()}
          disabled={busy}
        >
          Cancel
        </button>
        <button
          type="button"
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
          onClick={() => void submit()}
          disabled={busy || !password}
        >
          {busy ? 'Saving…' : 'Save'}
        </button>
      </ActionFooter>
    </>
  );
}

export default function Users() {
  return (
    <Page
      name="core.users"
      title="Users"
      model="user"
      searchBar
      create
      update
      delete
      open
      views={['list', 'cards']}
    >
      <PageContent>
        <Table model="user" emptyMessage="No users found.">
          <TableField name="name" label="Name" />
        </Table>
        <Cards model="user" emptyMessage="No users found.">
          <TableField name="name" label="Name" />
        </Cards>
        <Form model="user" title="User">
          <Action label="Change Password">
            <ChangePassword />
          </Action>
          <FormGroup label="General">
            <FormField name="name" label="Name" />
            <FormField name="username" label="Username" />
            <FormField name="image" label="Avatar" />
          </FormGroup>
        </Form>
      </PageContent>
    </Page>
  );
}
