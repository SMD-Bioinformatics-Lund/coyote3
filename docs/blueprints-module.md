# Blueprints

Coyote3 defines reusable features as **Flask Blueprints**, each in its own package. This aligns with Flask best practices for modular structure.

### Blueprint Structure
Each blueprint (`admin`, `dna`, `rna`, etc.) includes:
- `__init__.py`: Instantiate Blueprint and register handlers
- `views.py`: Route handlers (`@bp.route`)
- `forms.py`: WTForms definitions (optional)
- `filters.py`: Jinja filters specific to that domain
- `util.py`: Shared helpers
- `templates/`: Jinja templates
- `static/`: js/css/icons, where needed

The `common` blueprint provides templates and utilities reused across the other blueprints in the app.

### Integration
Blueprints are imported and registered in `coyote/__init__.py`, using `app.register_blueprint(...)`.

### Adding a Blueprint
1. Create new `blueprints/<name>/` package.
2. Define all `.py` files as above.
3. Add your templates and static assets.
4. Register the blueprint in the main app factory.

This ensures clean separation and reusability. 

### Example Blueprint Folder Structure
```
example/
├── __init__.py
├── views.py
├── filters.py
├── forms.py
├── util.py
├── templates/
│   └── example_template.html
├── static/
│   ├── js/
│   ├── css/
│   └── icons/
```

### Example Blueprint
This is an example of how a blueprint might be structured in Coyote3:

Example code in the `__init.py__` file of the `example` blueprint:
```python
from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
example_bp = Blueprint(
    name="example_bp",
    import_name=__name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="example/static",
)

from coyote.blueprints.example import views 
from coyote.blueprints.example import filters

app.example_logger = logging.getLogger("coyote.example")
```

## Example Util Class
```python
class ExampleUtil:
    @staticmethod
    def example_method(param):
        # Example utility method
        return f"Processed {param}"
```
