"""API contract namespace.

Import response models from their explicit module, for example
``coyote3.contracts.dna`` or ``coyote3.contracts.schemas.samples``. Keeping this
package initializer dependency-free prevents schema/domain import cycles during
CLI tools, migrations, and focused tests.
"""
