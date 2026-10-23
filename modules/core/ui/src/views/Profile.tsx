import * as React from 'react';
import { Page, PageContent, Form, FormField, FormGroup, model } from '@jerp/ui';

function currentUsername(): string {
  const match = document.cookie.match(/(?:^|;\s*)jerp_user=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

export default function Profile() {
  const [userId, setUserId] = React.useState<number | null>(null);

  React.useEffect(() => {
    const username = currentUsername();
    if (!username) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const users = await model('sys.user').all<{ id: number }>({
          domain: [['username', '=', username]],
          limit: 1,
        });
        if (!cancelled) {
          setUserId(users[0]?.id ?? null);
        }
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Page
      name="core.profile"
      title="Profile"
      model="sys.user"
      searchBar={false}
      create={false}
      delete={false}
      recordBreadcrumb={false}
      views={['form']}
    >
      <PageContent>
        {userId ? (
          <Form model="sys.user" title="Profile" recordId={userId}>
            <FormGroup label="Profile">
              <FormField name="name" />
              <FormField name="image" />
            </FormGroup>
          </Form>
        ) : null}
      </PageContent>
    </Page>
  );
}
