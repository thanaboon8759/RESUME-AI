-- Create the candidates table in Supabase
DROP TABLE IF EXISTS public.candidates;

CREATE TABLE public.candidates (
    id TEXT PRIMARY KEY,
    candidate_name TEXT NOT NULL,
    position TEXT NOT NULL,
    score INTEGER NOT NULL,
    decision TEXT NOT NULL,
    reason JSONB NOT NULL,
    full_data JSONB NOT NULL, -- Stores the rich UI structure for the frontend
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Note: Run this script in the Supabase SQL Editor.
