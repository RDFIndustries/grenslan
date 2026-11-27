# Discovery provider preflight: primary-source verification

- Date of research: 2026-11-26. Every source listed as "read 2026-11-26" was fetched live that day, through WebFetch, curl, the `gh` API or a headless browser (Playwright).
- Scope: read-only. No repository files were changed. Nothing user-identifying was sent to any provider: no email address, `mailto`, token or API key.
- Notation: **[doc]** means the primary documentation states it. **[src]** means read from the provider's own published source code or machine-readable spec. **[live]** means one anonymous observation against the live service. **[inference]** means the researcher's reasoning, not stated by the provider. **UNVERIFIED** means it could not be confirmed from a primary source.
- Facts were checked against the live primary pages rather than any locally indexed copy.

---

## 1. SearXNG

### Version and distribution
- **[doc]** The docs build is titled "SearXNG Documentation (2026.11.26+b5605b8f2)", which has the form `YYYY.MM.DD+<git short hash>`.
- **[live]** Docker Hub `searxng/searxng` tags, newest first: `latest` and `2026.11.26-b5605b8f2` (both 2026-11-26), then `2026.11.23-a7163d091`, `2026.11.21-c6ee3e9fd`, and several `2026.11.20-*` tags. Several builds can appear on one day.
  - **[live]** The GitHub repo has **no git tags and no GitHub Releases**: `gh api repos/searxng/searxng/tags` returned `[]`.
  - **[inference]** Every commit on `master` is effectively a release. Pin by the full date-hash tag, ideally also by image digest, and never by `latest`.
- **[doc]** Images are on Docker Hub (`docker.io/searxng/searxng`) with a GHCR mirror (`ghcr.io/searxng/searxng`). The docs note that Docker Hub rate-limits unauthenticated pulls.
- **[doc]** Container settings and paths:
  - Config: `/etc/searxng` (holds `settings.yml`).
  - Persistent cache: `/var/cache/searxng` (e.g. `faviconcache.db`).
  - Environment variables: `$SEARXNG_*`, `$GRANIAN_*` and `$FORCE_OWNERSHIP` (default true).
- **[src]** `searx/version.py` holds the placeholders `VERSION_STRING`, `DOCKER_TAG`, `GIT_URL` and `GIT_BRANCH`, derived from git at build time.

### Running as a plain process
- **[doc]** Step-by-step install:
  1. Clone `https://github.com/searxng/searxng` into `/usr/local/searxng/searxng-src`.
  2. Create a venv with `python3 -m venv`.
  3. `pip install pyyaml msgspec typing-extensions pybind11`.
  4. `pip install --use-pep517 --no-build-isolation -e .`
  5. Set `SEARXNG_SETTINGS_PATH`. Check with `python -m searx.webapp`.
- **[doc]** Granian page: "Granian will be the future replacement for uWSGI in SearXNG. At the moment, it's only officially supported in the Installation container."
  - Install with `pip install granian`. Configure through `GRANIAN_*` env vars or CLI flags.
  - The docs advise against changing the worker count, because it causes Bot Detection problems.
  - uWSGI is not marked deprecated, and its guide is still linked.
- **[inference]** Our options:
  - Run SearXNG as a supervised process inside the primary container (AGENTS.md reference deployment). Granian is the current, container-supported server, but outside the official container it is "not officially supported".
  - uWSGI is the documented non-container path.
  - This is a choice for the maintainer.
- **[doc]** No minimum Python version is stated on the install page. Only an example `Python 3.11.10` appears. **UNVERIFIED:** minimum Python version.

### JSON API
- **[doc]** Endpoints are `GET /`, `GET /search`, `POST /` and `POST /search`. POST takes `application/x-www-form-urlencoded`.
- **[doc]** Parameters:

  | Parameter | Description |
  |---|---|
  | `q` | Required. |
  | `categories` | Comma-separated. |
  | `language` | Default comes from `search:` settings. |
  | `pageno` | Default 1. |
  | `time_range` | Docs list `day`, `month`, `year`. |
  | `format` | `json`, `csv` or `rss`. A format that is not enabled returns **403**. |
  | `safesearch` | `0`, `1` or `2`. |
  | `theme` | Theme name. |

- **[src]** Parsing in `searx/webadapter.py`:
  - `time_range` also accepts **`week`** (`None, 'day', 'week', 'month', 'year'`). The docs omit it.
  - `pageno` must be a digit and at least 1.
  - `safesearch` must be 0–2 and can be locked by preferences.
  - `timeout_limit` is accepted as a float.
  - **`engines`** is a comma-separated list. Unknown engine names are **silently dropped**. If both `engines` and `categories` are given, the engines of those categories are added. Categories can be locked in config.
  - Invalid values raise `SearxParameterException`.
