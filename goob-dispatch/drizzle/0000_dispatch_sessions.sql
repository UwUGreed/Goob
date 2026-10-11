CREATE TABLE dispatch_sessions (id TEXT PRIMARY KEY NOT NULL, revision INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL, updated_at INTEGER NOT NULL);
--> statement-breakpoint
CREATE TABLE dispatch_rate_limits (id TEXT PRIMARY KEY NOT NULL, window INTEGER NOT NULL, count INTEGER NOT NULL);
