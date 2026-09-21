import type { Role } from "./permissions.js";

export interface AuthenticatedUser {
  id: string;
  username: string;
  email: string;
  name: string;
  role: Role;
  roles: Role[];
}

declare global {
  // Express exposes request augmentation through its global namespace.
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      authUser?: AuthenticatedUser;
      authSessionToken?: string;
    }
  }
}

export {};
