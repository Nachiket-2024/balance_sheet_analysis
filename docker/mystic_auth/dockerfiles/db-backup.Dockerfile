FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS rclone-builder

ARG RCLONE_VERSION=1.75.1
ARG RCLONE_SOURCE_SHA256=fcc9351ab3976c73b4824cf7919f98f911f2442a606e2910fc2bd562111da220
ARG GRPC_VERSION=v1.85.0-dev.0.20260825072537-93e31b48545e
ARG X_NET_VERSION=v0.60.0

RUN apk add --no-cache ca-certificates curl tar \
    && mkdir -p /src /out \
    && curl -fsSL "https://github.com/rclone/rclone/archive/refs/tags/v${RCLONE_VERSION}.tar.gz" -o /tmp/rclone.tar.gz \
    && echo "${RCLONE_SOURCE_SHA256}  /tmp/rclone.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/rclone.tar.gz --strip-components=1 -C /src \
    && rm -f /tmp/rclone.tar.gz

WORKDIR /src

RUN go install github.com/google/go-licenses@v1.6.0

RUN go mod edit -require="google.golang.org/grpc@${GRPC_VERSION}" \
    -require="golang.org/x/net@${X_NET_VERSION}" \
    && go mod tidy \
    && GOFLAGS="-tags=noselfupdate" /go/bin/go-licenses save . --save_path=/out/rclone-licenses \
    && CGO_ENABLED=0 go build -tags=noselfupdate -trimpath -ldflags="-s -w" -o /out/rclone .

FROM postgres:15-trixie@sha256:a5f9ead8ed7cb25abc36bea51fb9bb2be8d5579ed4ef3d28876027e438391ff0

# The scheduled backup service needs both the B2 client and
# curl for the Sentry-compatible Bugsink failure notification. Keep the
# database client image as the base so pg_dump/pg_restore stay version-matched
# with the server image. Debian's installed package copyright files are retained
# and copied into the notice bundle below. setpriv replaces the base image's
# older gosu binary for the privilege drop.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ca-certificates curl openssl util-linux \
    && groupadd --system --gid 10001 mysticbackup \
    && useradd --system --uid 10001 --gid mysticbackup --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin mysticbackup \
    && rm -f /usr/local/bin/gosu \
    && mkdir -p /usr/share/licenses/mystic-auth/db-backup/debian \
    && dpkg-query -W | sort -k1,1 > /usr/share/licenses/mystic-auth/db-backup/debian/packages.tsv \
    && cp -a /usr/share/doc/. /usr/share/licenses/mystic-auth/db-backup/debian/ \
    && mkdir -p /usr/share/licenses/mystic-auth/db-backup/debian/common-licenses \
    && cp -a /usr/share/common-licenses/. /usr/share/licenses/mystic-auth/db-backup/debian/common-licenses/ \
    && test -n "$(find /usr/share/licenses/mystic-auth/db-backup/debian -type f -name copyright -print -quit)" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=rclone-builder /out/rclone /usr/local/bin/rclone
COPY --from=rclone-builder /out/rclone-licenses/ /usr/share/licenses/mystic-auth/db-backup/rclone/
RUN chmod 0755 /usr/local/bin/rclone

COPY scripts/mystic_auth/db/database-backup/database-backup-failure-alert.sh /usr/local/bin/backup-failure-alert
COPY scripts/mystic_auth/db/backup-upload/backup-upload.sh /usr/local/bin/run-backup-upload
COPY scripts/mystic_auth/db/backup-verification/backup-hmac.sh /usr/local/bin/backup-hmac
RUN chmod 0755 /usr/local/bin/backup-failure-alert /usr/local/bin/run-backup-upload /usr/local/bin/backup-hmac

COPY docker/mystic_auth/dockerfiles/db-backup-entrypoint.sh /usr/local/bin/db-backup-entrypoint
RUN chmod 0755 /usr/local/bin/db-backup-entrypoint

# The production image is non-root by default. Compose services with a
# bind-mounted backup directory explicitly start the entrypoint as root so it
# can normalize that mount's ownership, then it drops to UID/GID 10001.
USER mysticbackup

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD pg_isready -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" || exit 1
