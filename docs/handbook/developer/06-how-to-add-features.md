# How to Add Features

Adding features in Coyote3 should follow the same shape as existing functionality: define behavior first, attach it to the correct blueprint, implement the data behavior in handlers, wire UI controls in the owning templates, and then document what changed for both users and developers.

Start by writing the feature contract in plain terms: what users can do, where they do it, what permission is required, what is read, what is written, and what happens on failure. This avoids ambiguous implementations and helps decide whether the change belongs in Home, DNA, RNA, Common, Dashboard, or Admin.

Once ownership is clear, implement route behavior and permission enforcement first. Route handlers should remain thin and predictable: parse input, enforce access, call handler/util logic, and return a deterministic result. If a route is sample-scoped, sample access checks must be part of the contract.

Data behavior should live in handler or utility layers, not templates. New queries and updates should be explicit, compatible with existing documents, and safe when optional fields are missing. If the feature affects interpretation history or reporting, verify that report snapshot behavior remains consistent with the current report model.

UI changes should then expose the new behavior where users already work. Keep existing navigation and interaction patterns, and avoid adding controls that bypass permission checks or hide important state transitions.

Testing infrastructure in this repository is still evolving. For now, treat automated test coverage as **coming soon** and focus on careful manual validation of permission behavior, state mutation behavior, and report/history behavior. When the test suite is established, this chapter should be extended with concrete test standards and CI gates.

Before considering a feature complete, ensure the handbook is updated so future developers and users understand what changed, where it lives, and why it behaves that way.
