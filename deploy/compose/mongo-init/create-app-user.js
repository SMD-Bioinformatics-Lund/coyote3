/* First initialization only. Logical databases share one mongod dbPath. */
const scope = process.env.MONGO_SERVICE_SCOPE;
const appUser = process.env.MONGO_APP_USER;
const appPassword = process.env.MONGO_APP_PASSWORD;
const kb = process.env.KNOWLEDGEBASE_DB;
if (!appUser || !appPassword || !kb) {
  throw new Error("MONGO_APP_USER, MONGO_APP_PASSWORD and KNOWLEDGEBASE_DB are required");
}
const roles = [{ role: "read", db: kb }];
if (scope === "app") {
  const databases = [process.env.COYOTE3_DB, process.env.IDENTITY_DB, process.env.BAM_DB];
  if (databases.some((name) => !name) || new Set([...databases, kb]).size !== 4) {
    throw new Error("App, identity, BAM and knowledgebase names must be present and distinct on this instance");
  }
  const identityDb = db.getSiblingDB(process.env.IDENTITY_DB);
  const policy = JSON.parse(require("fs").readFileSync(
    process.env.COYOTE3_ROLE_POLICY_PATH || "/opt/coyote3/identity-role-policy.json", "utf8"));
  for (const index of policy.indexes) {
    const { collection, fields, ...options } = index;
    identityDb.getCollection(collection).createIndex(Object.fromEntries(fields), options);
  }
  const definition = policy.identity_role;
  const privileges = definition.privileges.map((privilege) => ({
    ...privilege, resource: { ...privilege.resource, db: process.env.IDENTITY_DB },
  }));
  if (!identityDb.getRole(definition.role)) {
    identityDb.createRole({ role: definition.role, privileges, roles: [] });
  }
  roles.push({ role: "readWrite", db: process.env.COYOTE3_DB },
    { role: "readWrite", db: process.env.BAM_DB },
    { role: definition.role, db: process.env.IDENTITY_DB });
} else if (scope !== "knowledgebase") {
  throw new Error("MONGO_SERVICE_SCOPE must be app or knowledgebase");
}
const authDb = db.getSiblingDB("admin");
if (!authDb.getUser(appUser)) {
  authDb.createUser({ user: appUser, pwd: appPassword, roles });
}
