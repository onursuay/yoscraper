-- ============================================================
-- Email Marketing Infrastructure — Faz 1
-- Supabase SQL Editor'da çalıştır
-- ============================================================

-- 1. Suppressions (unsubscribed + bounced + complained)
CREATE TABLE IF NOT EXISTS email_suppressions (
  email       text PRIMARY KEY,
  reason      text NOT NULL CHECK (reason IN ('unsubscribed', 'bounced', 'complained', 'manual')),
  source      text DEFAULT 'user',
  created_at  timestamptz DEFAULT now()
);

-- Mevcut unsubscribed tablosunu migrate et (varsa)
INSERT INTO email_suppressions (email, reason, source, created_at)
SELECT email, 'unsubscribed', 'migration', COALESCE(created_at, now())
FROM unsubscribed
ON CONFLICT (email) DO NOTHING;

-- 2. Kampanyalar
CREATE TABLE IF NOT EXISTS campaigns (
  id               uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  name             text NOT NULL,
  type             text NOT NULL CHECK (type IN ('broadcast', 'sequence')),
  status           text DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'running', 'paused', 'completed', 'cancelled')),
  subject          text,
  body_html        text,
  segment_filter   jsonb DEFAULT '{}',
  scheduled_at     timestamptz,
  recurrence_cron  text,
  trigger_type     text DEFAULT 'manual' CHECK (trigger_type IN ('manual', 'lead_created', 'segment_match')),
  created_at       timestamptz DEFAULT now(),
  updated_at       timestamptz DEFAULT now()
);

-- 3. Sekans adımları
CREATE TABLE IF NOT EXISTS campaign_steps (
  id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  campaign_id  uuid REFERENCES campaigns(id) ON DELETE CASCADE,
  step_order   int NOT NULL,
  delay_hours  int DEFAULT 0,
  subject      text NOT NULL,
  body_html    text NOT NULL,
  created_at   timestamptz DEFAULT now()
);

-- 4. Sekans enrollments
CREATE TABLE IF NOT EXISTS campaign_enrollments (
  id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  campaign_id   uuid REFERENCES campaigns(id) ON DELETE CASCADE,
  lead_email    text NOT NULL,
  lead_name     text,
  lead_data     jsonb DEFAULT '{}',
  current_step  int DEFAULT 0,
  status        text DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused', 'failed', 'unsubscribed')),
  next_send_at  timestamptz,
  enrolled_at   timestamptz DEFAULT now(),
  UNIQUE (campaign_id, lead_email)
);

-- 5. Email kuyruğu
CREATE TABLE IF NOT EXISTS email_queue (
  id                   uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  campaign_id          uuid REFERENCES campaigns(id) ON DELETE SET NULL,
  enrollment_id        uuid REFERENCES campaign_enrollments(id) ON DELETE SET NULL,
  step_id              uuid REFERENCES campaign_steps(id) ON DELETE SET NULL,
  to_email             text NOT NULL,
  to_name              text,
  subject              text NOT NULL,
  body_html            text NOT NULL,
  status               text DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'sent', 'failed')),
  scheduled_at         timestamptz DEFAULT now(),
  sent_at              timestamptz,
  provider_message_id  text,
  attempts             int DEFAULT 0,
  last_error           text,
  created_at           timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_email_queue_pending
  ON email_queue (status, scheduled_at)
  WHERE status = 'pending';

-- 6. Email events (Resend webhook)
CREATE TABLE IF NOT EXISTS email_events (
  id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  queue_id     uuid REFERENCES email_queue(id) ON DELETE SET NULL,
  campaign_id  uuid REFERENCES campaigns(id) ON DELETE SET NULL,
  to_email     text NOT NULL,
  event_type   text NOT NULL,
  metadata     jsonb DEFAULT '{}',
  occurred_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_email_events_campaign ON email_events (campaign_id);
CREATE INDEX IF NOT EXISTS idx_email_events_email    ON email_events (to_email);

-- 7. RLS — service_role key ile erişim (dashboard app kullanır)
ALTER TABLE email_suppressions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns             ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_steps        ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_enrollments  ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_queue           ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_events          ENABLE ROW LEVEL SECURITY;

-- service_role tüm tablolara erişebilir (default Supabase davranışı)
-- anon key için sadece email_suppressions insert izni (unsubscribe sayfası için)
CREATE POLICY "anon_insert_suppression" ON email_suppressions
  FOR INSERT TO anon WITH CHECK (true);
