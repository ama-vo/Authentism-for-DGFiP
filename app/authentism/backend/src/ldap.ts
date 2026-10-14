// Accès à l'annuaire LDAP EXISTANT de la DGFiP (gestion centralisée des identités).
//
// Principe :
//  - un compte de service (LDAP_BIND_DN) sert à chercher et administrer les comptes ;
//  - le mot de passe d'un utilisateur est vérifié par un "bind" LDAP avec SON compte :
//    l'API ne lit jamais les mots de passe, c'est l'annuaire qui les vérifie ;
//  - les changements de mot de passe passent par l'opération standard "Password Modify"
//    (RFC 3062) : c'est l'annuaire qui hache le mot de passe selon sa propre politique.
import fs from "fs";
import { Client, Change, Attribute, EqualityFilter, InvalidCredentialsError } from "ldapts";
import { config } from "./config";

export type Role = "usager" | "agent" | "admin";
export const ROLES: Role[] = ["usager", "agent", "admin"];

export interface User {
  dn: string;
  fiscalNumber: string;
  firstName: string;
  lastName: string;
  email: string;
  role: Role;
}

const { loginAttribute, roleAttribute, usersDn } = config.ldap;

// Certificat de l'autorité qui a signé le certificat du serveur LDAP (facultatif).
// Sans fichier, Node utilise les autorités de confiance du système.
// Ces options ne s'appliquent qu'aux adresses ldaps:// (connexion chiffrée).
const useTls = config.ldap.url.startsWith("ldaps://");
const tlsOptions =
  useTls && fs.existsSync(config.ldap.caFile) ? { ca: [fs.readFileSync(config.ldap.caFile)] } : undefined;
if (!useTls) {
  console.warn("[ldap] ATTENTION : connexion LDAP non chiffrée (ldap://). À n'utiliser que pour les tests.");
}

function newClient() {
  return new Client({ url: config.ldap.url, timeout: 5000, connectTimeout: 5000, tlsOptions });
}

// Ouvre une connexion avec le compte de service, exécute l'action, puis ferme la connexion.
async function withServiceAccount<T>(action: (client: Client) => Promise<T>): Promise<T> {
  const client = newClient();
  try {
    await client.bind(config.ldap.bindDn, config.ldap.bindPassword);
    return await action(client);
  } finally {
    await client.unbind().catch(() => {});
  }
}

function first(value: unknown): string {
  if (Array.isArray(value)) return String(value[0] ?? "");
  return value === undefined ? "" : String(value);
}

function toUser(entry: Record<string, unknown>): User {
  const role = first(entry[roleAttribute]) as Role;
  return {
    dn: String(entry.dn),
    fiscalNumber: first(entry[loginAttribute]),
    firstName: first(entry.givenName),
    lastName: first(entry.sn),
    email: first(entry.mail),
    // Rôle absent ou inconnu dans l'annuaire -> rôle le plus faible (moindre privilège)
    role: ROLES.includes(role) ? role : "usager",
  };
}

const ATTRIBUTES = ["dn", loginAttribute, "givenName", "sn", "mail", roleAttribute];

// EqualityFilter échappe automatiquement les caractères spéciaux LDAP
// ( * ( ) \ ) : protection contre l'injection LDAP.
export async function findUser(fiscalNumber: string): Promise<User | null> {
  return withServiceAccount(async (client) => {
    const { searchEntries } = await client.search(usersDn, {
      scope: "sub",
      filter: new EqualityFilter({ attribute: loginAttribute, value: fiscalNumber }),
      attributes: ATTRIBUTES,
    });
    return searchEntries.length === 1 ? toUser(searchEntries[0]) : null;
  });
}

export async function listUsers(): Promise<User[]> {
  return withServiceAccount(async (client) => {
    const { searchEntries } = await client.search(usersDn, {
      scope: "sub",
      filter: `(&(objectClass=inetOrgPerson)(${loginAttribute}=*))`,
      attributes: ATTRIBUTES,
      sizeLimit: 1000,
    });
    return searchEntries.map(toUser);
  });
}

// Vérifie le mot de passe en se connectant à l'annuaire AVEC le compte de l'utilisateur.
// Attention : un mot de passe vide ferait une connexion anonyme qui "réussit" ;
// c'est pour ça que la validation refuse les mots de passe vides.
export async function checkPassword(user: User, password: string): Promise<boolean> {
  if (!password) return false;
  const client = newClient();
  try {
    await client.bind(user.dn, password);
    return true;
  } catch (err) {
    if (err instanceof InvalidCredentialsError) return false;
    throw err; // autre problème (annuaire injoignable...) -> erreur 500
  } finally {
    await client.unbind().catch(() => {});
  }
}

// ---------------------------------------------------------------
// Changement de mot de passe : opération LDAP "Password Modify" (OID 1.3.6.1.4.1.4203.1.11.1)
// Le message attendu est une petite structure binaire (BER) :
//   SEQUENCE { [0] dn de l'utilisateur, [2] nouveau mot de passe }
// ---------------------------------------------------------------
function berField(tag: number, value: Buffer): Buffer {
  const length = value.length;
  const lengthBytes =
    length < 128 ? Buffer.from([length]) : Buffer.from([0x82, length >> 8, length & 0xff]); // forme longue (< 64 Ko)
  return Buffer.concat([Buffer.from([tag]), lengthBytes, value]);
}

export async function updatePassword(user: User, newPassword: string) {
  const request = berField(
    0x30,
    Buffer.concat([berField(0x80, Buffer.from(user.dn)), berField(0x82, Buffer.from(newPassword))])
  );
  await withServiceAccount((client) => client.exop("1.3.6.1.4.1.4203.1.11.1", request));
}

export async function createUser(data: {
  fiscalNumber: string;
  firstName: string;
  lastName: string;
  email: string;
  role: Role;
  password: string;
}) {
  const dn = `${loginAttribute}=${data.fiscalNumber},${usersDn}`;
  await withServiceAccount((client) =>
    client.add(dn, {
      objectClass: ["inetOrgPerson"],
      [loginAttribute]: data.fiscalNumber,
      cn: `${data.firstName} ${data.lastName}`,
      givenName: data.firstName,
      sn: data.lastName,
      mail: data.email,
      [roleAttribute]: data.role,
    })
  );
  // Le mot de passe est défini ensuite, pour que ce soit l'annuaire qui le hache
  const user = await findUser(data.fiscalNumber);
  if (user) await updatePassword(user, data.password);
}

export async function updateRole(user: User, role: Role) {
  const change = new Change({
    operation: "replace",
    modification: new Attribute({ type: roleAttribute, values: [role] }),
  });
  await withServiceAccount((client) => client.modify(user.dn, [change]));
}

export async function deleteUser(user: User) {
  await withServiceAccount((client) => client.del(user.dn));
}

// Test de connexion au démarrage : on réessaie pendant 1 minute (le temps que l'annuaire
// démarre), puis on affiche un message clair si la configuration est fausse.
export async function testLdapConnection(attempt = 1) {
  try {
    const users = await listUsers();
    console.log(`[ldap] Connecté à ${config.ldap.url} - ${users.length} compte(s) trouvé(s) dans ${usersDn}`);
  } catch (err) {
    if (attempt < 12) {
      setTimeout(() => testLdapConnection(attempt + 1), 5000);
      return;
    }
    console.error(`[ldap] ERREUR de connexion à ${config.ldap.url} : ${(err as Error).message}`);
    console.error("[ldap] Vérifiez LDAP_URL, LDAP_BIND_DN, LDAP_BIND_PASSWORD et LDAP_USERS_DN dans le fichier .env");
  }
}
