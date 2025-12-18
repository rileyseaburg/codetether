# Pocket

Pocket is a [Tailwind Plus](https://tailwindcss.com/plus) site template built using [Tailwind CSS](https://tailwindcss.com) and [Next.js](https://nextjs.org).

## Getting started

To get started with this template, first install the npm dependencies:

```bash
npm install
```

Next, run the development server:

```bash
npm run dev
```

Finally, open [http://localhost:3000](http://localhost:3000) in your browser to view the website.

## Local login (Keycloak / NextAuth)

This app uses NextAuth (Keycloak provider). For local development, the Keycloak client must allow the callback URL that NextAuth uses.

### 1) Ensure `NEXTAUTH_URL` matches the port you are running

If port `3000` is already in use, Next.js will move to another port (for example `3001`). In that case, set:

- `NEXTAUTH_URL=http://localhost:3001`

This repo includes a dev override at `/.env.development.local` for that purpose.

### 2) Update Keycloak client redirect URIs

In the Keycloak Admin Console, open the client configured by `KEYCLOAK_CLIENT_ID` (default: `a2a-monitor`) and add at least one of the following to **Valid Redirect URIs**:

- `http://localhost:3001/api/auth/*`
- `http://127.0.0.1:3001/api/auth/*`

NextAuth’s Keycloak callback endpoint is:

- `http://localhost:3001/api/auth/callback/keycloak`

If you see `Invalid parameter: redirect_uri` during login, it almost always means this list does not include the URL/port you are using.

Optionally also add the matching **Web Origins** entries:

- `http://localhost:3001`
- `http://127.0.0.1:3001`

## Customizing

You can start editing this template by modifying the files in the `/src` folder. The site will auto-update as you edit these files.

## License

This site template is a commercial product and is licensed under the [Tailwind Plus license](https://tailwindcss.com/plus/license).

## Learn more

To learn more about the technologies used in this site template, see the following resources:

- [Tailwind CSS](https://tailwindcss.com/docs) - the official Tailwind CSS documentation
- [Next.js](https://nextjs.org/docs) - the official Next.js documentation
- [Headless UI](https://headlessui.dev) - the official Headless UI documentation
