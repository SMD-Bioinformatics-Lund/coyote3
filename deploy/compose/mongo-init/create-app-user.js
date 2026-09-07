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
  roles.push(...databases.map((name) => ({ role: "readWrite", db: name })));
} else if (scope !== "knowledgebase") {
  throw new Error("MONGO_SERVICE_SCOPE must be app or knowledgebase");
}
const authDb = db.getSiblingDB("admin");
if (!authDb.getUser(appUser)) {
  authDb.createUser({ user: appUser, pwd: appPassword, roles });
}
