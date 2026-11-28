# Grenslan foundation container

The development and reference image runs Grenslan's service with bundled SearXNG as a separately supervised, namespace-confined process (AD-423, `docs/implementation/SEARXNG-EGRESS.md`). Full release packaging is PRP-006 work. This image is the foundation path: it can be built from the repository and run locally.

| File | Purpose |
|---|---|
| `Dockerfile` | The image. The base and uv images are pinned by digest. Dependencies are installed from hash-verified locks. |
| `seccomp.json` | Grenslan's seccomp profile: Docker's default, plus one rule for SearXNG's confinement. |
| `seccomp-docker-default.json` | Docker's default profile (moby/profiles `seccomp/v0.2.3`, Apache-2.0), which `seccomp.json` is derived from. |
| `seccomp.py` | Regenerates `seccomp.json`. Run with `--check` to verify it is current. |
| `NOTICE.md` | Installed as `/usr/share/doc/grenslan/NOTICE.md`, with all third-party notices. |
| `smoke-test.sh` | Isolation smoke test for a built image. |

## Build

From the repository root:

```sh
docker build -f docker/Dockerfile -t grenslan:dev .
```

The build fetches SearXNG's pinned source and the hash-locked Python packages. It fails if the committed notices (`packaging/notices/`) no longer match the packages it installed. Compare its `notices.py check` step.

## Run

```sh
docker run -d --name grenslan \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --security-opt seccomp=docker/seccomp.json \
  -v /path/to/config:/etc/grenslan:ro \
  -v /path/to/tls:/run/secrets:ro \
  -p 127.0.0.1:8443:8443 \
  grenslan:dev
```

Notes:
- **Configuration:** `/etc/grenslan/service.yaml` and `/etc/grenslan/providers.yaml`. See `examples/` and `docs/implementation/SERVICE-CONFIGURATION.md`.
- **TLS material:** the certificate and key are at the paths the service configuration names. The examples use `/run/secrets/`.
- **User:** the image runs as uid and gid 10001. Mounted files must be readable by that user.
- **Ports:** publish 8443 only where consumers should reach it. Nothing else listens: SearXNG and its egress proxy use owner-only Unix sockets in a private directory under `/tmp`.
- **Docker socket:** do not mount it, or any other host control interface.

### Why the seccomp profile is needed

Grenslan starts SearXNG in a new user and network namespace that contains only loopback. Its only way out is Grenslan's egress proxy, which enforces the configured destinations. Docker's default seccomp profile allows creating namespaces only with `CAP_SYS_ADMIN`.

`seccomp.json` is Docker's default plus one rule. It allows `unshare` only when its flags are exactly `CLONE_NEWUSER | CLONE_NEWNET`. Every other combination is still refused, including either flag alone, or with mount or PID namespaces added. The container needs no added capability and stays non-root.

Without the profile, Grenslan still starts, but bundled SearXNG is `unavailable`. It never runs unconfined. The log says why:

```
provider searxng_bundled: initializing -> unavailable (provider_unavailable: SearXNG cannot be confined on this host: ... Operation not permitted. In a container, run it with Grenslan's seccomp profile (docker/README.md).)
```

Hosts that restrict unprivileged user namespaces in other ways also stop confinement, with the same fail-closed result:
- the `user.max_user_namespaces=0` sysctl;
- AppArmor's `kernel.apparmor_restrict_unprivileged_userns=1`, as on Ubuntu 23.10 and later.

Such hosts have not been tested yet.

## Smoke test

```sh
docker/smoke-test.sh grenslan:dev
```

The test runs the image on a temporary internal Docker network with an untrusted probe container. It uses throwaway TLS material and credentials, and removes everything it creates. It checks:
- the image runs non-root;
- SearXNG fails closed without the profile and is ready with it;
- the probe reaches HTTPS ingress, with verified TLS and authentication required;
- a full TCP port scan finds only 8443;
- the container has no other listener;
- another uid can't reach SearXNG's or the proxy's socket;
- a confined process has only loopback and no route out;
- the egress proxy refuses unlisted hosts, metadata, loopback and Grenslan itself;
- there is no Docker socket;
- `docker stop` shuts down cleanly.

## Source and notices

Grenslan's licence and every third-party notice are in `/usr/share/doc/grenslan/`. `NOTICE.md` there gives the layout. SearXNG's complete source is in `/opt/grenslan/searxng/src`.

This image is built locally from the repository. When a built image is distributed, its distributor must also make the source of the bundled components available (see the README's License section and `docs/implementation/DEPENDENCIES.md`). `packaging/searxng/fetch-sources.sh` assembles it.
