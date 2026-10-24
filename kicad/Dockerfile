# KiCad MCP Pro med KiCad 10 (kicad-cli + biblioteker) i samme image
FROM kicad/kicad:10.0

ARG KICAD_MCP_PRO_VERSION=4.4.0
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv

USER root
RUN uv venv --python /usr/bin/python3 /opt/kicad-mcp \
    && uv pip install --python /opt/kicad-mcp/bin/python --no-cache "kicad-mcp-pro==${KICAD_MCP_PRO_VERSION}" \
    && mkdir -p /projects && chown kicad:kicad /projects
USER kicad

ENV PATH=/opt/kicad-mcp/bin:$PATH \
    KICAD_MCP_KICAD_CLI=/usr/bin/kicad-cli \
    KICAD_MCP_WORKSPACE_ROOT=/projects \
    KICAD_MCP_TRANSPORT=streamable-http \
    KICAD_MCP_HOST=0.0.0.0 \
    KICAD_MCP_PORT=3334 \
    KICAD_MCP_HTTP_BOUNDARY=loopback-proxy \
    KICAD_MCP_PUBLIC_BASE_URL=http://127.0.0.1:3334 \
    KICAD_MCP_HEADLESS=1

WORKDIR /projects
EXPOSE 3334
CMD ["kicad-mcp-pro"]