- **[doc]** `settings.yml` → `search.formats`: "remove format to deny access". The shipped default enables only `html`, so `json` **must be added explicitly**.
- **[src]** Shipped defaults in `searx/settings.yml`:
  - `server.limiter: false` (env `SEARXNG_LIMITER`)
  - `server.public_instance: false`
  - `bind_address: "127.0.0.1"`, `port: 8888`
  - `secret_key: "ultrasecretkey"` (overridden by `SEARXNG_SECRET`; must be replaced)
  - `general.enable_metrics: true`
  - `search.autocomplete` defaults to `duckduckgo` per the docs. It is a backend that sends traffic outbound; set it blank to disable.
- **[src]** JSON response body (`searx/webutils.py: get_json_response`) has these keys: `query`, `results`, `answers`, `corrections`, `infoboxes`, `suggestions`, `unresponsive_engines` (a list of translated errors).
- **[src]** Fields on each result (`searx/result_types/_base.py`):
  - From `Result`: `url`, `engine` (with prefix `plugin:` or `answerer:` for those producers), `parsed_url`.
  - From `MainResult`:
    - Display and media: `template`, `title`, `content` (the snippet), `img_src`, `iframe_src`, `audio_src`, `thumbnail`.
    - Dates and metadata: `publishedDate` (datetime, ISO in JSON), `pubdate` (deprecated string), `length`, `views`, `author`, `metadata`.
    - Ranking and attribution: `priority`, **`engines`** (the set of engines that found the merged result), **`positions`** (a list of int ranks, one per engine hit), **`score`** (float), `category`, `open_group`, `close_group`.
  - Some engines still emit `LegacyResult` dicts. **[inference]** Expect engine-specific extra keys, and parse tolerantly.
- **[src]** Score (`searx/results.py: calculate_score`):
  - `weight` is the product of the configured engine `weight`s × `len(positions)`.
  - `score` is the sum over positions of `weight/position`.
  - `priority=high` adds `weight`; `priority=low` adds 0.
  - **[inference]** This is transparent rank-based fusion. Engine `weight` settings are operator-controlled ranking bias, so the AGENTS.md "no source-trust bias" rule means leaving weights at their default of 1 unless the maintainer approves.
- **UNVERIFIED (docs):** No official docs page describes the JSON response shape. The above comes from source only.

### Limiter and bot detection (trusted internal caller)
- **[doc]** The limiter is "Bot protection / IP rate limitation".
  - It is enabled by `server.limiter: true` and **requires a Valkey database** (`valkey.url`).
  - It is configured in `limiter.toml`:
    - `pass_ip`: unrestricted access, e.g. `192.168.0.0/16`.
    - `block_ip`.
    - `pass_searxng_org`.
    - `[botdetection.ip_limit] link_token`.
    - `filter_link_local`: by default, link-local networks are not monitored.
- **[doc]** Client IP comes from `X-Forwarded-For` / `X-Real-IP` **only if** the peer is in `trusted_proxies`. Loopback (`127.0.0.0/8`, `::1`) is trusted by default.
- **[inference]** For a private, internal-only instance called only by Grenslan, leave `limiter: false`, which is the default and needs no Valkey. Alternatively, enable it with `pass_ip` covering only the Grenslan caller.
  - Because loopback is a default trusted proxy, a loopback caller could set `X-Forwarded-For`. Grenslan should never forward consumer-supplied forwarding headers to SearXNG.

### License and corresponding source
- **[live]** GitHub reports the license as `AGPL-3.0`. **[src]** The `LICENSE` file starts "GNU AFFERO GENERAL PUBLIC LICENSE Version 3, 19 November 2007".
- Source is published at `https://github.com/searxng/searxng` (branch `master`).
- **[doc]** The brand settings (`docs_url`, `wiki_url`, `issue_url`, `new_issue_url`, `public_instances`, `custom.links`) have **no** explicit "source code" / `git_url` setting.
- **[inference]** Each image tag encodes a commit hash, so corresponding source for a bundled build is `github.com/searxng/searxng/tree/<hash>`. Grenslan should also archive or mirror that exact source, or offer it, to meet AGPL §13/§6 obligations. **UNVERIFIED:** how SearXNG's UI exposes the source link (`GIT_URL`) for modified builds.

### Restricted or offline deployment
- **[inference]** SearXNG is a metasearch proxy. Every search makes outbound requests to the configured third-party engines, and those requests must go through Grenslan's egress policy.
  - Outbound defaults: `autocomplete: duckduckgo`, favicon fetching and the default engine list.
  - In an air-gapped deployment SearXNG returns `unresponsive_engines`, not results. That must surface as "unavailable", not as an empty success.
- Docker Hub pull rate limits apply to unauthenticated pulls; GHCR is the documented mirror.

