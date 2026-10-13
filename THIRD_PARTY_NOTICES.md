# Third-party notices

WattWise's original source and documentation use the MIT license in `LICENSE`.
Dependency code retains its own license. The source commit excludes `.venv`,
`node_modules`, native binaries, SQLite files, and build outputs; it includes
manifests and lockfiles that let users obtain dependencies from their upstreams.
The dashboard screenshot was created from this project's own local browser test.
No external images, fonts, or copied application templates are included.

## Review scope and preserved notices

Reviewed 13 October 2026 against `requirements-lock.txt`, `web/package-lock.json`,
and the installed Python / npm distributions. The tables record upstream license
metadata for all locked dependencies, including development and optional platform
packages. Metadata is descriptive; upstream license texts govern.

[docs/third-party-licenses.txt](docs/third-party-licenses.txt) preserves the available
upstream LICENSE, COPYING, and NOTICE files verbatim, including AWS SDK notices
and licenses shipped inside Next.js's compiled dependencies. Optional packages
for platforms other than this Windows environment were inventoried from the
lockfile but their archives were not installed or independently inspected.

## Attribution and distribution requirements

- **MIT, BSD, ISC, PSF and similar licenses:** preserve the relevant copyright,
  permission, conditions and disclaimer texts when distributing covered code.
  WattWise's MIT license does not replace those texts.
  [MIT license](https://opensource.org/license/mit).
- **Apache-2.0:** include the license, retain relevant attribution notices and
  supplied NOTICE content, and mark modified upstream files if distributing
  modifications. AWS boto3, botocore and s3transfer NOTICE files are included
  in the preserved bundle. [Apache section 4](https://www.apache.org/licenses/LICENSE-2.0).
- **MPL-2.0:** certifi and lightningcss have file-level copyleft obligations.
  If distributing their covered code in executable form, inform recipients
  how to obtain the corresponding MPL source; modifications to covered files
  retain MPL terms. Original WattWise files do not contain copied MPL code.
  Sources: [certifi](https://github.com/certifi/python-certifi),
  [lightningcss](https://github.com/parcel-bundler/lightningcss).
  [Mozilla FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/).
- **CC-BY-4.0:** caniuse-lite's browser-support data requires attribution and a
  license link when redistributed; identify changes if the data is modified.
  Attribution: caniuse-lite / Can I Use contributors,
  [upstream data](https://github.com/browserslist/caniuse-lite),
  [license](https://creativecommons.org/licenses/by/4.0/).
- **LGPL:** the optional Windows sharp binary package declares
  `Apache-2.0 AND LGPL-3.0-or-later`. If packaging native binaries in a release,
  review the exact upstream library/source, notice, replacement/relinking and
  installation-information requirements for that artifact. These binaries are
  excluded from this source commit. A source-only GitHub commit is not a review
  of a future binary installer or container image.
  [sharp](https://github.com/lovell/sharp),
  [sharp-libvips](https://github.com/lovell/sharp-libvips),
  [LGPL v3](https://www.gnu.org/licenses/lgpl-3.0.html).

This inventory covers the current source publication. Future dependency updates
or distributions containing installed dependencies/build outputs need a renewed
review of the exact shipped artifacts and their notices.

### License files absent from installed Python archives

The following distributions declare licenses in metadata but do not ship a
LICENSE/NOTICE file in their installed RECORD: `dnspython`, `py-key-value-aio`, `py-key-value-shared`.
No missing license text has been invented. Their declarations and upstream
references are recorded below; retain upstream notices if vendoring them.

- [dnspython (ISC)](https://github.com/rthalley/dnspython/blob/main/LICENSE)
- [py-key-value upstream (Apache-2.0)](https://github.com/strawgate/py-key-value)

## Python dependency inventory

| Package | Version | Declared license | Preserved files |
|---|---|---|---|
| annotated-doc | 0.0.5 | MIT | 1 |
| annotated-types | 0.8.0 | MIT | 1 |
| anyio | 4.15.1 | MIT | 1 |
| attrs | 26.1.0 | MIT | 1 |
| Authlib | 1.8.0 | BSD-3-Clause | 1 |
| beartype | 0.23.1 | MIT | 1 |
| boto3 | 1.43.111 | Apache-2.0 | 2 |
| botocore | 1.43.111 | Apache-2.0 | 2 |
| burner-redis | 0.1.7 | MIT | 1 |
| cachetools | 7.2.1 | MIT | 1 |
| certifi | 2026.7.22 | MPL-2.0 | 1 |
| cffi | 2.1.1 | MIT-0 | 1 |
| click | 8.5.0 | BSD-3-Clause | 1 |
| cloudpickle | 3.1.2 | BSD-3-Clause | 1 |
| colorama | 0.4.6 | BSD License | 1 |
| cronsim | 2.7 | BSD License | 1 |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | 3 |
| cyclopts | 5.2.0 | Apache-2.0 | 1 |
| diskcache | 5.6.3 | Apache 2.0 | 1 |
| dnspython | 2.9.0 | ISC | 0 |
| docstring_parser | 0.18.0 | MIT | 1 |
| email-validator | 2.3.0 | Unlicense | 1 |
| exceptiongroup | 1.3.1 | MIT License | 1 |
| fastapi | 0.143.0 | MIT | 1 |
| fastmcp | 2.14.5 | Apache-2.0 | 1 |
| h11 | 0.16.0 | MIT | 1 |
| httpcore | 1.0.9 | BSD-3-Clause | 1 |
| httpx | 0.28.1 | BSD-3-Clause | 1 |
| httpx-sse | 0.4.3 | MIT | 1 |
| idna | 3.20 | BSD-3-Clause | 1 |
| iniconfig | 2.3.1 | MIT | 1 |
| jaraco.classes | 3.4.0 | MIT License | 1 |
| jaraco.context | 6.1.2 | MIT | 1 |
| jaraco.functools | 4.6.0 | MIT | 1 |
| jmespath | 1.1.0 | MIT | 1 |
| joserfc | 1.7.5 | BSD-3-Clause | 1 |
| jsonref | 1.1.0 | MIT | 1 |
| jsonschema | 4.26.0 | MIT | 1 |
| jsonschema-path | 0.5.0 | Apache-2.0 | 1 |
| jsonschema-specifications | 2025.9.1 | MIT | 1 |
| keyring | 25.7.0 | MIT | 1 |
| markdown-it-py | 4.2.0 | MIT License | 2 |
| mcp | 1.26.0 | MIT | 1 |
| mdurl | 0.1.2 | MIT License | 1 |
| more-itertools | 11.1.0 | MIT | 1 |
| openapi-pydantic | 0.6.0 | MIT | 5 |
| opentelemetry-api | 1.45.1 | Apache-2.0 | 1 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | 3 |
| pathable | 0.6.0 | Apache-2.0 | 1 |
| pathvalidate | 3.3.1 | MIT License | 1 |
| platformdirs | 4.13.0 | MIT | 1 |
| pluggy | 1.6.0 | MIT | 1 |
| prometheus_client | 0.26.0 | Apache-2.0 AND BSD-2-Clause | 2 |
| py-key-value-aio | 0.3.0 | Apache Software License | 0 |
| py-key-value-shared | 0.3.0 | Apache Software License | 0 |
| pycparser | 3.11 | BSD-3-Clause | 1 |
| pydantic | 2.14.1 | MIT | 1 |
| pydantic-settings | 2.15.0 | MIT | 1 |
| pydantic_core | 2.50.1 | MIT | 1 |
| pydocket | 0.27.0 | MIT | 1 |
| Pygments | 2.21.0 | BSD-2-Clause | 1 |
| PyJWT | 2.15.1 | MIT | 1 |
| pyperclip | 1.11.0 | BSD | 1 |
| pytest | 9.1.1 | MIT | 1 |
| pytest-asyncio | 1.4.0 | Apache-2.0 | 1 |
| python-dateutil | 2.9.0.post0 | Dual License | 1 |
| python-dotenv | 1.2.4 | BSD-3-Clause | 1 |
| python-json-logger | 4.2.0 | BSD-2-Clause | 1 |
| python-multipart | 0.0.32 | Apache-2.0 | 1 |
| pywin32 | 312 | PSF | 14 |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | 1 |
| PyYAML | 6.0.3 | MIT | 1 |
| redis | 8.1.0 | MIT | 1 |
| referencing | 0.37.0 | MIT | 1 |
| rich | 15.0.0 | MIT | 1 |
| rich-rst | 2.2.0 | MIT | 3 |
| rpds-py | 2026.9.1 | MIT | 1 |
| s3transfer | 0.19.2 | Apache License 2.0 | 2 |
| shellingham | 1.5.4 | ISC License | 1 |
| six | 1.17.0 | MIT | 1 |
| sse-starlette | 3.5.0 | BSD-3-Clause | 1 |
| starlette | 1.7.0 | BSD-3-Clause | 1 |
| typer | 0.27.3 | MIT | 2 |
| typing-inspection | 0.4.4 | MIT | 1 |
| typing_extensions | 4.16.0 | PSF-2.0 | 1 |
| tzdata | 2026.5 | Apache-2.0 | 2 |
| uncalled-for | 0.4.1 | MIT | 1 |
| urllib3 | 2.8.0 | MIT | 1 |
| uvicorn | 0.54.0 | BSD-3-Clause | 1 |
| websockets | 17.2 | BSD-3-Clause | 1 |

## npm dependency inventory

| Lockfile package path | Version | Declared license |
|---|---|---|
| @alloc/quick-lru | 5.3.0 | MIT |
| @img/colour | 1.1.0 | MIT |
| @img/sharp-win32-x64 | 0.35.5 | Apache-2.0 AND LGPL-3.0-or-later |
| @jridgewell/gen-mapping | 0.3.13 | MIT |
| @jridgewell/remapping | 2.3.5 | MIT |
| @jridgewell/resolve-uri | 3.1.2 | MIT |
| @jridgewell/sourcemap-codec | 1.6.0 | MIT |
| @jridgewell/trace-mapping | 0.3.31 | MIT |
| @next/env | 16.3.8 | MIT |
| @next/swc-darwin-arm64 | 16.3.8 | MIT |
| @next/swc-darwin-x64 | 16.3.8 | MIT |
| @next/swc-linux-arm64-gnu | 16.3.8 | MIT |
| @next/swc-linux-arm64-musl | 16.3.8 | MIT |
| @next/swc-linux-x64-gnu | 16.3.8 | MIT |
| @next/swc-linux-x64-musl | 16.3.8 | MIT |
| @next/swc-win32-arm64-msvc | 16.3.8 | MIT |
| @next/swc-win32-x64-msvc | 16.3.8 | MIT |
| @swc/helpers | 0.5.23 | Apache-2.0 |
| @tailwindcss/node | 4.3.3 | MIT |
| @tailwindcss/oxide | 4.3.3 | MIT |
| @tailwindcss/oxide-android-arm64 | 4.3.3 | MIT |
| @tailwindcss/oxide-darwin-arm64 | 4.3.3 | MIT |
| @tailwindcss/oxide-darwin-x64 | 4.3.3 | MIT |
| @tailwindcss/oxide-freebsd-x64 | 4.3.3 | MIT |
| @tailwindcss/oxide-linux-arm-gnueabihf | 4.3.3 | MIT |
| @tailwindcss/oxide-linux-arm64-gnu | 4.3.3 | MIT |
| @tailwindcss/oxide-linux-arm64-musl | 4.3.3 | MIT |
| @tailwindcss/oxide-linux-x64-gnu | 4.3.3 | MIT |
| @tailwindcss/oxide-linux-x64-musl | 4.3.3 | MIT |
| @tailwindcss/oxide-wasm32-wasi | 4.3.3 | MIT |
| @tailwindcss/oxide-win32-arm64-msvc | 4.3.3 | MIT |
| @tailwindcss/oxide-win32-x64-msvc | 4.3.3 | MIT |
| @tailwindcss/postcss | 4.3.3 | MIT |
| @types/node | 24.19.2 | MIT |
| @types/react | 19.3.0 | MIT |
| @types/react-dom | 19.3.0 | MIT |
| baseline-browser-mapping | 2.11.28 | Apache-2.0 |
| caniuse-lite | 1.0.30001815 | CC-BY-4.0 |
| client-only | 0.0.1 | MIT |
| csstype | 3.2.3 | MIT |
| detect-libc | 2.1.2 | Apache-2.0 |
| enhanced-resolve | 5.26.0 | MIT |
| graceful-fs | 4.2.11 | ISC |
| jiti | 2.7.0 | MIT |
| lightningcss | 1.32.0 | MPL-2.0 |
| lightningcss-android-arm64 | 1.32.0 | MPL-2.0 |
| lightningcss-darwin-arm64 | 1.32.0 | MPL-2.0 |
| lightningcss-darwin-x64 | 1.32.0 | MPL-2.0 |
| lightningcss-freebsd-x64 | 1.32.0 | MPL-2.0 |
| lightningcss-linux-arm-gnueabihf | 1.32.0 | MPL-2.0 |
| lightningcss-linux-arm64-gnu | 1.32.0 | MPL-2.0 |
| lightningcss-linux-arm64-musl | 1.32.0 | MPL-2.0 |
| lightningcss-linux-x64-gnu | 1.32.0 | MPL-2.0 |
| lightningcss-linux-x64-musl | 1.32.0 | MPL-2.0 |
| lightningcss-win32-arm64-msvc | 1.32.0 | MPL-2.0 |
| lightningcss-win32-x64-msvc | 1.32.0 | MPL-2.0 |
| magic-string | 0.30.21 | MIT |
| nanoid | 3.3.20 | MIT |
| next | 16.3.8 | MIT |
| next/node_modules/postcss | 8.5.23 | MIT |
| picocolors | 1.1.1 | ISC |
| postcss | 8.5.29 | MIT |
| react | 19.3.0 | MIT |
| react-dom | 19.3.0 | MIT |
| scheduler | 0.28.0 | MIT |
| semver | 7.8.5 | ISC |
| sharp | 0.35.5 | Apache-2.0 |
| source-map-js | 1.2.2 | BSD-3-Clause |
| styled-jsx | 5.1.6 | MIT |
| tailwindcss | 4.3.3 | MIT |
| tapable | 2.3.3 | MIT |
| tslib | 2.8.1 | 0BSD |
| typescript | 5.9.3 | Apache-2.0 |
| undici-types | 7.24.6 | MIT |
