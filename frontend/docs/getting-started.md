# Run the frontend locally

Use Node.js 22 or newer. From the frontend directory:

```bash
npm ci
COYOTE4_API_INTERNAL_URL=http://127.0.0.1:8001 npm run dev
```

The proxy target above assumes a separately configured local API on port 8001.
The command starts only the browser development server; it does not start the
API, databases or workers. Use the address printed by Vite to open the interface.

React and style edits use Vite's development reload. Configuration inputs are read
when Vite starts, so restart it after changing them. See
[configuration](configuration.md) for mount prefixes and proxy behavior.

The repository's complete local-stack guide is the appropriate starting point
when a disposable application and synthetic data are also needed.