### Sources (all read 2026-11-26)
- https://docs.searxng.org/dev/search_api.html
- https://docs.searxng.org/admin/settings/settings_search.html
- https://docs.searxng.org/admin/searx.limiter.html
- https://docs.searxng.org/admin/installation-docker.html
- https://docs.searxng.org/admin/installation-searxng.html
- https://docs.searxng.org/admin/installation-granian.html
- https://docs.searxng.org/admin/settings/settings_brand.html
- Source on master as of 2026-11-26: `searx/webutils.py`, `searx/webadapter.py`, `searx/results.py`, `searx/result_types/_base.py`, `searx/settings.yml`, `searx/version.py`, `LICENSE` (raw.githubusercontent.com/searxng/searxng/master/...)
- https://hub.docker.com/v2/repositories/searxng/searxng/tags (live tag listing); GitHub API `repos/searxng/searxng`, `/tags`, `/releases`

---

## 2. arXiv API

### Endpoint
- **[doc]** The manual gives the base URL as `http://export.arxiv.org/api/query`, and one example uses `https://export.arxiv.org/api/query`.
- **[live]** `https://export.arxiv.org/api/query?search_query=all:electron&max_results=1` returned 200 over HTTPS (one request).
- **[inference]** Use HTTPS with certificate validation.
- The API is unversioned. The ToU calls it the "legacy arXiv API".

### Parameters
- **[doc]** Parameters:

  | Parameter | Description |
  |---|---|
  | `search_query` | Search query. |
  | `id_list` | Comma-delimited IDs. |
  | `start` | 0-based. |
  | `max_results` | Default 10. |
  | `sortBy` | `relevance`, `lastUpdatedDate` or `submittedDate`. |
  | `sortOrder` | `ascending` or `descending`. |

- **[doc]** Limits:
  - At most **2000 results per call** and **30000 total**. `max_results` above 30000 returns HTTP 400.
  - Refine queries that return more than 1000 results. Use OAI-PMH for bulk.
- **[doc]** Field prefixes: `ti`, `au`, `abs`, `co`, `jr`, `cat`, `rn`, `id` (use `id_list` instead) and `all`.
- **[doc]** Operators are `AND`, `OR` and `ANDNOT`. Group with `%28 %29`; quote phrases with `%22`.
- **[doc]** Date range syntax: `submittedDate:[YYYYMMDDTTTT+TO+YYYYMMDDTTTT]`, in GMT.

### Response (Atom 1.0 + OpenSearch + arxiv namespace)
- **[doc]** Feed level: `title`, `id`, `link rel=self`, `updated`, `opensearch:totalResults`, `opensearch:startIndex`, `opensearch:itemsPerPage`.
- **[doc]** Entry level:
  - Identity and text: `id` (the abs URL), `title`, `summary`.
  - Dates: `published`, `updated`.
  - People: `author/name`, `arxiv:affiliation`.
  - Links: `link rel=alternate` (abs page) and `link rel=related title=pdf`.
  - Classification and extras: `category`, `arxiv:primary_category`, `arxiv:comment`, `arxiv:journal_ref`, `arxiv:doi`.
- **[doc]** Errors come back as an Atom feed with a single entry. The `summary` holds the message and the `link` points to the explanation.
  - **[inference]** An HTTP 200 can still carry an error, so detect the error entry explicitly.
- **[doc]** Results update on a 24-hour cycle, so cache results and don't repeat the same query more than once a day.

### Authentication
- **[doc]** The ToU mentions no API key or registration. It forbids using someone else's credentials.

### Rate limits
- **[doc]** ToU: "make no more than one request every three seconds, and limit requests to a single connection at a time."
  - The limit applies to all machines under your control as a whole.
  - Do not add machines to get around it. Limits may change.
  - The user manual also says to "incorporate a 3 second delay".
- **UNVERIFIED:** whether arXiv sends `Retry-After` or 429/503 on overload. No primary doc states it.

### Terms, attribution and license
- **[doc]** Descriptive metadata (title, abstract, authors, identifiers, classification) is **CC0 1.0**.
- **[doc]** E-prints are copyrighted. Do **not** store and serve e-prints (PDF/source) without permission from the copyright holder or license. Linking users to arXiv.org is encouraged, abstract pages in particular.
- **[doc]** Do not represent the project as endorsed by arXiv, and do not brand it with arXiv names, logos or colors.
- **[doc]** The API index page asks every API user to show the statement "Thank you to arXiv for use of its open access interoperability." on the product. It is phrased as a request ("we do request"), while the ToU page itself contains no attribution clause.
- **[doc]** Commercial projects should review the brand guidelines and consider becoming an affiliate.
- **[inference]** This affects Grenslan's artifact cache and delivery of arXiv PDFs. Retrieval for a consumer is "personal/research use"? That is ambiguous for a multi-user service, so it is a maintainer and legal question.

### Sources (all read 2026-11-26)
- https://info.arxiv.org/help/api/index.html
- https://info.arxiv.org/help/api/user-manual.html
- https://info.arxiv.org/help/api/tou.html

---

## 3. Crossref REST API

### Endpoint and version
- **[doc]** Base URL is `https://api.crossref.org/`. No sign-up is required.
- **[live]** The live Swagger spec at `https://api.crossref.org/swagger-docs` reports **version `4.11.3`** (swagger 2.0).
- **[doc]** The `CrossRef/rest-api-doc` GitHub README carries a **DEPRECATION NOTICE**. The API moved from Solr to Elasticsearch, and the current docs are at api.crossref.org.
  - The README was used only where the current Swagger agrees with it, or I flagged it.
