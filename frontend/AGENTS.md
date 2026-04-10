<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

## Frontend Working Rules
- Keep all admin route work aligned with `src/app/admin/page.tsx` and existing dark-theme visual language.
- Preserve responsiveness across mobile and desktop when editing dashboard layout.
- Do not remove admin auth header usage (`X-Admin-User`, `X-Admin-Password`) in API calls.
- Any destructive action UI (bulk delete/history delete) should keep explicit user confirmation safeguards.
- Prefer minimal state complexity and avoid introducing global state libraries unless explicitly required.

## API Integration Rules
- Backend API base URL must come from `NEXT_PUBLIC_API_URL` fallback behavior already used in code.
- Keep endpoint paths consistent with backend routers:
	- `/api/admin/*`
	- `/api/intake/*`
- For WhatsApp docs/UI text, use canonical route naming: `/api/intake/twilio`.

## Quality Gates
- Run `npm run lint` after frontend changes.
- Avoid visual regressions in tabs:
	- Dashboard
	- Assigned Tickets
	- Manage Data

## File Focus
- Main admin implementation: `src/app/admin/page.tsx`
- Project config: `package.json`, `tsconfig.json`, `next.config.ts`
<!-- END:nextjs-agent-rules -->
