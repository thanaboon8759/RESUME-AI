-- Create preferences table
DROP TABLE IF EXISTS public.preferences CASCADE;
CREATE TABLE public.preferences (
    id TEXT PRIMARY KEY,
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

-- Create jobs table
DROP TABLE IF EXISTS public.jobs CASCADE;
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

-- Create the candidates table in Supabase
DROP TABLE IF EXISTS public.candidates CASCADE;
CREATE TABLE public.candidates (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    job_id TEXT NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    candidate_name TEXT NOT NULL,
    position TEXT NOT NULL,
    score INTEGER NOT NULL,
    decision TEXT NOT NULL,
    reason JSONB NOT NULL,
    full_data JSONB NOT NULL, -- Stores the rich UI structure for the frontend
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Create decisions table
DROP TABLE IF EXISTS public.decisions CASCADE;
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

-- Create uploads table
DROP TABLE IF EXISTS public.uploads CASCADE;
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
