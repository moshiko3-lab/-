// Staff log in with a username. Supabase Auth needs an email, so a username maps to an address
// on a reserved domain that can never receive mail. The owner logs in with a real email.
export const STAFF_EMAIL_DOMAIN = "staff.shokogi.invalid";

export function loginEmail(input: string) {
  const login = input.trim().toLowerCase();
  return login.includes("@") ? login : `${login}@${STAFF_EMAIL_DOMAIN}`;
}
