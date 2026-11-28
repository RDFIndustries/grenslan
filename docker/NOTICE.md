# Notices for this image

Grenslan's own code is licensed under the Apache License 2.0 (`LICENSE`). Everything else in this image keeps its own licence. The notices for each component are in this directory:

| Path | Contents |
|---|---|
| `LICENSE` | Grenslan, Apache-2.0 |
| `python/grenslan/` | The licence files of every Python package in Grenslan's environment (`/opt/grenslan/venv`) |
| `python/searxng/` | The licence files of every Python package in SearXNG's environment (`/opt/grenslan/searxng/venv`) |
| `searxng/` | SearXNG's licence (AGPL-3.0-or-later) and `SOURCE`, which records the exact commit installed |
| `native/` | The licence files of the native libraries compiled into those packages (OpenSSL, curl and its libraries, BoringSSL, libxml2, libxslt, zlib, libidn2, GNU libiconv, libyaml, libffi) |
| `crates.txt` | The licence texts of the Rust crates compiled into those packages |

The base image (Debian and Python) carries its own notices: Debian packages in `/usr/share/doc/*/copyright`, and Python in `/usr/local/lib/python3.12/LICENSE.txt`.

Some of these components are licensed under the GNU AGPL, GPL or LGPL. Their full licence texts are included above:

| Licence | Where its text is |
|---|---|
| AGPL-3.0 | `searxng/LICENSE` |
| GPL-3.0 | `native/libidn2-2.3.7.tar.gz/COPYING` |
| LGPL-3.0 | `native/libidn2-2.3.7.tar.gz/COPYING.LESSERv3` |
| GPL-2.0 | `native/libidn2-2.3.7.tar.gz/COPYINGv2` |
| LGPL-2.1 | `native/libiconv-1.18.tar.gz/COPYING.LIB` |
| MPL-2.0 | `python/searxng/certifi-*/` |

## Source

SearXNG's complete source, at the commit recorded in `searxng/SOURCE`, is installed in `/opt/grenslan/searxng/src`.

When this image is distributed as a Grenslan release, the source of every component is published with that release on the project's GitHub Releases page (https://github.com/RDFIndustries/grenslan/releases), next to the image. That covers every Python package, every Rust crate and every native library compiled into them. This meets the source obligations of the AGPL and LGPL components and allows anyone to audit, modify or rebuild them.

Grenslan's own source is at https://github.com/RDFIndustries/grenslan. Running `packaging/searxng/fetch-sources.sh OUTDIR` there assembles the same source set for SearXNG's environment.

Anyone who distributes an image they built themselves takes on the same obligation for their copy.
