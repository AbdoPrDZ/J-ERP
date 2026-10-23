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
        const users = await model('user').all<{ id: number }>({
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
    <Page name="core.profile" title="Profile" model="user">
      <PageContent>
        {userId ? (
          <Form model="user" title="Profile" recordId={userId}>
            <FormGroup label="Profile">
              <FormField name="name" label="Name" />
              <FormField name="image" label="Avatar" />
            </FormGroup>
          </Form>
        ) : null}
      </PageContent>
    </Page>
  );
}
