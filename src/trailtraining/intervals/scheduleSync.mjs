import { listWellnessBearer, normalizeSleepAndHr } from "./intervalsClient.mjs";
import pg from "pg";

const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });

function yyyyMmDd(d) {
  return d.toISOString().slice(0, 10);
}

async function getLastSyncedDay(userId) {
  const r = await pool.query(
    "select max(day) as max_day from wellness_day where user_id = $1",
    [userId]
  );
  return r.rows[0]?.max_day ? new Date(r.rows[0].max_day) : null;
}

async function upsertWellness(userId, rec) {
  await pool.query(
    `insert into wellness_day (user_id, day, sleep_secs, resting_hr, avg_sleeping_hr, raw)
     values ($1, $2, $3, $4, $5, $6)
     on conflict (user_id, day) do update set
       sleep_secs = excluded.sleep_secs,
       resting_hr = excluded.resting_hr,
       avg_sleeping_hr = excluded.avg_sleeping_hr,
       raw = excluded.raw,
       updated_at = now()`,
    [userId, rec.day, rec.sleepSecs, rec.restingHR, rec.avgSleepingHR, rec.raw]
  );
}

export async function syncUserWellness(userId) {
  // Load token
  const auth = await pool.query("select athlete_id, access_token from intervals_auth where user_id=$1", [userId]);
  if (!auth.rowCount) throw new Error(`No Intervals auth for user ${userId}`);

  const { athlete_id: athleteId, access_token: accessToken } = auth.rows[0];

  const last = await getLastSyncedDay(userId);
  const overlapDays = 7; // backfill window to capture late syncs/edits
  const oldest = last ? new Date(last) : new Date(Date.now() - 30 * 864e5);

  oldest.setDate(oldest.getDate() - overlapDays);
  const newest = new Date();

  const wellness = await listWellnessBearer({
    accessToken,
    athleteId: athleteId ?? "0",
    oldest: yyyyMmDd(oldest),
    newest: yyyyMmDd(newest),
  });

  for (const w of wellness) {
    const rec = normalizeSleepAndHr(w);
    await upsertWellness(userId, rec);
  }
}