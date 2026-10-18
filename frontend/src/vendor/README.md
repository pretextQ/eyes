# shadcn Tailwind CSS

`shadcn-tailwind.css` is an unmodified copy of `dist/tailwind.css` from the npm
package `shadcn@4.21.1` (MIT, copyright 2023 shadcn). The full license is preserved
in [shadcn.txt](../../public/licenses/shadcn.txt). Vite also copies this notice to
`/licenses/shadcn.txt` in the deployed site.

- Upstream: <https://github.com/shadcn-ui/ui>
- Source package: <https://registry.npmjs.org/shadcn/-/shadcn-4.21.1.tgz>
- SHA-256: `4c371f7a1ff5d219ae2f7ff28bd256b4346fd546fe46fbae22092e57db2f0fae`

Eyes uses these CSS utilities and variants, but does not execute the shadcn CLI.
Keeping the stylesheet here avoids installing the unused CLI and its vulnerable
glob dependency chain (GHSA-vfj7-8cjw-p6xm). Existing UI components and
`components.json` remain maintained in the repository.

The stylesheet is excluded from Prettier so its upstream bytes and checksum remain
stable. Project-owned styles continue to use the normal formatting checks.

To update, review the upstream stylesheet and license, copy the CSS without
modification, update the version and SHA-256 here, and run the frontend checks and
compare the generated CSS. Audit any proposed component-generation tooling before
adding it; do not restore the CLI dependency solely to import this stylesheet.