- **[doc]** Responses are JSON with MIME type `application/vnd.crossref-api-message+json`. The envelope is `status`, `message-type`, `message-version`, `message`.

### /works parameters (live Swagger)
- **[doc]** Parameters:
  - `query` and field queries. Field queries from the README: `query.bibliographic`, `query.author`, `query.container-title`, `query.editor`, `query.chair`, `query.translator`, `query.contributor`, `query.affiliation`. `query.title` is removed.
  - `filter` (comma-separated `name:value`; the full list is on the filters page).
  - `rows`, `offset`, `cursor`, `sort`, `order` (`asc`, or `desc` as default), `select`, `facet`, `sample`, `mailto`.
- **[doc]** Limits:
  - `rows` defaults to 20, maximum **1000**.
  - **`offset` up to 10,000.** Beyond that, use the cursor.
  - Cursor: start with `cursor=*` (and rows > 0), then follow `next-cursor`. Stop when items < rows. **Cursors expire after 5 minutes of non-use.**
  - `offset` and `sample` cannot be combined with a cursor (README).
  - `sample` maximum is 100 (README).
  - Facet values: up to 1000.
- **[doc]** Sort values (README; the current Swagger defers to the docs):
  - `score`/`relevance`, `updated`, `deposited`, `indexed`, `published`, `published-print`, `published-online`, `issued`, `is-referenced-by-count`, `references-count`.
  - With a query, the default is relevance. Without one, it is DOI update date.
  - **UNVERIFIED:** that this exact sort list is current. The live Swagger only says "See Sorting".

### Response fields (live Swagger `Work` definition)
- Required fields: `DOI`, `URL`, `type`, `publisher`, `prefix`, `member`, `source`, `score`, `resource`, `issued`, `created`, `deposited`, `indexed`.
- Useful optional fields:
  - Titles and venue: `title` (array), `subtitle`, `short-title`, `container-title`.
  - People: `author` (given, family, ORCID, affiliation), `editor`.
  - Text and dates: `abstract` (JATS XML string), `published`, `published-print`, `published-online`.
  - Identifiers: `ISSN`, `ISBN`.
  - Links and rights: `link`, `license`, `subject`.
  - Counts and relations: `is-referenced-by-count`, `references-count`, `relation`, `update-to`, `updated-by`.
  - Other: `language`, `alternative-id`.
- `score` is the relevance score.

### Pools, authentication and rate limits (Access & authentication page, "Last updated: 2025-October-16")
- **[doc]** Pools:
  - **Public:** no identification.
  - **Polite:** email in the `mailto` parameter or the `agent` header. Best practice also recommends an identifying `User-Agent`.
  - **Metadata Plus:** paid; header `crossref-api-key: Bearer [API key]`.
- **[doc]** Limits:

  | Pool | Request type | Rate limit (req/s) | Concurrency |
  |---|---|---|---|
  | Public | DOI lookup | 5 | 1 |
  | Public | Lists (filters/queries) | 1 | 1 |
  | Polite | DOI lookup | 10 | 3 |
  | Polite | Lists (filters/queries) | 3 | 3 |
  | Plus | All requests | 150 | no limit |

- **[doc]** Headers: `x-rate-limit-limit`, `x-rate-limit-interval`, `x-concurrency-limit`. On Plus, `x-api-pool: plus`.
  - Exceeding the limit returns **429**: wait, then retry slower or with less concurrency.
  - Blocks return **403**. They are usually automatic and temporary.
  - The Swagger text says "429 or 403 ... temporarily or permanently blocked, check the response text".
- **UNVERIFIED:** whether Crossref sends `Retry-After`. No primary doc mentions it.
- **[inference]** A polite-pool `mailto` is operator-supplied configuration. It must not come from consumer identity (privacy and AGENTS.md).

### Terms and license
- **[doc]** "almost none of the metadata is subject to copyright"; metadata may be used for any purpose. **Abstracts may be copyrighted** by publishers or authors.
- No CC0 or other specific metadata license is named on the page read. The site's own content is CC BY 4.0.
- **[doc]** Etiquette: cache results, prefer filters over per-DOI calls, use `select`, back off on 429.

### Sources (all read 2026-11-26)
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- https://api.crossref.org/swagger-docs (live spec v4.11.3)
- https://github.com/CrossRef/rest-api-doc (README, deprecated; raw master)

---

## 4. PubMed via NCBI E-utilities

**Access note:** www.ncbi.nlm.nih.gov serves a reCAPTCHA "Checking your browser" interstitial to curl and WebFetch. The pages were read through a headless browser (Playwright) after the challenge redirected.
- **[inference]** This affects only documentation pages. The `eutils.ncbi.nlm.nih.gov` API host was not tested here.

