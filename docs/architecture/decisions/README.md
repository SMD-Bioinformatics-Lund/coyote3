# Architecture decisions

Decision records explain constraints and consequences behind the current architecture. Read the [architecture guide](../README.md) for the implementation overview.

## Guides

| Guide | Use it to |
| --- | --- |
| [ADR-0001: Resolve Authentication Provider From User Document](0001-authentication-provider-resolution.md) | Resolve the authentication provider from the stored user account. |
| [ADR-0002: Local Password Lifecycle With Email Fallback](0002-local-password-lifecycle.md) | Define local password changes, resets, and mail fallback. |
| [ADR 0003: synchronous HTTP handlers and MongoDB execution](0003-synchronous-http-and-mongodb.md) | Keep synchronous MongoDB execution within synchronous HTTP handlers. |

[Documentation home](../../README.md)
