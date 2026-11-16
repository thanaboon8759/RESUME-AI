-- Resume AI database: run once on a new, empty Supabase project (SQL Editor).
-- Applied to the resume-ai project on 2026-11-16 as migration "resume_ai_schema".

CREATE TABLE public.preferences (
    id TEXT PRIMARY KEY,  -- the owner's user id: one row per user
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT NOT NULL,
    retention TEXT NOT NULL,
    reasons JSONB NOT NULL,
    members JSONB NOT NULL,
    deleted JSONB NOT NULL,
    job_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE public.jobs (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    title TEXT NOT NULL,
    jd TEXT NOT NULL,
    required JSONB NOT NULL,
    preferred JSONB NOT NULL,
    weights JSONB NOT NULL,
    experience TEXT NOT NULL,
    education TEXT NOT NULL,
    location TEXT NOT NULL,
    salary TEXT NOT NULL,
    mandatory JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE public.candidates (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    job_id TEXT NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    candidate_name TEXT NOT NULL,
    position TEXT NOT NULL,
    score INTEGER NOT NULL,
    decision TEXT NOT NULL,
    reason JSONB NOT NULL,
    full_data JSONB NOT NULL, -- the rich candidate object the frontend shows
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE public.decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    candidate_id TEXT NOT NULL REFERENCES public.candidates(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    reason_code TEXT,
    reason_label TEXT NOT NULL,
    decision TEXT NOT NULL,
    actor TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    note TEXT,
    seconds_spent INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE public.uploads (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    job_id TEXT NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    candidate_id TEXT REFERENCES public.candidates(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    size INTEGER NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Indexes for the app's filters (every query filters by user_id; foreign keys need their own index)
CREATE INDEX preferences_user_id_idx ON public.preferences (user_id);
CREATE INDEX jobs_user_id_idx ON public.jobs (user_id);
CREATE INDEX candidates_job_user_idx ON public.candidates (job_id, user_id);
CREATE INDEX candidates_user_id_idx ON public.candidates (user_id);
CREATE INDEX decisions_user_id_idx ON public.decisions (user_id);
CREATE INDEX decisions_candidate_id_idx ON public.decisions (candidate_id);
CREATE INDEX decisions_job_id_idx ON public.decisions (job_id);
CREATE INDEX uploads_job_user_idx ON public.uploads (job_id, user_id);
CREATE INDEX uploads_candidate_id_idx ON public.uploads (candidate_id);
CREATE INDEX uploads_user_id_idx ON public.uploads (user_id);

-- Row level security: the backend's service-role key bypasses it; any direct client access sees only its own rows.
ALTER TABLE public.preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.uploads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own preferences" ON public.preferences FOR ALL TO authenticated
    USING (user_id = (select auth.uid())) WITH CHECK (user_id = (select auth.uid()));
CREATE POLICY "own jobs" ON public.jobs FOR ALL TO authenticated
    USING (user_id = (select auth.uid())) WITH CHECK (user_id = (select auth.uid()));
CREATE POLICY "own candidates" ON public.candidates FOR ALL TO authenticated
    USING (user_id = (select auth.uid())) WITH CHECK (user_id = (select auth.uid()));
CREATE POLICY "own decisions" ON public.decisions FOR ALL TO authenticated
    USING (user_id = (select auth.uid())) WITH CHECK (user_id = (select auth.uid()));
CREATE POLICY "own uploads" ON public.uploads FOR ALL TO authenticated
    USING (user_id = (select auth.uid())) WITH CHECK (user_id = (select auth.uid()));

-- Private resume storage: no public URLs; only the backend (service role) reads and writes it. 20 MB = the app's limit.
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('uploads', 'uploads', false, 20971520);