### Endpoints
- **[doc]** All requests go to `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` (HTTPS):
  - `esearch.fcgi`
  - `esummary.fcgi`
  - `efetch.fcgi`
  - also `epost.fcgi`, `elink`, `espell`, `ecitmatch`
- The utilities are unversioned. ESummary has an optional `version=2.0` DocSum XML.
- NBK25497 last update: November 17, 2022. NBK25499 last update: March 4, 2026.

### ESearch
- **[doc]** `db` (default pubmed) and `term` (URL-encoded; use POST for very long queries).
- **[doc]** History server: `usehistory=y` returns `WebEnv` and `query_key`. Results can be appended or intersected through `WebEnv` and `query_key`.
- **[doc]** Retrieval:
  - `retstart` (default 0) and `retmax` (default 20, **maximum 10,000**).
  - **For PubMed and PMC, ESearch can only retrieve the first 10,000 records of a query.** Segment by date, or use EDirect.
  - `rettype`: `uilist` or `count`.
  - `retmode`: `xml` (default) or `json`.
  - `sort` for PubMed: `pub_date`, `Author`, `JournalName`, `relevance` ("Best Match"). The default sort varies by database.
  - `field`.
- **[doc]** Dates: `datetype` (`mdat`/`pdat`/`edat`), `reldate` (last n days), and `mindate` + `maxdate` (always together; `YYYY[/MM[/DD]]`).
- **[doc]** The web PubMed spelling correction and citation matching are not in ESearch; use ESpell or ECitMatch.

### ESummary / EFetch
- **[doc]** ESummary:
  - `id` is a comma list. There is no set maximum, but use POST above about 200 IDs. Alternatively, pass `query_key` + `WebEnv`.
  - `retstart` (default **1** for ESummary) and `retmax` (maximum 10,000).
  - `retmode`: `xml` or `json`.
  - `version=2.0`.
- **[doc]** EFetch:
  - `id` or history input. Use POST above about 200 IDs.
  - `retstart` (default 0) and `retmax` (maximum 10,000).
  - PubMed `rettype`/`retmode` values (Table 1):
    - XML: `rettype` null, `retmode` `xml` (default).
    - MEDLINE: `medline` / `text`.
    - PMID list: `uilist` / `text`.
    - Abstract: `abstract` / `text`.
- **UNVERIFIED:** field-level detail of the PubMed XML or DocSum JSON (title, authors, dates, DOI, PMCID locations). Not checked in a primary DTD or doc today.

### Authentication, identification and rate limits
- **[doc]** Without an API key, more than **3 requests/second** per site (IP) gets an error. With `api_key`, **10 requests/second** by default; higher rates are available on request.
  - The key comes from the NCBI account settings and is passed as the `api_key` parameter.
  - One key per account; requesting a new one invalidates the old one.
  - Example over-limit body: `{"error":"API rate limit exceeded","count":"11"}`.
- **[doc]** Run large jobs on weekends or 9 PM–5 AM US Eastern on weekdays.
- **[doc]** `tool` (no spaces) and `email` (the developer's, **not a third-party end user's**) parameters:
  - Non-compliant IPs may be blocked. A block is lifted only after tool and email are registered (by emailing eutilities@ncbi.nlm.nih.gov).
  - Merely sending the values is "not sufficient"; they must be registered.
  - Once registered, all requests should include both.
- **[inference]** The key is optional but recommended. `tool` and `email` are operator-level configuration, never per-consumer.
- **UNVERIFIED:** the HTTP status code returned on rate-limit errors (e.g. 429) and whether `Retry-After` is sent. The docs show only the JSON body.

