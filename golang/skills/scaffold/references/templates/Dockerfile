FROM debian:13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETPLATFORM
COPY $TARGETPLATFORM/<NAME> /usr/local/bin/<NAME>

USER 65532:65532
ENTRYPOINT ["/usr/local/bin/<NAME>"]
