FROM debian:bookworm-slim@sha256:1def178129dfb5f24db43afbf2fcac04530012e3264ba4ff81c71184e17a9ee4

ARG DEBIAN_FRONTEND=noninteractive
ARG SNAPSHOT=20260623T000000Z
ARG RUST_VERSION=1.92.0
ARG RUST_DATE=2025-12-11
ARG RUST_SHA256=d2ccef59dd9f7439f2c694948069f789a044dc1addcc0803613232af8f88ee0c

RUN printf '%s\n' \
      "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/$SNAPSHOT bookworm main" \
      "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/$SNAPSHOT bookworm-security main" \
      > /etc/apt/sources.list \
    && rm -f /etc/apt/sources.list.d/* \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends \
      ca-certificates=20230311+deb12u1 \
      curl=7.88.1-10+deb12u14 \
      g++=4:12.2.0-3 \
      libgmp-dev=2:6.2.1+dfsg1-1.1 \
      libssl-dev=3.0.20-1~deb12u2 \
      m4=1.4.19-3 \
      make=4.3-4.1 \
      nlohmann-json3-dev=3.11.2-2 \
      pkg-config=1.8.1-1 \
      python3=3.11.2-1+b1 \
      python3-jsonschema=4.10.3-1 \
      xz-utils=5.4.1-1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl --fail --location --proto '=https' --tlsv1.2 \
      "https://static.rust-lang.org/dist/$RUST_DATE/rust-$RUST_VERSION-x86_64-unknown-linux-gnu.tar.xz" \
      --output /tmp/rust.tar.xz \
    && echo "$RUST_SHA256  /tmp/rust.tar.xz" | sha256sum --check --strict \
    && tar -C /tmp -xf /tmp/rust.tar.xz \
    && "/tmp/rust-$RUST_VERSION-x86_64-unknown-linux-gnu/install.sh" \
      --prefix=/usr/local --without=rust-docs \
    && rm -rf /tmp/rust*

ENV CARGO_HOME=/opt/cargo
WORKDIR /workspace
COPY . .
RUN make build-all

CMD ["python3", "-B", "verify_all.py", "--profile", "fast"]
