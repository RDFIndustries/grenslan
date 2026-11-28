# syntax=docker/dockerfile:1
#
# Grenslan foundation development image: the service with bundled SearXNG as
# a separately supervised, namespace-confined process (AD-423,
# SEARXNG-EGRESS.md S1 to S4). Build from the repository root:
#
#   docker build -f docker/Dockerfile -t grenslan:dev .
#
# Run it with Grenslan's seccomp profile; see docker/README.md.

ARG PYTHON_IMAGE=python:3.12-slim@sha256:5b5fe805d367f8f5a359ded6ab2652b7f9a206453ee6ee789c0045ba6ec15016
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.10@sha256:a3ea1357342c1a4bf9a0c53a3deb1b55379aefa037338d8113d5771efa01774f

FROM ${UV_IMAGE} AS uv

# Build tooling only; also used by docker/offline-install-test.sh.
FROM ${PYTHON_IMAGE} AS tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never

FROM tools AS build
WORKDIR /src
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY packaging ./packaging
COPY docker/NOTICE.md ./docker/NOTICE.md

# Grenslan: hash-locked runtime dependencies, then the project wheel, in a venv without pip.
RUN uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file /tmp/requirements.txt \
    && python -m venv --without-pip /opt/grenslan/venv \
    && uv pip install --python /opt/grenslan/venv/bin/python --require-hashes --no-deps --compile-bytecode \
        -r /tmp/requirements.txt \
    && uv build --wheel --out-dir /tmp/wheel \
    && uv pip install --python /opt/grenslan/venv/bin/python --no-deps --compile-bytecode /tmp/wheel/grenslan-*.whl

# SearXNG: pinned source and hash-locked environment, as a separate component. pip is removed afterwards.
RUN packaging/searxng/install.sh /opt/grenslan/searxng /usr/local/bin/python3.12 \
    && /opt/grenslan/searxng/venv/bin/python -m pip uninstall --yes --quiet pip

# Notices: fail the build unless the committed notices cover exactly what is installed.
RUN python3 -I packaging/notices/notices.py check --site-packages \
        /opt/grenslan/venv/lib/python3.12/site-packages \
        /opt/grenslan/searxng/venv/lib/python3.12/site-packages \
    && doc=/opt/doc \
    && python3 -I packaging/notices/notices.py copy-python \
        --site-packages /opt/grenslan/venv/lib/python3.12/site-packages --output $doc/python/grenslan \
    && python3 -I packaging/notices/notices.py copy-python \
        --site-packages /opt/grenslan/searxng/venv/lib/python3.12/site-packages --output $doc/python/searxng \
    && cp -r packaging/notices/native packaging/notices/crates.txt $doc/ \
    && mkdir $doc/searxng \
    && cp /opt/grenslan/searxng/src/LICENSE /opt/grenslan/searxng/SOURCE $doc/searxng/ \
    && cp LICENSE $doc/LICENSE \
    && cp docker/NOTICE.md $doc/NOTICE.md

FROM ${PYTHON_IMAGE}
# The runtime needs no package installer.
RUN python -m pip uninstall --yes --quiet pip \
    && groupadd --gid 10001 grenslan \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin grenslan
COPY --from=build /opt/grenslan /opt/grenslan
COPY --from=build /opt/doc /usr/share/doc/grenslan
ENV PATH=/opt/grenslan/venv/bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONDONTWRITEBYTECODE=1 \
    GRENSLAN_SERVICE_CONFIG=/etc/grenslan/service.yaml \
    GRENSLAN_PROVIDER_CONFIG=/etc/grenslan/providers.yaml
USER 10001:10001
EXPOSE 8443
ENTRYPOINT ["grenslan"]
CMD ["serve"]
