# Install and construct MongoDB connections

Python 3.12 or newer is required. Install `coyote-mongo` together with the selected
`coyote-core` wheel. For repository development, install both projects editable:

```bash
python -m pip install -e core -e adapters/mongo
```

Run that command at the repository root. The adapter does not require the API.

A host supplies explicit endpoints and logical database names:

```python
from coyote_mongo.connections import MongoConnections

settings = {
    "COYOTE4_MONGO_URI": "mongodb://localhost:27017/?replicaSet=coyote4-rs",
    "COYOTE4_DB": "coyote4_dev",
    "IDENTITY_DB": "coyote4_identity_dev",
    "KNOWLEDGEBASE_DB": "coyote4_knowledgebases_dev",
    "BAM_DB": "coyote4_bam_dev",
}

connections = MongoConnections(settings)
try:
    primary = connections.databases["primary"]
finally:
    connections.close()
```

Constructing clients does not install data or indexes. A successful constructor
alone does not prove server availability; use the connection's explicit `ping()`
when the host needs a connectivity check. See [configuration](configuration.md).
