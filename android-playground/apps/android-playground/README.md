# Midscene Android Playground

Playground tool for Android cli @midscene/android.

See https://midscenejs.com/ for details.

## Workspace dev (recommended)

From workspace root:

```bash
pnpm dev:auto
```

This command starts UI dev server and all dependent package watchers together
(`@midscene/visualizer`, `@midscene/playground`, etc.), so `src` and `dist`
stay in sync and UI language/content won't fall back to stale bundles.

Start backend service in another terminal:

```bash
pnpm dev:server
```
