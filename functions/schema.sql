-- Cloudflare D1 schema for the live API (functions/api/[[route]].js).  npx wrangler d1 execute pixel-trichy --file functions/schema.sql
create table if not exists visitors (id text primary key, first_ts integer);
create table if not exists presence (id text primary key, ts integer);
create table if not exists memories (id integer primary key autoincrement, lat real, lon real, text text, name text, ts integer, hidden integer default 0);
create table if not exists reports (id integer primary key autoincrement, uid text, kind text, note text, lat real, lon real, status text default 'new', ts integer);
create table if not exists hits (ip text, kind text, ts integer);
create index if not exists hits_idx on hits (ip, kind, ts);
