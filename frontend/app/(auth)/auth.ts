import { compare } from "bcrypt-ts";
import NextAuth, { type DefaultSession } from "next-auth";
import type { DefaultJWT } from "next-auth/jwt";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";
import { DUMMY_PASSWORD } from "@/lib/constants";
import {
  createGuestUser,
  getOrCreateGoogleUser,
  getUser,
} from "@/lib/db/queries";
import { authConfig } from "./auth.config";

export type UserType = "guest" | "regular";

const googleClientId = process.env.AUTH_GOOGLE_ID || process.env.GOOGLE_CLIENT_ID;
const googleClientSecret =
  process.env.AUTH_GOOGLE_SECRET || process.env.GOOGLE_CLIENT_SECRET;

declare module "next-auth" {
  interface Session extends DefaultSession {
    user: {
      id: string;
      type: UserType;
    } & DefaultSession["user"];
  }

  interface User {
    email?: string | null;
    id?: string;
    type: UserType;
  }
}

declare module "next-auth/jwt" {
  interface JWT extends DefaultJWT {
    id: string;
    type: UserType;
  }
}

export const {
  handlers: { GET, POST },
  auth,
  signIn,
  signOut,
} = NextAuth({
  ...authConfig,
  callbacks: {
    async signIn({ user, account, profile }) {
      if (account?.provider !== "google") {
        return true;
      }
      // Accounts are matched by email, so only trust addresses Google verified
      if (!user.email || profile?.email_verified !== true) {
        return false;
      }
      try {
        const dbUser = await getOrCreateGoogleUser(
          user.email,
          user.name,
          user.image
        );
        // The session must carry our database id, not Google's account id
        user.id = dbUser.id;
        user.type = "regular";
        return true;
      } catch (error) {
        console.error("Error creating Google user:", error);
        return false;
      }
    },
    jwt({ token, user }) {
      if (user) {
        token.id = user.id as string;
        token.type = user.type || "regular";
      }

      return token;
    },
    session({ session, token }) {
      if (session.user) {
        session.user.id = token.id;
        session.user.type = token.type;
      }

      return session;
    },
  },
  providers: [
    // Only offer Google when real OAuth credentials exist; placeholder values
    // make Google reject every sign-in attempt
    ...(googleClientId && googleClientSecret
      ? [
          Google({
            allowDangerousEmailAccountLinking: true,
            clientId: googleClientId,
            clientSecret: googleClientSecret,
          }),
        ]
      : []),
    Credentials({
      async authorize(credentials) {
        const email = String(credentials.email ?? "");
        const password = String(credentials.password ?? "");
        const users = await getUser(email);

        if (users.length === 0) {
          await compare(password, DUMMY_PASSWORD);
          return null;
        }

        const [user] = users;

        if (!user.password) {
          await compare(password, DUMMY_PASSWORD);
          return null;
        }

        const passwordsMatch = await compare(password, user.password);

        if (!passwordsMatch) {
          return null;
        }

        return { ...user, type: "regular" };
      },
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
    }),
    Credentials({
      async authorize() {
        const [guestUser] = await createGuestUser();
        return { ...guestUser, type: "guest" };
      },
      credentials: {},
      id: "guest",
    }),
  ],
});