### Terms, disclaimer and attribution
- **[doc]** Software using E-utilities must make **NCBI's Disclaimer and Copyright notice evident to users**: https://www.ncbi.nlm.nih.gov/About/disclaimer.html, which now redirects to https://www.ncbi.nlm.nih.gov/home/about/policies/.
- **[doc]** PubMed abstracts may be copyrighted. Reproduction beyond fair use needs the copyright owner's permission.
- **[doc]** For large data mining, download the PubMed/MEDLINE baseline instead (https://www.nlm.nih.gov/databases/download/pubmed_medline.html).
- **[doc]** Policies page: US-government-created information is public domain, and NLM asks to be given "appropriate acknowledgment". Material contributed by third parties (PMC, Bookshelf, OMIM, PubChem) may be copyrighted.

### Sources (read 2026-11-26 via browser)
- https://www.ncbi.nlm.nih.gov/books/NBK25497/ (General Introduction: usage guidelines, API keys, disclaimer)
- https://www.ncbi.nlm.nih.gov/books/NBK25499/ (In-Depth: ESearch/ESummary/EFetch parameters) and its Table 1: https://www.ncbi.nlm.nih.gov/books/NBK25499/table/chapter4.T._valid_values_of__retmode_and/?report=objectonly
- https://www.ncbi.nlm.nih.gov/home/about/policies/ (redirect target of About/disclaimer.html)
- NBK25501 (book index) was requested but only the captcha page was retrieved; nothing in this report depends on it.

---

## 5. OpenAlex

**Untrusted-content note:** `llms.txt` and the Authentication page contain instructions aimed at AI agents, e.g. "ask the user for their email" and `POST /api-keys` to provision a key for the user. They were treated as data and **not** acted on.
- **[inference]** Grenslan must not provision provider credentials automatically. The key is operator configuration.

### Endpoint
- **[doc]** `https://api.openalex.org/works`. A single record is `/works/{id}`, where the ID is also a URL like https://openalex.org/W….
- **[doc]** `POST /` accepts OQL in a JSON body for queries longer than the GET URL limit of **8,190 bytes**.
- The API path is not versioned. A deprecations page tracks field removals; examples include `volume` removed 2026-11-14 and `/relationships` renamed, with removal from works on 2026-12-07.

### Search, filter and sort
- **[doc]** Search parameters:
  - `search=`: works match title, alternate_titles, abstract, fulltext (~60M works with `has_fulltext:true`) and keywords.
  - Scoped: `search.title`, `search.title_and_abstract`, `search.title_abstract_keywords`, each with an `.exact` variant.
  - `search.semantic` cannot be combined with other searches.
  - Boolean `AND`/`OR`/`NOT` (uppercase) and quoted phrases. A leading minus sign does **not** exclude.
- **[doc]** `filter=attr:val,attr2:val2`:
  - Comma means AND, `|` means OR (up to **100** values per filter), `!` negates, `<`/`>` compare.
  - Convenience filters include `from_publication_date` and `to_publication_date`.
  - Filters are case-insensitive.
- **[doc]** `sort=field[:desc]`. Ascending is the default.
  - Fields include `display_name`, `cited_by_count`, `works_count`, `publication_date`, `relevance_score` (only with a search; otherwise an error).
  - Search results default to `relevance_score` descending.
  - Sorting works by `created_date`/`updated_date` needs a Member+/Partner plan.
- **[doc]** `relevance_score` combines text similarity, a **capped citation-count boost** (at most +50%) and a keyword bonus.
  - `rerank=true` reorders the top 100 using a "decision model" and costs extra.
  - **[inference]** Both matter under the AGENTS.md ranking rules: the citation boost is a popularity signal inside the provider's ordering, and rerank is model-based. Preserve the provider ordering as-is, label it, and do not enable `rerank` by default.
- **[doc]** `select=` limits returned fields. `sample` maximum is 10,000.

### Paging
- **[doc]** `page` (default 1) and `per_page` (default 25, **maximum 100**). `per_page=200` is still accepted as legacy behavior but is deprecated.
  - Basic paging is capped at **page × per_page ≤ 10,000**.
- **[doc]** Cursor paging: `cursor=*`, then `meta.next_cursor`, until `null`.
  - **It needs an API key past the first page**: without a key, following `next_cursor` returns **401**.
  - Don't use cursors to download the whole dataset; use the snapshot.

### Response fields
- **[doc]** The response has `meta` (`count`, `per_page`, `next_cursor`, cost information, `x_query.oql`, `reranked`) and `results`.
- **[doc]** Works attributes include:
  - Identity and text: `id`, `ids`, `doi`, `display_name`, `title`, `type`, `language`, `abstract_inverted_index` (the abstract is an inverted index, not plain text).
  - Dates: `publication_date`, `publication_year`.
  - Authorship: `authorships`, `is_authors_truncated`.
  - Locations and access: `primary_location`, `locations`, `best_oa_location`, `open_access`.
  - Classification: `primary_topic`, `topics`, `keywords`.
  - Citations: `cited_by_count`, `referenced_works`, `related_works`.
  - Status and housekeeping: `is_retracted`, `has_fulltext`, `content_urls`, `created_date`, `updated_date`.
  - Search results add `relevance_score` (and `rerank_score` when reranked).

### Authentication, pricing and rate limits (current; changed during 2026)
- **[doc]** **The polite pool is gone.** "Before February 2026, OpenAlex used a 'polite pool' ... This system has been replaced by API keys. The `mailto` parameter is ignored."
- **[doc]** Keys are free (account sign-up with a verified email).
  - Send as `api_key=` or `Authorization: Bearer <key>`.
  - Keyless use still works but has a smaller budget.
- **[doc]** Usage-based daily budget in USD, reset at midnight UTC:
  - No key: **$0.10/day**.
  - Free key: **$1/day**. New accounts are paced at $0.10 per 5 minutes until the first $1 is spent; this does not apply to accounts made before 2026-11-03.
  - Prepaid: $1 increments, expiring 3 months after the last purchase.
  - Annual plans: Member $5,000/yr ($20/day), Member+ $10,000/yr ($100/day), Partner from $20,000/yr ($200+/day).
- **[doc]** Costs per call:

  | Call type | Cost |
  |---|---|
  | Singleton | free |
  | List/filter | $0.0001 |
  | Search (incl. `.search` filters) | **$0.001** |
  | Rerank | +$0.001 |
  | PDF download | $0.01 |
  | Error responses (4xx/5xx) | free |

  - "$1/day ≈ 1,000 searches". **[inference]** That makes keyless about 100 searches/day per IP.
- **[doc]** Per-second limits:

  | Request kind | No key (per IP) | Free key / prepaid | Member | Member+ / Partner |
  |---|---|---|---|---|
  | All requests | 10 | 30 | 50 | 50 |
  | Searches with >5 boolean operators | 1 | 2 | 2 | 5 |
  | Wide OR filters on topics/concepts | 1 | 1 | 1 | 1 |
  | Semantic search | 1 | 1 | 1 | 1 |

  - "Until 27 June 2026 every caller could send 100 requests per second; older copies of these docs say 100."
- **[doc]** 429 responses:
  - The body carries `reason` (`requests_per_second`, `broad_boolean_query`, `wide_or_filter`, `semantic_search`, `daily_budget`) and `perSecondLimit`.
  - **Wait `Retry-After` seconds** (usually 1).
  - `not_enough_credits` means the budget is spent before the query runs.
  - A key that is not yet activated gets 403 `key_not_activated`.
  - Usage headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Credits-Used`, `X-RateLimit-Reset` (seconds to midnight UTC).
  - `GET /rate-limit` is free.

### License
- **[doc]** "Every record is released under a CC0 public-domain license". A free full snapshot is refreshed quarterly; daily sync is a paid Member+ feature.
- **[inference]** For restricted deployments, the snapshot is a lawful offline option, but it is large and out of scope for a discovery adapter.

### Sources (all read 2026-11-26; `.md` siblings fetched)
- https://help.openalex.org/llms.txt
- https://help.openalex.org/api/authentication.md
- https://help.openalex.org/api/paging.md
- https://help.openalex.org/api/searching.md
- https://help.openalex.org/api/sorting.md
- https://help.openalex.org/api/filtering.md
- https://help.openalex.org/api/errors.md
- https://help.openalex.org/api/deprecations.md
- https://help.openalex.org/api/llm-quick-reference.md
- https://help.openalex.org/access/pricing.md
- https://help.openalex.org/access/example-costs.md
- https://help.openalex.org/access/snapshot.md
- https://help.openalex.org/data/works/attributes.md

---

## 6. GitHub REST search API

### Endpoints and version
- **[doc]** Search endpoints: `GET /search/code`, `/search/commits`, `/search/issues`, `/search/labels`, `/search/repositories`, `/search/topics`, `/search/users` on `https://api.github.com`.
- **[doc]** Supported API versions: **`2026-03-10`** (newest; no end date scheduled) and `2022-11-28` (supported until **March 10, 2028**).
  - **Requests without `X-GitHub-Api-Version` default to `2022-11-28`.**
  - Versions are supported for 24 months after a newer one is released.
  - The search reference examples use `X-GitHub-Api-Version: 2026-03-10`.
  - **[inference]** Pin `2026-03-10` explicitly.
- **[doc]** Headers:
  - `Accept: application/vnd.github+json` is recommended.
  - **A valid `User-Agent` is required**; a missing or invalid one returns 403.
  - Text-match fragments: `Accept: application/vnd.github.text-match+json`, which adds `text_matches`.
  - Auth: `Authorization: Bearer <token>` (PAT, GitHub App or GITHUB_TOKEN).

### Parameters and limits
- **[doc]** `q` (required), `sort`, `order` (`desc` by default; ignored without `sort`), `per_page` (default 30, **maximum 100**) and `page` (default 1).
- **[doc]** At most **1,000 results per search**.
- **[doc]** Queries are limited to 256 characters (excluding operators and qualifiers) and at most five `AND`/`OR`/`NOT` operators.
- **[doc]** Sort values:
  - Repositories: `stars`, `forks`, `help-wanted-issues`, `updated`.
  - Code: only `indexed`, and code `sort`/`order` is marked "closing down".
  - Issues: `comments`, `reactions`, reaction variants, `interactions`, `created`, `updated`. The default is best match.
- **[doc]** Issues search also has:
  - `advanced_search` ("Set to true to use advanced search").
  - `search_type` (`semantic`/`hybrid`; lexical is the default). Semantic and hybrid need auth and are limited to 10/min.
  - With a GitHub App user token, queries without `is:issue` or `is:pull-request` return 422.
- **[doc]** A timeout sets `incomplete_results: true`, but a timeout "does not necessarily mean that search results are incomplete".
  - **[inference]** Surface this as "partial".
- **[doc]** Accessing repositories without permission returns 422 "Validation Failed". Results silently omit resources you cannot access.

### Response fields
- **[doc]** The body has `total_count`, `incomplete_results` and `items[]`.
  - Repository items: `name`, `full_name`, `html_url`, `description`, `score`, …
  - Code items: `name`, `path`, `html_url`, `score`, `repository{full_name, …}`, plus `text_matches` with the text-match media type.

### Authentication and rate limits
- **[doc]** Search limits:
  - Authenticated: **30 requests/minute** for all search endpoints except code search.
  - **Code search requires authentication**: 10 requests/minute.
  - Unauthenticated: **10 requests/minute**.
- **[live]** Anonymous `GET /rate_limit` returned `search.limit=10`, `core.limit=60`, and `code_search.limit=60` (a separate resource).
  - The anonymous `code_search` bucket contradicts or supplements the docs' auth requirement. Treat code search as auth-required, per the docs.
- **[doc]** Primary limits: unauthenticated 60/hour per IP; authenticated user 5,000/hour; GitHub App installation 5,000/hour, scaling up to 12,500; GITHUB_TOKEN 1,000/hour per repository.
- **[doc]** Secondary limits: at most 100 concurrent requests, 900 points/minute for REST, 90 seconds of CPU per 60 seconds, and 80 content-creating requests/minute.
- **[doc]** Headers: `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-used`, `x-ratelimit-reset` (UTC epoch seconds), `x-ratelimit-resource`.
- **[doc]** When a primary limit is exceeded: 403 or 429 with `x-ratelimit-remaining: 0`. Don't retry before `x-ratelimit-reset`.
- **[doc]** When a secondary limit is exceeded: 403 or 429.
  - If `retry-after` is present, wait that many seconds.
  - Else, if remaining is 0, wait until reset.
  - Else, wait at least one minute.
  - Then back off exponentially.

### Terms
- **UNVERIFIED:** GitHub Terms of Service / API terms and acceptable-use policy (e.g. limits on scraping, how search results may be redistributed). Not read today.
- **[inference]** Code content is licensed per repository and is not covered by any GitHub data license.

### Sources (all read 2026-11-26)
- https://docs.github.com/en/rest/search/search
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- https://docs.github.com/en/rest/about-the-rest-api/api-versions
- https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api
- https://api.github.com/rate_limit (one anonymous live call)

---

## Cross-provider notes for Grenslan [inference]
- Every provider except SearXNG is a hosted external service. In a restricted or offline deployment they must report **unavailable**, not empty. Egress allowlist hosts:
  - `export.arxiv.org`
  - `api.crossref.org`
  - `eutils.ncbi.nlm.nih.gov`
  - `api.openalex.org`
  - `api.github.com`
- SearXNG's own engines need further egress.
- Credentials and identifiers are all optional, and all of them are operator-level settings. Never derive them from consumer identity:
  - Crossref `mailto` / Plus key
  - NCBI `api_key`, `tool`, `email`
  - OpenAlex `api_key`
  - GitHub token
- OpenAlex is the only provider where a key changes **functionality** (cursor paging) and not just throughput. GitHub code search requires a token.
- `Retry-After`: documented for OpenAlex and GitHub (secondary limits). Not documented for Crossref, NCBI or arXiv. Plan client-side pacing instead:
  - arXiv: 1 request per 3 seconds on a single connection.
  - NCBI: 3/s or 10/s.
  - Crossref: 1/s and concurrency 1 for public list queries; 3/s and 3 concurrent when polite.
- Attribution or notice obligations:
  - arXiv: requested acknowledgement statement.
  - NCBI: disclaimer must be evident.
  - NLM: acknowledgment requested.
  - OpenAlex: CC0, with a citation suggestion on the help site.
  - Crossref: metadata essentially uncopyrightable, abstracts excepted.
- Full-text and abstract copyright cautions: arXiv e-prints, PubMed abstracts and Crossref abstracts.

## Open questions / UNVERIFIED
1. SearXNG: no official doc for the JSON response schema (taken from source only). The `week` value for `time_range` is in code but not docs. Minimum Python version not stated. How the UI exposes the AGPL source link for builds is unconfirmed.
2. SearXNG: Granian is "officially supported" only in the official container. For a plain process in our container, Granian or uWSGI is a maintainer decision.
3. arXiv: whether 429/503 or `Retry-After` is returned on overload. Whether delivering or caching arXiv PDFs for consumers is permitted, since the ToU forbids serving e-prints.
4. Crossref: whether `Retry-After` is sent. Whether the README's sort-value list and `sample` maximum of 100 are still current, since that doc is deprecated and Swagger defers. No named metadata license (only "almost none ... subject to copyright").
5. NCBI: the HTTP status and `Retry-After` behavior on rate-limit errors. PubMed XML/JSON field mapping (not verified against the DTD). Doc pages are captcha-gated for non-browser clients.
6. OpenAlex: pricing is new (2026) and changing quickly (per-second limits cut on 2026-06-27; new-account pacing from 2026-11-03). Re-verify before release. Whether citation-boosted `relevance_score` is acceptable under the ranking rules is a maintainer review item.
7. GitHub: the API ToS and acceptable-use terms were not read. The anonymous live `code_search` bucket (limit 60) conflicts with the documented auth requirement.
