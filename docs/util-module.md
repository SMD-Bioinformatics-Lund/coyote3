# Utility Module (`coyote/util/`)

The `util` package contains application-wide helper functions, decorators, and report-generation utilities that are shared across multiple blueprints and services. These utilities promote code reuse, consistency, and clear separation of concerns.

---

## 📦 Summary Table

| Component                         | Location                                 | Responsibilities                                                                 |
|----------------------------------|------------------------------------------|----------------------------------------------------------------------------------|
| `access.py`                      | `coyote/util/decorators/access.py`       | Access control decorators: `@require_sample_access()`, `@require_group_access()` |
| `common_utility.py`              | `coyote/util/common_utility.py`          | General helper functions: datetime formatting, slug creation         |
| `misc.py`                        | `coyote/util/misc.py`                    | Miscellaneous utilities: string normalization, ID/token generation               |
| `report_util.py`                 | `coyote/util/report/report_util.py`      | PDF/HTML report generation utilities                                             |
| `Utility` class                  | `coyote/util/utility.py`                 | Central manager that initializes and aggregates utility classes across modules   |

---

## Component Details

### 1. `access.py`

Provides commonly-used route protection decorators:

- **`@require_sample_access(sample_id: str)`**: Checks if the `current_user` has access to the specific sample.
- **`@require_group_access(group_id: str)`**: Checks if the `current_user` has access to the specific group.

Decorators are built using `functools.wraps`, preserving metadata (following best practices.

**Example:**
```python
@app.route('/samples')
@require_sample_access(sample_id="000012345")
def show_variants():
    ...
```

### 2. `common_utility.py`
Implements general-purpose helper functions:

- Datetime formatting helpers
- Slug or URL-safe identifier creation

These utilities standardize consistent behavior and reduce code duplication across blueprints.

### 3. `misc.py`
A collection of miscellaneous utility functions:

- String normalization and sanitization
- Unique ID or token generation (e.g. uuid4())
- Other reusable helpers that don't fit specific categories

### 4. `report_util.py`
Handles generation and export of student reports:
- Renders Jinja templates into HTML
- Converts HTML to PDF (using tools like wkhtmltopdf)
- Applies consistent styles, metadata, and watermarking

Centralizing report logic supports a DRY architecture, preventing duplication.

### 5. `Utility` Class
A centralized manager for utility access across the application:

```python
class Utility:
    """
    Central access-point aggregating all utility classes for each blueprint and shared domain.
    """

    def init_util(self) -> None:
        from coyote.blueprints.dna.util import DNAUtility
        from coyote.util.common_utility import CommonUtility
        from coyote.util.report.report_util import ReportUtility
        from coyote.blueprints.home.util import HomeUtility
        from coyote.blueprints.rna.util import RNAUtility
        from coyote.blueprints.dashboard.util import DashBoardUtility
        from coyote.blueprints.admin.util import AdminUtility
        from coyote.blueprints.coverage.util import CoverageUtility
        from coyote.blueprints.common.util import BPCommonUtility

        self.dna = DNAUtility()
        self.common = CommonUtility()
        self.main = HomeUtility()
        self.rna = RNAUtility()
        self.dashboard = DashBoardUtility()
        self.admin = AdminUtility()
        self.coverage = CoverageUtility()
        self.report = ReportUtility()
        self.bpcommon = BPCommonUtility()
```

This class initializes and aggregates utility classes from various blueprints, providing a single access point for all shared utilities.

### Integration
1. Initialization (initiated in extensions.py and then instantiated in the app factory):
```python
util = Utility()
extensions.util.init_util()
```

2. Usage Example
```python
from extensions import util
formatted = util.report.format_timestamp(sample.date)
```
