# Domains

Domain files capture knowledge that is broader or deeper than the project-wide
files, but still not a code inventory. Read only the domains relevant to the
task.

| File | Domain | Read it for |
|---|---|---|
| `framework.md` | J-ERP backend framework | Models, fields, schema sync, registry, module lifecycle, environment |
| `auth.md` | Authentication and session | Login, cookies, user model, current authorization limits |
| `ui.md` | Shared React UI kit and view pipeline | Building views, component behavior, runtime module loading |
| `stock.md` | Stock business module | Products, dependencies on core, extending stock |

Rules:

- One file per meaningful domain — never per module, model, or table.
- Include purpose, important entities, business rules, relationships,
  workflows, integrations, constraints, and project-specific implementation
  knowledge.
- Keep generic framework documentation out; describe only how this project uses
  it.
- Create a new domain file only through a deliberate structure change recorded
  in `../structure.md`.
