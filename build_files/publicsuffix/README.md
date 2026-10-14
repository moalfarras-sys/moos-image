# The Public Suffix List, as the Mo Store gate reads it

`public_suffix_list.dat` is Mozilla's [Public Suffix List](https://publicsuffix.org/): the names
under which different people own sites. Anyone can publish `<name>.github.io`, `<name>.co.uk` or
`<name>.notion.site`, so none of those three suffixes is one site, and a cookie, a permission or
a trusted window that spans one is shared with strangers.

`build_files/verify_store_catalog.py` uses it to refuse a web app host that is a public suffix,
and a `*.` wildcard whose base is one or that has a public suffix inside it. A web app's window
has no address bar and answers its hosts' permission requests with the person's decisions for
that app, so a `*.notion.site` host kept every Notion user's published page inside MoOS's Notion
window. The gate reads this copy, never the machine's: the CI runner, the image build container
and the station must give the same answer.

## This copy

| | |
|---|---|
| Source | https://publicsuffix.org/list/public_suffix_list.dat (the only URL the list's maintainers support) |
| Fetched | 2026-10-15 |
| List version | `VERSION: 2026-10-07_07-28-19_UTC`, `COMMIT: 3929462652695bad04f0a27afb600974014a3c8b` (the file's own header) |
| Size, SHA-256 | 335,478 bytes, `ba7d836c0ea57a8bcf9f1fcb868066a7554bed029b441ecc6204ad8494a32612` |
| Integrity at download | the server's MD5 (`x-goog-hash: md5=e6b7OQK7PNQPRW4oP5GC3A==`) matched the bytes |
| Changes | none: the file is byte for byte as published |

## Licence

The list is subject to the terms of the Mozilla Public License, v. 2.0 (MPL-2.0), as its own
header states; a copy of the licence is at https://mozilla.org/MPL/2.0/. It is kept unmodified
and with that header, and it is data for a build gate: `build_files/` is bind-mounted into the
image build and does not ship in the image.

## Refreshing it

```bash
curl -fsS -o build_files/publicsuffix/public_suffix_list.dat \
    https://publicsuffix.org/list/public_suffix_list.dat
head -12 build_files/publicsuffix/public_suffix_list.dat   # VERSION and COMMIT for the table above
sha256sum build_files/publicsuffix/public_suffix_list.dat
python3 tests/test_mo_store_catalog_gate.py
MOOS_TEST_ROOT=system_files python3 build_files/verify_store_catalog.py
```

Update the table. If a shipped web app is refused after a refresh, a publisher has registered one
of its hosts as a public suffix (it now hands those names to its users): change the catalogue
entry, never this list.
