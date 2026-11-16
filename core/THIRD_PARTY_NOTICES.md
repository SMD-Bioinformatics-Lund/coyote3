# Core third-party notices

The Coyote core license does not replace third-party licenses or attribution.
Runtime dependencies are declared in [pyproject.toml](pyproject.toml);
installed dependencies provide their own license metadata and license files.

Report rendering uses `smd-reports==0.5.3`, whose metadata declares
`GPL-3.0-only`. Its report fonts, artwork and other bundled materials retain
their packaged notices. Those assets are supplied by the rendering dependency,
not copied into the Coyote core.

Database adapters, the API and the HTTP client are separate distributions.
Host-supplied reference datasets and institutional insignia retain their
respective terms.
