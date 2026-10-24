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
  Action,
  ActionHeader,
  ActionContent,
  ActionFooter,
  useAction,
  RecordContext,
  model,
} from '@jerp/ui';
import { t } from '@jerp/locale';

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
      await model('sys.user').update(record.id as number, { password });
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
      <ActionHeader>{t('view.core.users.change_password')}</ActionHeader>
      <ActionContent>
        {error ? (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-brand-navy">
            {t('view.core.users.new_password')}
          </span>
          <input
            type="password"
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
      </ActionContent>
      <ActionFooter>
        <button
          type="button"
          className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5"
          onClick={() => action?.close()}
          disabled={busy}
        >
          {t('app.cancel')}
        </button>
        <button
          type="button"
          className="rounded bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
          onClick={() => void submit()}
          disabled={busy || !password}
        >
          {busy ? t('app.saving') : t('app.save')}
        </button>
      </ActionFooter>
    </>
  );
}

export default function Users() {
  return (
    <Page
      name="core.users"
      title={t('view.core.users.title')}
      model="sys.user"
      searchBar
      create
      update
      delete
      open
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sys.user"
          emptyMessage={t('view.core.users.empty_message')}
        >
          <TableField name="name" />
        </Table>

        <Cards
          model="sys.user"
          emptyMessage={t('view.core.users.empty_message')}
        >
          <CardField name="avatar" />
          <CardField name="name" />
        </Cards>

        <Form model="sys.user" title={t('view.core.users.form_title')}>
          <Action label={t('view.core.users.change_password')}>
            <ChangePassword />
          </Action>

          <FormField name="name" />
          <FormField name="username" />
          <FormField name="image" />
          <FormField name="lang_id" />
        </Form>
      </PageContent>
    </Page>
  );
}
