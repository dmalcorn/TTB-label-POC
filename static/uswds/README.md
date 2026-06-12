# Vendored USWDS assets

**Version:** see [`VERSION`](VERSION) — currently **USWDS 3.13.0** (latest 3.x at vendoring).

These are the **compiled** U.S. Web Design System assets, self-hosted to satisfy the
firewall posture (NFR-2 / AR-8): no CDN, no Google Fonts, no Node build step in the app
or Docker image. The committed files are what ship; the only build is the one-time
**dev-time** fetch below.

## What's here

- `css/uswds.min.css` (+ `.map`) — compiled USWDS stylesheet (default theme).
- `js/uswds.min.js`, `js/uswds-init.min.js` (+ `.map`) — USWDS behaviors.
- `fonts/` — `.woff2` only (the sole format the compiled CSS references): `public-sans`,
  `roboto-mono`, `source-sans-pro`, `merriweather`. `.ttf`/`.woff` were pruned as dead weight.
- `img/` — icon sprite (`sprite.svg`), `usa-icons/`, and component images.

The brand layer ([`/static/css/brand.css`](../css/brand.css)) loads **after** this CSS and
applies the Treasury tokens (navy primary, civic green) plus a self-hosted **Public Sans**
`@font-face` so body type renders in Public Sans (DESIGN.md), while Roboto Mono is already
referenced by the compiled CSS natively.

## Regenerate (dev-time only — not part of the app/Docker build)

```sh
# from a scratch dir, with network access (one-time):
npm pack @uswds/uswds@3.13.0
tar -xzf uswds-uswds-3.13.0.tgz
# copy the runtime subset into static/uswds/:
#   package/dist/css/uswds.min.css(.map)
#   package/dist/js/uswds(-init).min.js(.map)
#   package/dist/fonts/  (then delete *.ttf and *.woff — keep *.woff2)
#   package/dist/img/
# update VERSION
```

Do **not** add `node`/`npm`/`@uswds/uswds` to `requirements.txt` or the Docker image.
