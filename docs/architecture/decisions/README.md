# Architecture decisions

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Decision records explain constraints and consequences behind the current architecture. Read the [architecture guide](../README.md) for the implementation overview.

## Guides

| Guide | Use it to |
| --- | --- |
| [ADR-0001: Resolve Authentication Provider From User Document](0001-authentication-provider-resolution.md) | Resolve the authentication provider from the stored user account. |
| [ADR-0002: Local Password Lifecycle With Email Fallback](0002-local-password-lifecycle.md) | Define local password changes, resets, and mail fallback. |
| [ADR 0003: synchronous HTTP handlers and MongoDB execution](0003-synchronous-http-and-mongodb.md) | Keep synchronous MongoDB execution within synchronous HTTP handlers. |
| [ADR 0004: installable application and library packages](0004-installable-application-packages.md) | Explain package boundaries, deployment artifacts, editable development and their costs. |

[Documentation home](../../README.md)
